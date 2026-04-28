"""Frameless popup window with all 13 sections — replicates widget.gif."""

from __future__ import annotations
import math
import webbrowser
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QRectF, QPointF, Signal
from PySide6.QtGui import (
    QPixmap, QPainter, QColor, QBrush, QPen, QFont, QFontMetrics,
    QLinearGradient, QPainterPath, QGuiApplication, QImage, QPalette,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QScrollArea, QSizePolicy, QApplication,
)

from theme import (
    COLORS, SPRITE_MAP, limit_color, bar_fill,
    status_color, status_color_rgb, component_status_color,
    dumb_level_color, dumb_level_label, dumb_level_emoji,
    format_tokens,
)

ASSETS = Path(__file__).parent / "assets" / "sprites"

POPUP_WIDTH = 400
POPUP_HEIGHT = 900


# ── Helpers ────────────────────────────────────────────────────────
def clear_layout_recursive(layout):
    """Remove and delete all widgets/layouts at any depth so nothing ghost-paints."""
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.setParent(None)
            w.deleteLater()
            continue
        sub = item.layout()
        if sub is not None:
            clear_layout_recursive(sub)


def render_svg_pixmap(svg_path: Path, size: int) -> QPixmap:
    """Render an SVG to a QPixmap at the given size (pixel-art friendly, no smoothing)."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    if not svg_path.exists():
        return pm
    renderer = QSvgRenderer(str(svg_path))
    if not renderer.isValid():
        return pm
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, False)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return pm


def rgba(color_hex: str, alpha: float) -> str:
    c = QColor(color_hex)
    return f"rgba({c.red()},{c.green()},{c.blue()},{alpha})"


def make_card(parent=None, object_name="card") -> QFrame:
    f = QFrame(parent)
    f.setObjectName(object_name)
    f.setProperty("class", "card")
    return f


# ── Custom painted sub-widgets ─────────────────────────────────────
class ProgressRing(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pct = 0.0
        self._color = QColor(COLORS["amber"])
        self.setFixedSize(96, 96)

    def set_value(self, pct: float, color_hex: str):
        self._pct = max(0.0, min(100.0, float(pct)))
        self._color = QColor(color_hex)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        side = min(self.width(), self.height()) - 10
        rect = QRectF((self.width() - side) / 2, (self.height() - side) / 2, side, side)

        pen_bg = QPen(QColor(255, 255, 255, 20))
        pen_bg.setWidth(8)
        pen_bg.setCapStyle(Qt.FlatCap)
        p.setPen(pen_bg)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(rect)

        if self._pct > 0:
            pen_fg = QPen(self._color)
            pen_fg.setWidth(8)
            pen_fg.setCapStyle(Qt.RoundCap)
            p.setPen(pen_fg)
            span = int(-360 * 16 * (self._pct / 100.0))
            p.drawArc(rect, 90 * 16, span)

        p.end()


class ProgressBar(QWidget):
    def __init__(self, parent=None, height=6):
        super().__init__(parent)
        self._pct = 0.0
        self._color = QColor(COLORS["amber"])
        self.setFixedHeight(height)
        self.setMinimumWidth(80)

    def set_value(self, pct: float, color_hex: str):
        self._pct = max(0.0, min(100.0, float(pct)))
        self._color = QColor(color_hex)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        radius = rect.height() / 2
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 22))
        p.drawRoundedRect(rect, radius, radius)
        if self._pct > 0:
            w = int(rect.width() * (self._pct / 100.0))
            fill = QRectF(0, 0, w, rect.height())
            p.setBrush(self._color)
            p.drawRoundedRect(fill, radius, radius)


class StackedModelBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._segments: list[tuple[float, QColor]] = []
        self.setFixedHeight(8)

    def set_segments(self, segments):
        self._segments = [(float(pct), QColor(color)) for pct, color in segments]
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        radius = 4
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), radius, radius)
        p.setClipPath(path)

        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 22))
        p.drawRect(rect)

        x = 0.0
        total = sum(s[0] for s in self._segments) or 100.0
        for pct, color in self._segments:
            w = rect.width() * (pct / total)
            p.setBrush(color)
            p.drawRect(QRectF(x, 0, w, rect.height()))
            x += w


class TrendChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: list[dict] = []
        self.setMinimumHeight(56)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_data(self, data):
        self._data = data or []
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), Qt.transparent)

        data = self._data
        if not data:
            return

        w = self.width()
        h = self.height()
        max_t = max((d.get("tokens") or 0) for d in data) or 1
        n = len(data)
        bw = (w - 12) / n
        pad = 3
        ch = h - 14

        for i, d in enumerate(data):
            x = 6 + i * bw + pad / 2
            tokens = d.get("tokens") or 0
            bar_h = max(2, (tokens / max_t) * ch)
            y = ch - bar_h
            b_width = bw - pad
            is_last = i == n - 1
            alpha = 217 if is_last else int((0.2 + (i / n) * 0.2) * 255)
            alpha = max(40, min(255, alpha))

            color = QColor(217, 119, 6, alpha)
            p.setBrush(color)
            p.setPen(Qt.NoPen)
            rect = QRectF(x, y, b_width, bar_h)
            path = QPainterPath()
            r = min(4, b_width / 2)
            path.moveTo(rect.left() + r, rect.top())
            path.lineTo(rect.right() - r, rect.top())
            path.quadTo(rect.right(), rect.top(), rect.right(), rect.top() + r)
            path.lineTo(rect.right(), rect.bottom())
            path.lineTo(rect.left(), rect.bottom())
            path.lineTo(rect.left(), rect.top() + r)
            path.quadTo(rect.left(), rect.top(), rect.left() + r, rect.top())
            p.drawPath(path)

            # Day label
            label = str(d.get("label") or "")
            f = QFont("Segoe UI", 7)
            if is_last:
                f.setBold(True)
            p.setFont(f)
            text_color = QColor(COLORS["text"])
            text_color.setAlphaF(0.8 if is_last else 0.35)
            p.setPen(text_color)
            fm = QFontMetrics(f)
            tw = fm.horizontalAdvance(label)
            p.drawText(int(x + b_width / 2 - tw / 2), h - 2, label)


class PeakHoursChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: dict = {}
        self.setMinimumHeight(40)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_data(self, data: dict):
        self._data = data or {}
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        w = self.width()
        h = self.height()
        if not self._data:
            return

        vals = []
        for i in range(24):
            v = self._data.get(str(i)) or 0
            vals.append(v)
        max_v = max(vals) or 1

        bw = (w - 4) / 24
        ch = h - 12

        for i, v in enumerate(vals):
            x = 2 + i * bw + 1
            bar_h = max(1, (v / max_v) * ch)
            y = ch - bar_h
            b_width = bw - 2
            alpha = (0.3 + (v / max_v) * 0.5) if v > 0 else 0.08
            if 9 <= i <= 18:
                color = QColor(217, 119, 6)
            else:
                color = QColor(59, 130, 246)
            color.setAlphaF(alpha)
            p.setBrush(color)
            p.setPen(Qt.NoPen)
            p.drawRect(QRectF(x, y, b_width, bar_h))

            if i % 6 == 0:
                f = QFont("Segoe UI", 6)
                p.setFont(f)
                tc = QColor(COLORS["text"])
                tc.setAlphaF(0.3)
                p.setPen(tc)
                fm = QFontMetrics(f)
                lbl = f"{i}h"
                tw = fm.horizontalAdvance(lbl)
                p.drawText(int(x + b_width / 2 - tw / 2), h - 2, lbl)


class PulseDot(QWidget):
    def __init__(self, size=10, parent=None):
        super().__init__(parent)
        self._color = QColor(COLORS["green"])
        self._pulsing = False
        self._alpha = 1.0
        self._dir = -1
        self.setFixedSize(size, size)
        self._timer = QTimer(self)
        self._timer.setInterval(60)
        self._timer.timeout.connect(self._tick)

    def set_state(self, color_hex: str, pulsing: bool):
        self._color = QColor(color_hex)
        self._pulsing = pulsing
        if pulsing:
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._timer.stop()
            self._alpha = 1.0
        self.update()

    def _tick(self):
        self._alpha += 0.04 * self._dir
        if self._alpha <= 0.3:
            self._alpha = 0.3
            self._dir = 1
        elif self._alpha >= 1.0:
            self._alpha = 1.0
            self._dir = -1
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QColor(self._color)
        c.setAlphaF(self._alpha)
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        p.drawEllipse(self.rect())


# ── Header ─────────────────────────────────────────────────────────
class HeaderWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._sprites: dict[str, list[QPixmap]] = {}
        self._sprite_frame = 0
        self._sprite_level = "genius"

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 6)
        layout.setSpacing(12)

        # Mascot stack (clawd background + overlay sprite)
        self.mascot_wrap = QWidget(self)
        self.mascot_wrap.setFixedSize(64, 64)
        self.clawd = QLabel(self.mascot_wrap)
        self.clawd.setGeometry(8, 10, 48, 48)
        self.clawd.setScaledContents(False)
        self.clawd.setAlignment(Qt.AlignCenter)
        self.clawd.setPixmap(render_svg_pixmap(ASSETS / "clawd.svg", 48))
        self.sprite_label = QLabel(self.mascot_wrap)
        self.sprite_label.setGeometry(0, 0, 64, 64)
        self.sprite_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.mascot_wrap)

        info = QWidget(self)
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(0, 4, 0, 0)
        info_layout.setSpacing(3)

        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        self.title = QLabel("Claude", self)
        self.title.setStyleSheet(f"font-size:22px;font-weight:700;color:{COLORS['text']};")
        self.pill = QLabel("Genius", self)
        self.pill.setStyleSheet(
            "padding:2px 7px;border-radius:10px;font-size:12px;font-weight:700;"
        )
        title_row.addWidget(self.title)
        title_row.addWidget(self.pill)
        title_row.addStretch(1)
        info_layout.addLayout(title_row)

        sub_row = QHBoxLayout()
        sub_row.setSpacing(4)
        self.logo = QLabel(self)
        self.logo.setPixmap(render_svg_pixmap(ASSETS / "claude-logo.svg", 12))
        self.plan_label = QLabel("Max (20x)", self)
        self.plan_label.setStyleSheet(f"font-size:10px;color:{COLORS['amber']};")
        self.source_dot = QLabel("\u2022", self)
        self.source_dot.setStyleSheet(f"color:{COLORS['text_dim']};font-size:10px;")
        self.source_label = QLabel("Live", self)
        self.source_label.setStyleSheet(f"font-size:10px;color:{COLORS['green']};")
        sub_row.addWidget(self.logo)
        sub_row.addWidget(self.plan_label)
        sub_row.addWidget(self.source_dot)
        sub_row.addWidget(self.source_label)
        sub_row.addStretch(1)
        info_layout.addLayout(sub_row)
        info_layout.addStretch(1)

        layout.addWidget(info, 1)

        self._load_sprites()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)

    def _load_sprites(self):
        for level, cfg in SPRITE_MAP.items():
            self._sprites[level] = [
                QPixmap(str(ASSETS / f"{cfg['prefix']}-{i}.png"))
                for i in range(cfg["frames"])
            ]

    def _advance(self):
        frames = self._sprites.get(self._sprite_level) or []
        if not frames:
            return
        self._sprite_frame = (self._sprite_frame + 1) % len(frames)
        self.sprite_label.setPixmap(frames[self._sprite_frame])

    def update_data(self, data: dict):
        dumb = data.get("dumbness") or {}
        level = dumb.get("level") or "genius"
        rl = data.get("rateLimits") or {}
        plan = rl.get("plan") or "Max (20x)"
        source = "Live" if rl.get("source") == "api" else "Offline"
        indicator = (data.get("serviceStatus") or {}).get("indicator") or "none"

        self.plan_label.setText(plan)
        self.source_label.setText(source)
        self.source_label.setStyleSheet(
            f"font-size:10px;color:{COLORS['green'] if source == 'Live' else COLORS['text']};"
        )

        # Pill
        r, g, b = status_color_rgb(indicator)
        clr = dumb_level_color(level)
        self.pill.setText(dumb_level_label(level))
        self.pill.setStyleSheet(
            f"padding:2px 7px;border-radius:10px;font-size:12px;font-weight:700;"
            f"background:rgba({r},{g},{b},0.18);color:{clr};"
        )

        # Mascot
        self.clawd.setVisible(level != "braindead")
        if level != self._sprite_level or not self._timer.isActive():
            self._sprite_level = level
            self._sprite_frame = 0
            frames = self._sprites.get(level) or []
            if frames:
                self.sprite_label.setPixmap(frames[0])
            self._timer.stop()
            self._timer.start(SPRITE_MAP.get(level, {}).get("interval", 200))


# ── Session Card (Hero) ────────────────────────────────────────────
class SessionCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sessionCard")
        self._reset_min_target = 0  # epoch seconds countdown target

        v = QVBoxLayout(self)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(6)

        header = QHBoxLayout()
        self.title = QLabel("Current session", self)
        self.title.setStyleSheet(f"font-size:12px;font-weight:600;color:{rgba(COLORS['text'], 0.7)};")
        self.reset_label = QLabel("", self)
        self.reset_label.setStyleSheet(f"font-size:11px;color:{rgba(COLORS['text'], 0.4)};")
        header.addWidget(self.title)
        header.addStretch(1)
        header.addWidget(self.reset_label)
        v.addLayout(header)

        ring_wrap = QHBoxLayout()
        ring_wrap.addStretch(1)
        ring_holder = QWidget(self)
        ring_holder.setFixedSize(96, 96)
        self.ring = ProgressRing(ring_holder)
        self.ring.setGeometry(0, 0, 96, 96)
        self.ring_label = QLabel("--%", ring_holder)
        self.ring_label.setGeometry(0, 0, 96, 96)
        self.ring_label.setAlignment(Qt.AlignCenter)
        self.ring_label.setStyleSheet(
            f"font-size:28px;font-weight:700;color:{COLORS['text']};background:transparent;"
        )
        ring_wrap.addWidget(ring_holder)
        ring_wrap.addStretch(1)
        v.addLayout(ring_wrap)

        self.alert_label = QLabel("", self)
        self.alert_label.setAlignment(Qt.AlignCenter)
        self.alert_label.setStyleSheet(
            f"font-size:10px;font-style:italic;color:{COLORS['amber_light']};"
        )
        self.alert_label.hide()
        v.addWidget(self.alert_label)

        self._pct = 0.0
        self._countdown = QTimer(self)
        self._countdown.setInterval(1000)
        self._countdown.timeout.connect(self._tick)

    def _tick(self):
        import time
        remain = max(0, self._reset_min_target - int(time.time()))
        h = remain // 3600
        m = (remain % 3600) // 60
        s = remain % 60
        if h > 0:
            self.reset_label.setText(f"Resets in {h}h {m:02d}m {s:02d}s")
        elif m > 0:
            self.reset_label.setText(f"Resets in {m}m {s:02d}s")
        elif s > 0:
            self.reset_label.setText(f"Resets in {s}s")
        else:
            self.reset_label.setText("Rolling 5h")

    def update_data(self, data: dict):
        import time
        session = (data.get("rateLimits") or {}).get("session") or {}
        pct = float(session.get("percentUsed") or 0)
        reset_min = float(session.get("resetsInMinutes") or 0)
        self._pct = pct

        color = limit_color(pct)
        stroke = bar_fill(pct, COLORS["amber"])
        self.ring.set_value(pct, stroke)
        self.ring_label.setText(f"{round(pct)}%")
        self.ring_label.setStyleSheet(
            f"font-size:28px;font-weight:700;color:{color};background:transparent;"
        )

        # Border
        if pct > 80:
            border = "rgba(239,68,68,0.6)"
        elif pct > 50:
            border = "rgba(245,158,11,0.5)"
        else:
            border = "rgba(217,119,6,0.35)"
        self.setStyleSheet(
            f"#sessionCard {{ background:{COLORS['bg_card']}; border:2px solid {border}; border-radius:12px; }}"
        )

        self._reset_min_target = int(time.time() + reset_min * 60)
        self._tick()
        self._countdown.start()

        # Predictive alert
        eta = data.get("limitEta") or {}
        m2l = eta.get("minutesToLimit")
        if m2l is not None and 0 < m2l < 120:
            self.alert_label.setText(f"At current rate, limit in {eta.get('label', '?')}")
            self.alert_label.show()
        else:
            self.alert_label.hide()


# ── Weekly Card ────────────────────────────────────────────────────
class WeeklyCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", "card")
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(10)

        title = QLabel("Weekly limits", self)
        title.setStyleSheet(f"font-size:11px;font-weight:600;color:{rgba(COLORS['text'], 0.45)};letter-spacing:0.5px;")
        v.addWidget(title)

        self.all_row, self.all_bar, self.all_pct, self.all_reset = self._mk_row(v, "All models", COLORS["blue"])
        self.son_row, self.son_bar, self.son_pct, self.son_reset = self._mk_row(v, "Sonnet only", COLORS["green"])

    def _mk_row(self, parent_layout, label, dot_color):
        section = QVBoxLayout()
        section.setSpacing(3)
        row = QHBoxLayout()
        row.setSpacing(4)
        dot = QLabel(self)
        dot.setFixedSize(8, 8)
        dot.setStyleSheet(f"background:{dot_color};border-radius:4px;")
        name = QLabel(label, self)
        name.setStyleSheet(f"font-size:12px;color:{COLORS['text']};")
        reset = QLabel("", self)
        reset.setStyleSheet(f"font-size:10px;color:{rgba(COLORS['text'], 0.35)};")
        pct = QLabel("--%", self)
        pct.setStyleSheet(f"font-size:14px;font-weight:700;color:{COLORS['text']};")
        row.addWidget(dot)
        row.addWidget(name)
        row.addStretch(1)
        row.addWidget(reset)
        row.addWidget(pct)
        section.addLayout(row)
        bar = ProgressBar(self)
        section.addWidget(bar)
        parent_layout.addLayout(section)
        return (row, bar, pct, reset)

    def update_data(self, data: dict):
        rl = data.get("rateLimits") or {}
        wa = rl.get("weeklyAll") or {}
        ws = rl.get("weeklySonnet") or {}

        wa_pct = float(wa.get("percentUsed") or 0)
        ws_pct = float(ws.get("percentUsed") or 0)

        self.all_pct.setText(f"{round(wa_pct)}%")
        self.all_pct.setStyleSheet(f"font-size:14px;font-weight:700;color:{limit_color(wa_pct)};")
        self.all_reset.setText(f"Resets {wa.get('resetsLabel') or ''}".strip())
        self.all_bar.set_value(wa_pct, bar_fill(wa_pct, COLORS["blue"]))

        self.son_pct.setText(f"{round(ws_pct)}%")
        self.son_pct.setStyleSheet(f"font-size:14px;font-weight:700;color:{limit_color(ws_pct)};")
        self.son_reset.setText(f"Resets {ws.get('resetsLabel') or ''}".strip())
        self.son_bar.set_value(ws_pct, bar_fill(ws_pct, COLORS["green"]))


# ── Credits Card ───────────────────────────────────────────────────
class CreditsCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", "card")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(14, 14, 14, 14)
        self._layout.setSpacing(6)

    def _clear(self):
        clear_layout_recursive(self._layout)

    def update_data(self, data: dict):
        rl = data.get("rateLimits") or {}
        credits = rl.get("credits")
        extra = rl.get("extraUsage")
        self._clear()

        if not credits:
            self.hide()
            return
        self.show()

        currency = credits.get("currency") or "USD"
        prefix = "R$ " if currency == "BRL" else "$ "

        # Header
        header = QHBoxLayout()
        icon = QLabel("\U0001F4B3", self); icon.setStyleSheet("font-size:13px;")
        title = QLabel("Credits", self)
        title.setStyleSheet(f"font-size:12px;font-weight:600;color:{rgba(COLORS['text'], 0.55)};")
        amount = QLabel(f"{prefix}{float(credits.get('amount') or 0):,.2f}", self)
        amount.setStyleSheet(f"font-size:17px;font-weight:700;color:{COLORS['amber']};")
        header.addWidget(icon)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(amount)
        self._layout.addLayout(header)

        # Auto-reload
        auto = bool(credits.get("autoReload"))
        reload_row = QHBoxLayout()
        rl_icon = QLabel("\u21BB", self); rl_icon.setStyleSheet(f"color:{rgba(COLORS['text'], 0.4)};font-size:11px;")
        rl_lbl = QLabel("Auto-reload", self); rl_lbl.setStyleSheet(f"font-size:11px;color:{rgba(COLORS['text'], 0.5)};")
        rl_val = QLabel("ON" if auto else "OFF", self)
        rl_val.setStyleSheet(
            f"font-size:11px;font-weight:700;color:{COLORS['green'] if auto else COLORS['amber_light']};"
        )
        reload_row.addWidget(rl_icon); reload_row.addWidget(rl_lbl)
        reload_row.addStretch(1); reload_row.addWidget(rl_val)
        self._layout.addLayout(reload_row)

        if extra:
            divider = QFrame(self)
            divider.setFixedHeight(1)
            divider.setStyleSheet(f"background:{COLORS['border']};")
            self._layout.addWidget(divider)

            ex_currency = extra.get("currency") or "USD"
            ex_prefix = "R$ " if ex_currency == "BRL" else "$ "
            enabled = bool(extra.get("enabled"))

            ex_row = QHBoxLayout()
            ex_icon = QLabel("+", self); ex_icon.setStyleSheet(f"color:{rgba(COLORS['text'], 0.5)};font-weight:700;")
            ex_lbl = QLabel("Extra Usage", self)
            ex_lbl.setStyleSheet(f"font-size:12px;font-weight:600;color:{rgba(COLORS['text'], 0.55)};")
            rgb = (16, 185, 129) if enabled else (239, 68, 68)
            ex_pill = QLabel("Active" if enabled else "Disabled", self)
            ex_pill.setStyleSheet(
                f"padding:2px 6px;border-radius:9px;font-size:10px;font-weight:700;"
                f"background:rgba({rgb[0]},{rgb[1]},{rgb[2]},0.18);"
                f"color:{COLORS['green'] if enabled else COLORS['red']};"
            )
            ex_row.addWidget(ex_icon); ex_row.addWidget(ex_lbl)
            ex_row.addStretch(1); ex_row.addWidget(ex_pill)
            self._layout.addLayout(ex_row)

            limit = float(extra.get("monthlyLimit") or 0)
            used = float(extra.get("usedCredits") or 0)

            lim_row = QHBoxLayout()
            lim_lbl = QLabel("Monthly limit", self); lim_lbl.setStyleSheet(f"font-size:11px;color:{rgba(COLORS['text'], 0.5)};")
            lim_val = QLabel(f"{ex_prefix}{limit:,.2f}", self)
            lim_val.setStyleSheet("font-size:11px;font-weight:600;")
            lim_row.addWidget(lim_lbl); lim_row.addStretch(1); lim_row.addWidget(lim_val)
            self._layout.addLayout(lim_row)

            used_row = QHBoxLayout()
            used_lbl = QLabel("Used", self); used_lbl.setStyleSheet(f"font-size:11px;color:{rgba(COLORS['text'], 0.5)};")
            used_val = QLabel(f"{ex_prefix}{used:,.2f} / {ex_prefix}{limit:,.2f}", self)
            used_val.setStyleSheet(f"font-size:10px;color:{rgba(COLORS['text'], 0.6)};")
            used_row.addWidget(used_lbl); used_row.addStretch(1); used_row.addWidget(used_val)
            self._layout.addLayout(used_row)

            bar = ProgressBar(self)
            pct = min(100.0, (used / limit * 100.0) if limit > 0 else 0)
            color = COLORS["red"] if (limit and used / limit > 0.8) else COLORS["amber"]
            bar.set_value(pct, color)
            self._layout.addWidget(bar)


# ── Health Card ────────────────────────────────────────────────────
class HealthCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", "card")
        self.setObjectName("healthCard")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(14, 14, 14, 14)
        self._layout.setSpacing(6)

        self._header = QHBoxLayout()
        self.dot = PulseDot(10, self)
        self.title = QLabel("Service Health", self)
        self.title.setStyleSheet(f"font-size:12px;font-weight:600;color:{rgba(COLORS['text'], 0.65)};")
        self.pill = QLabel("", self)
        self._header.addWidget(self.dot)
        self._header.addWidget(self.title)
        self._header.addStretch(1)
        self._header.addWidget(self.pill)
        self._layout.addLayout(self._header)

        self.components_wrap = QWidget(self)
        self.components_layout = QHBoxLayout(self.components_wrap)
        self.components_layout.setContentsMargins(0, 0, 0, 0)
        self.components_layout.setSpacing(8)
        self._layout.addWidget(self.components_wrap)

        dd_row = QHBoxLayout()
        dd_icon = QLabel("\U0001F310", self); dd_icon.setStyleSheet(f"font-size:9px;color:{rgba(COLORS['text'], 0.35)};")
        dd_lbl = QLabel("User reports:", self); dd_lbl.setStyleSheet(f"font-size:10px;color:{rgba(COLORS['text'], 0.35)};")
        self.dd_btn = QPushButton("DownDetector \u2197", self)
        self.dd_btn.setCursor(Qt.PointingHandCursor)
        self.dd_btn.setFlat(True)
        self.dd_btn.setStyleSheet(
            f"QPushButton{{background:transparent;border:none;color:{COLORS['text']};"
            f"font-size:10px;padding:0;text-align:right;}}"
            f"QPushButton:hover{{color:{COLORS['text']};text-decoration:underline;}}"
        )
        self.dd_btn.clicked.connect(lambda: webbrowser.open("https://downdetector.com/status/claude-ai/"))
        dd_row.addWidget(dd_icon)
        dd_row.addWidget(dd_lbl)
        dd_row.addStretch(1)
        dd_row.addWidget(self.dd_btn)
        self._layout.addLayout(dd_row)

        self.incident_label = QLabel("", self)
        self.incident_label.setWordWrap(True)
        self.incident_label.setStyleSheet(f"font-size:10px;font-weight:600;color:{COLORS['red']};")
        self.incident_update = QLabel("", self)
        self.incident_update.setWordWrap(True)
        self.incident_update.setStyleSheet(f"font-size:10px;color:{rgba(COLORS['text'], 0.5)};")
        self._layout.addWidget(self.incident_label)
        self._layout.addWidget(self.incident_update)

    def _clear_components(self):
        clear_layout_recursive(self.components_layout)

    def update_data(self, data: dict):
        status = data.get("serviceStatus") or {}
        indicator = status.get("indicator") or "none"
        components = status.get("components") or []
        incidents = status.get("active_incidents") or []

        if indicator == "none":
            bg, border = COLORS["bg_card"], COLORS["border"]
        elif indicator == "minor":
            bg, border = "rgba(251,158,22,0.10)", "rgba(251,158,22,0.40)"
        else:
            bg, border = "rgba(239,68,68,0.10)", "rgba(239,68,68,0.40)"

        self.setStyleSheet(
            f"#healthCard {{ background:{bg}; border:1px solid {border}; border-radius:10px; }}"
        )
        self.dot.set_state(status_color(indicator), pulsing=(indicator != "none"))

        r, g, b = status_color_rgb(indicator)
        label_map = {"none": "Healthy", "minor": "Degraded", "major": "Major Outage", "critical": "Critical Outage"}
        self.pill.setText(label_map.get(indicator, "Unknown"))
        self.pill.setStyleSheet(
            f"padding:3px 8px;border-radius:10px;font-size:11px;font-weight:700;"
            f"background:rgba({r},{g},{b},0.20);border:1px solid rgba({r},{g},{b},0.55);"
            f"color:{status_color(indicator)};"
        )

        self._clear_components()
        for c in components:
            item = QWidget(self.components_wrap)
            il = QHBoxLayout(item)
            il.setContentsMargins(0, 0, 0, 0); il.setSpacing(3)
            cdot = QLabel(item)
            cdot.setFixedSize(6, 6)
            cdot.setStyleSheet(f"background:{component_status_color(c.get('status', ''))};border-radius:3px;")
            cname = QLabel(c.get("name") or "", item)
            cname.setStyleSheet(f"font-size:10px;color:{rgba(COLORS['text'], 0.55)};")
            il.addWidget(cdot); il.addWidget(cname)
            self.components_layout.addWidget(item)
        self.components_layout.addStretch(1)

        if incidents:
            inc = incidents[0]
            self.incident_label.setText(inc.get("name") or "")
            self.incident_update.setText(inc.get("latest_update") or "")
            self.incident_label.show()
            self.incident_update.setVisible(bool(inc.get("latest_update")))
        else:
            self.incident_label.hide()
            self.incident_update.hide()


# ── Dumbness Card ──────────────────────────────────────────────────
class DumbnessCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", "card")
        self.setObjectName("dumbCard")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(14, 14, 14, 14)
        self._layout.setSpacing(4)

        header = QHBoxLayout()
        self.emoji = QLabel("", self)
        self.emoji.setStyleSheet("font-size:13px;font-weight:700;")
        self.badge = QLabel("", self)
        header.addWidget(self.emoji)
        header.addStretch(1)
        header.addWidget(self.badge)
        self._layout.addLayout(header)

        self.reasons_container = QWidget(self)
        self.reasons_layout = QVBoxLayout(self.reasons_container)
        self.reasons_layout.setContentsMargins(0, 2, 0, 0)
        self.reasons_layout.setSpacing(2)
        self._layout.addWidget(self.reasons_container)

        self.tip = QLabel("", self)
        self.tip.setStyleSheet(f"font-size:10px;font-style:italic;color:{rgba(COLORS['text'], 0.45)};")
        self._layout.addWidget(self.tip)

    def _clear_reasons(self):
        clear_layout_recursive(self.reasons_layout)

    def update_data(self, data: dict):
        d = data.get("dumbness") or {}
        score = int(d.get("score") or 0)
        level = d.get("level") or "genius"
        reasons = d.get("reasons") or []
        adaptive_on = (data.get("adaptiveThinking") or {}).get("adaptive_thinking", True)

        if score <= 0:
            self.hide()
            return
        self.show()

        if score >= 75:
            bg = "rgba(239,68,68,0.12)"
        elif score >= 50:
            bg = "rgba(249,115,22,0.10)"
        elif score >= 25:
            bg = "rgba(245,158,11,0.10)"
        else:
            bg = COLORS["bg_card"]

        self.setStyleSheet(
            f"#dumbCard {{ background:{bg}; border:1px solid {COLORS['border']}; border-radius:10px; }}"
        )

        self.emoji.setText(dumb_level_emoji(level))

        if score >= 75:
            bbg, bclr = "rgba(239,68,68,0.25)", COLORS["red"]
        elif score >= 50:
            bbg, bclr = "rgba(249,115,22,0.25)", COLORS["orange"]
        else:
            bbg, bclr = "rgba(245,158,11,0.25)", COLORS["amber_light"]
        self.badge.setText(f"{score}/100")
        self.badge.setStyleSheet(
            f"padding:3px 7px;border-radius:10px;font-size:11px;font-weight:700;background:{bbg};color:{bclr};"
        )

        self._clear_reasons()
        for r in reasons:
            lbl = QLabel(f"  \u2022 {r}", self.reasons_container)
            lbl.setWordWrap(True)
            lbl.setStyleSheet(f"font-size:10px;color:{rgba(COLORS['text'], 0.55)};")
            self.reasons_layout.addWidget(lbl)

        if not adaptive_on:
            self.tip.setText("Tip: Adaptive Thinking is OFF in settings.json")
            self.tip.show()
        else:
            self.tip.hide()


# ── Activity Card ──────────────────────────────────────────────────
class ActivityCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", "card")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(14, 14, 14, 14)
        self._layout.setSpacing(6)

    def _clear(self):
        clear_layout_recursive(self._layout)

    def _row(self, icon, label, value, color):
        row = QHBoxLayout()
        ic = QLabel(icon, self); ic.setStyleSheet(f"font-size:11px;color:{rgba(COLORS['text'], 0.5)};")
        ic.setFixedWidth(16); ic.setAlignment(Qt.AlignCenter)
        lb = QLabel(label, self); lb.setStyleSheet(f"font-size:11px;color:{rgba(COLORS['text'], 0.6)};")
        val = QLabel(str(value), self)
        val.setStyleSheet(f"font-size:11px;font-weight:700;color:{color};")
        row.addWidget(ic); row.addWidget(lb); row.addStretch(1); row.addWidget(val)
        self._layout.addLayout(row)

    def update_data(self, data: dict):
        self._clear()

        title = QLabel("Activity", self)
        title.setStyleSheet(f"font-size:11px;font-weight:600;color:{rgba(COLORS['text'], 0.45)};letter-spacing:0.5px;")
        self._layout.addWidget(title)

        burn = float((data.get("burnRate") or {}).get("output_per_hour") or 0)
        if burn >= 1e6:
            burn_text = f"{burn/1e6:.1f}M/h"
        elif burn >= 1e3:
            burn_text = f"{burn/1e3:.0f}K/h"
        else:
            burn_text = f"{int(burn)}/h"
        self._row("\u26A1", "Burn rate", burn_text,
                  COLORS["amber_light"] if burn > 500_000 else COLORS["text"])

        errs = int((data.get("errorRate") or {}).get("total") or 0)
        err_text = f"{errs} errors" if errs > 0 else "None"
        err_color = COLORS["red"] if errs > 5 else COLORS["amber_light"] if errs > 0 else COLORS["green"]
        self._row("\u26A0", "Errors (2h)", err_text, err_color)

        adaptive = (data.get("adaptiveThinking") or {}).get("adaptive_thinking", True)
        self._row("\u2699", "Adaptive Thinking",
                  "ON" if adaptive else "OFF",
                  COLORS["green"] if adaptive else COLORS["red"])

        avg = float((data.get("responseQuality") or {}).get("avgTokensPerResponse") or 0)
        if avg > 0:
            avg_c = COLORS["green"] if avg > 500 else COLORS["amber_light"] if avg > 200 else COLORS["red"]
            self._row("\u270F", "Avg response", f"{format_tokens(avg)} tok", avg_c)

        lat = float((data.get("latency") or {}).get("avgSeconds") or 0)
        if lat > 0:
            lat_c = COLORS["green"] if lat < 10 else COLORS["amber_light"] if lat < 30 else COLORS["red"]
            self._row("\u23F1", "Avg latency", f"{lat:.1f}s", lat_c)

        models = data.get("modelBreakdown") or []
        if models:
            sub = QLabel("Model split", self)
            sub.setStyleSheet(f"font-size:10px;color:{rgba(COLORS['text'], 0.4)};margin-top:4px;")
            self._layout.addWidget(sub)

            bar = StackedModelBar(self)
            bar.set_segments([(m.get("percentage") or 0, m.get("color") or "#9CA3AF") for m in models])
            self._layout.addWidget(bar)

            legend_row = QHBoxLayout()
            legend_row.setSpacing(6)
            for m in models:
                pct = float(m.get("percentage") or 0)
                if pct <= 0.5:
                    continue
                item = QHBoxLayout()
                item.setSpacing(3)
                dot = QLabel(self); dot.setFixedSize(6, 6)
                dot.setStyleSheet(f"background:{m.get('color') or '#9CA3AF'};border-radius:3px;")
                nm = QLabel(f"{m.get('model', '')} {round(pct)}%", self)
                nm.setStyleSheet(f"font-size:10px;color:{rgba(COLORS['text'], 0.5)};")
                item.addWidget(dot); item.addWidget(nm)
                legend_row.addLayout(item)
            legend_row.addStretch(1)
            self._layout.addLayout(legend_row)


# ── Quick Actions ──────────────────────────────────────────────────
class QuickActions(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: dict = {}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.btn_claude = self._mk_btn("\U0001F310", "claude.ai")
        self.btn_status = self._mk_btn("\U0001F517", "Status")
        self.btn_copy = self._mk_btn("\U0001F4CB", "Copy Stats")

        self.btn_claude.clicked.connect(lambda: webbrowser.open("https://claude.ai"))
        self.btn_status.clicked.connect(lambda: webbrowser.open("https://status.claude.com"))
        self.btn_copy.clicked.connect(self._copy_stats)

        layout.addWidget(self.btn_claude)
        layout.addWidget(self.btn_status)
        layout.addWidget(self.btn_copy)

    def _mk_btn(self, icon, text) -> QPushButton:
        btn = QPushButton(f"{icon} {text}", self)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background:{COLORS['bg_card']};
                border:1px solid {COLORS['border']};
                border-radius:8px;
                padding:7px 4px;
                font-size:10px;
                color:{COLORS['text']};
            }}
            QPushButton:hover {{
                background:rgba(255,255,255,0.08);
            }}
        """)
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        return btn

    def update_data(self, data: dict):
        self._data = data

    def _copy_stats(self):
        d = self._data
        session_pct = round(float((d.get("rateLimits") or {}).get("session", {}).get("percentUsed") or 0))
        weekly_pct = round(float((d.get("rateLimits") or {}).get("weeklyAll", {}).get("percentUsed") or 0))
        cost = float((d.get("today") or {}).get("costUSD") or 0)
        tokens = (d.get("today") or {}).get("totalTokens") or 0
        text = (f"Claude {datetime.now().strftime('%Y-%m-%d')} | "
                f"Session: {session_pct}% | Weekly: {weekly_pct}% | "
                f"${cost:.2f} | {format_tokens(tokens)} tokens")
        QApplication.clipboard().setText(text)


# ── Trend Card ─────────────────────────────────────────────────────
class TrendCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", "card")
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(4)
        title = QLabel("7-day activity", self)
        title.setStyleSheet(f"font-size:11px;font-weight:600;color:{rgba(COLORS['text'], 0.45)};letter-spacing:0.5px;")
        v.addWidget(title)
        self.chart = TrendChart(self)
        v.addWidget(self.chart)

    def update_data(self, data: dict):
        trend = data.get("trend7d") or []
        if not any((d.get("tokens") or 0) for d in trend):
            self.hide()
            return
        self.show()
        self.chart.set_data(trend)


# ── Peak Hours Card ────────────────────────────────────────────────
class PeakCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", "card")
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(4)
        self.title = QLabel("Peak hours", self)
        self.title.setStyleSheet(f"font-size:11px;font-weight:600;color:{rgba(COLORS['text'], 0.45)};letter-spacing:0.5px;")
        v.addWidget(self.title)
        self.chart = PeakHoursChart(self)
        v.addWidget(self.chart)

    def update_data(self, data: dict):
        peak = (data.get("lifetime") or {}).get("peakHours") or {}
        if not peak:
            self.hide()
            return
        self.show()
        self.chart.set_data(peak)


# ── Footer ─────────────────────────────────────────────────────────
class FooterWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 4, 0, 4)
        self._layout.setSpacing(4)

    def _clear(self):
        clear_layout_recursive(self._layout)

    def update_data(self, data: dict):
        self._clear()
        lifetime = data.get("lifetime") or {}
        sessions = int(lifetime.get("totalSessions") or 0)
        first = lifetime.get("firstSession") or ""
        streak = int((data.get("streak") or {}).get("days") or 0)
        version = data.get("claudeCodeVersion") or ""

        logo_svg = ASSETS / "claude-logo.svg"
        if logo_svg.exists():
            logo = QLabel(self)
            pm = QPixmap(str(logo_svg)).scaled(10, 10, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo.setPixmap(pm)
            self._layout.addWidget(logo)

        sess_lbl = QLabel(f"{sessions} sessions", self)
        sess_lbl.setStyleSheet(f"font-size:10px;color:{rgba(COLORS['text'], 0.3)};")
        self._layout.addWidget(sess_lbl)

        self._layout.addWidget(self._dot())

        if first:
            try:
                d = datetime.fromisoformat(first.replace("Z", "+00:00"))
                since = QLabel(f"since {d.strftime('%b %Y')}", self)
                since.setStyleSheet(f"font-size:10px;color:{rgba(COLORS['text'], 0.3)};")
                self._layout.addWidget(since)
            except Exception:
                pass

        if streak > 1:
            badge = QLabel(f"{streak}d streak", self)
            badge.setStyleSheet(
                f"padding:2px 6px;border-radius:9px;font-size:10px;font-weight:700;"
                f"background:rgba(217,119,6,0.15);color:{COLORS['amber']};"
            )
            self._layout.addWidget(badge)

        self._layout.addStretch(1)

        if version:
            v = QLabel(version, self)
            v.setStyleSheet(f"font-size:10px;color:{rgba(COLORS['text'], 0.2)};")
            self._layout.addWidget(v)
            self._layout.addWidget(self._dot())

        brand = QLabel("Anthropic", self)
        brand.setStyleSheet(f"font-size:10px;font-weight:600;color:{rgba(COLORS['text'], 0.2)};")
        self._layout.addWidget(brand)

    def _dot(self):
        d = QLabel(self); d.setFixedSize(3, 3)
        d.setStyleSheet(f"background:{rgba(COLORS['text'], 0.15)};border-radius:1px;")
        return d


# ── Popup Window root ──────────────────────────────────────────────
class PopupWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("popupRoot")
        self.setWindowFlags(
            Qt.Window
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAutoFillBackground(True)
        self.resize(POPUP_WIDTH, POPUP_HEIGHT)
        self.setMinimumWidth(POPUP_WIDTH)
        self.setMaximumWidth(POPUP_WIDTH)

        pal = self.palette()
        pal.setColor(QPalette.Window, QColor(COLORS['bg']))
        pal.setColor(QPalette.Base, QColor(COLORS['bg']))
        pal.setColor(QPalette.WindowText, QColor(COLORS['text']))
        self.setPalette(pal)

        self.setStyleSheet(f"""
            QLabel {{
                background: transparent;
                color: {COLORS['text']};
                font-family: "Segoe UI", Arial, sans-serif;
                font-size: 13px;
            }}
            QFrame[class="card"] {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
            }}
            QFrame#sessionCard {{
                background: {COLORS['bg_card']};
                border-radius: 12px;
            }}
            QFrame#healthCard, QFrame#dumbCard {{
                background: {COLORS['bg_card']};
                border-radius: 10px;
            }}
            QScrollArea, QAbstractScrollArea {{
                background: {COLORS['bg']};
                border: none;
            }}
            QScrollArea > QWidget > QWidget {{
                background: {COLORS['bg']};
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 6px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(255,255,255,0.15);
                border-radius: 3px;
                min-height: 24px;
            }}
            QScrollBar::add-line, QScrollBar::sub-line {{ height: 0px; }}
        """)

        # Scroll area
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(scroll)

        content = QWidget()
        content.setObjectName("popupContent")
        content.setAttribute(Qt.WA_StyledBackground, True)
        v = QVBoxLayout(content)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(10)

        # Build all sections
        self.header = HeaderWidget(content); v.addWidget(self.header)
        self.session = SessionCard(content); v.addWidget(self.session)
        self.weekly = WeeklyCard(content); v.addWidget(self.weekly)
        self.credits = CreditsCard(content); v.addWidget(self.credits)
        self.health = HealthCard(content); v.addWidget(self.health)
        self.dumbness = DumbnessCard(content); v.addWidget(self.dumbness)
        self.activity = ActivityCard(content); v.addWidget(self.activity)
        self.actions = QuickActions(content); v.addWidget(self.actions)
        self.trend = TrendCard(content); v.addWidget(self.trend)
        self.peak = PeakCard(content); v.addWidget(self.peak)
        self.footer = FooterWidget(content); v.addWidget(self.footer)
        v.addStretch(1)

        scroll.setWidget(content)

    def update_data(self, data: dict):
        self.header.update_data(data)
        self.session.update_data(data)
        self.weekly.update_data(data)
        self.credits.update_data(data)
        self.health.update_data(data)
        self.dumbness.update_data(data)
        self.activity.update_data(data)
        self.actions.update_data(data)
        self.trend.update_data(data)
        self.peak.update_data(data)
        self.footer.update_data(data)

    def toggle_near(self, anchor_rect):
        """Show or hide the popup near a given screen-coordinate rect."""
        if self.isVisible():
            self.hide()
            return
        screen = QGuiApplication.screenAt(anchor_rect.topLeft()) or QGuiApplication.primaryScreen()
        g = screen.availableGeometry()
        margin = 8
        max_height = g.height() - 2 * margin
        popup_h = min(POPUP_HEIGHT, max_height)
        self.resize(POPUP_WIDTH, popup_h)
        x = min(g.right() - POPUP_WIDTH - margin, max(g.left() + margin, anchor_rect.right() - POPUP_WIDTH))
        if anchor_rect.top() - popup_h - 4 >= g.top() + margin:
            y = anchor_rect.top() - popup_h - 4
        elif anchor_rect.bottom() + 4 + popup_h <= g.bottom() - margin:
            y = anchor_rect.bottom() + 4
        else:
            y = g.bottom() - popup_h - margin
        y = max(g.top() + margin, min(y, g.bottom() - popup_h - margin))
        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()
