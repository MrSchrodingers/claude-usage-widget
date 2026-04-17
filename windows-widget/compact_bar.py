"""Inline AppBar widget — mascot + % + progress bar + status dot + status text.

Replicates the visual of screenshots/panel.png (KDE plasmoid compact view).
"""

from __future__ import annotations
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, Signal, QRectF, QPointF
from PySide6.QtGui import QPixmap, QPainter, QColor, QBrush, QPen, QLinearGradient, QFont, QGuiApplication
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QSizePolicy


def _render_svg_pixmap(svg_path, size: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    if not svg_path.exists():
        return pm
    r = QSvgRenderer(str(svg_path))
    if not r.isValid():
        return pm
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, False)
    r.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return pm

from theme import (
    COLORS, SPRITE_MAP, bar_fill, limit_color,
    status_color, dumb_level_label,
)

ASSETS = Path(__file__).parent / "assets" / "sprites"


class _ProgressStripe(QWidget):
    """Slim horizontal progress bar painted manually (matches KDE style)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pct = 0.0
        self._color = QColor(COLORS["amber"])
        self.setMinimumWidth(60)
        self.setFixedHeight(6)

    def set_value(self, pct: float, color_hex: str):
        self._pct = max(0.0, min(100.0, float(pct)))
        self._color = QColor(color_hex)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(0, 1, 0, -1)
        # track
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 28))
        p.drawRoundedRect(rect, 3, 3)
        # fill
        if self._pct > 0:
            w = int(rect.width() * (self._pct / 100.0))
            fill_rect = QRectF(rect.x(), rect.y(), w, rect.height())
            grad = QLinearGradient(fill_rect.topLeft(), fill_rect.topRight())
            base = self._color
            grad.setColorAt(0.0, base.lighter(115))
            grad.setColorAt(1.0, base)
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(fill_rect, 3, 3)


class _StatusDot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._color = QColor(COLORS["green"])
        self._pulse = 1.0
        self.setFixedSize(8, 8)
        self._timer = QTimer(self)
        self._timer.setInterval(60)
        self._timer.timeout.connect(self._tick)
        self._direction = -1
        self._timer.start()

    def set_color(self, color_hex: str, pulsing: bool):
        self._color = QColor(color_hex)
        if not pulsing:
            self._pulse = 1.0
            self._timer.stop()
        elif not self._timer.isActive():
            self._timer.start()
        self.update()

    def _tick(self):
        self._pulse += 0.04 * self._direction
        if self._pulse <= 0.3:
            self._pulse = 0.3
            self._direction = 1
        elif self._pulse >= 1.0:
            self._pulse = 1.0
            self._direction = -1
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QColor(self._color)
        c.setAlphaF(self._pulse)
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        p.drawEllipse(self.rect())


BAR_WIDTH = 240
BAR_HEIGHT = 40
TRAY_RIGHT_OFFSET = 120
BAR_BOTTOM_MARGIN = 0


class CompactBar(QWidget):
    """Floating topmost bar anchored on the taskbar, left of the system tray."""

    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.Window
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setAutoFillBackground(True)
        self.setFixedSize(BAR_WIDTH, BAR_HEIGHT)
        self.setObjectName("compactRoot")
        self.setStyleSheet(f"""
            #compactRoot {{
                background-color: {COLORS["bg"]};
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 6px;
            }}
            QLabel {{
                color: {COLORS["text"]};
                font-family: "Segoe UI", Arial, sans-serif;
                font-size: 11px;
            }}
            QLabel#pct {{
                font-size: 13px;
                font-weight: 700;
            }}
            QLabel#statusText {{
                font-size: 10px;
                color: rgba(255,255,255,0.65);
            }}
        """)
        self._position_taskbar_right()
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            screen.geometryChanged.connect(lambda _: self._position_taskbar_right())
            screen.availableGeometryChanged.connect(lambda _: self._position_taskbar_right())

        self._reposition_timer = QTimer(self)
        self._reposition_timer.setInterval(1000)
        self._reposition_timer.timeout.connect(self._position_taskbar_right)
        self._reposition_timer.start()

    def _position_taskbar_right(self):
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.geometry()
        bar_x = geo.x() + geo.width() - BAR_WIDTH - TRAY_RIGHT_OFFSET
        bar_y = geo.y() + geo.height() - BAR_HEIGHT - BAR_BOTTOM_MARGIN
        self.move(bar_x, bar_y)
        self.raise_()
        if not self.isVisible():
            self.show()

        # Sprite cache
        self._sprites: dict[str, list[QPixmap]] = {}
        self._sprite_frame = 0
        self._sprite_level = "genius"

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(6)

        self.mascot_wrap = QWidget(self)
        self.mascot_wrap.setFixedSize(26, 26)
        self.clawd = QLabel(self.mascot_wrap)
        self.clawd.setGeometry(3, 4, 20, 20)
        self.clawd.setAlignment(Qt.AlignCenter)
        self.clawd.setPixmap(_render_svg_pixmap(ASSETS / "clawd.svg", 20))
        self.mascot = QLabel(self.mascot_wrap)
        self.mascot.setGeometry(0, 0, 26, 26)
        self.mascot.setAlignment(Qt.AlignCenter)
        self.mascot.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        layout.addWidget(self.mascot_wrap)

        self.pct_label = QLabel("--%", self)
        self.pct_label.setObjectName("pct")
        layout.addWidget(self.pct_label)

        self.bar = _ProgressStripe(self)
        self.bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.bar, 1)

        self.dot = _StatusDot(self)
        layout.addWidget(self.dot)

        self.status_label = QLabel("--", self)
        self.status_label.setObjectName("statusText")
        layout.addWidget(self.status_label)

        self._sprite_timer = QTimer(self)
        self._sprite_timer.timeout.connect(self._advance_sprite)

        self._load_sprites()
        self._apply_sprite()

    def _load_sprites(self):
        for level, cfg in SPRITE_MAP.items():
            frames = []
            for i in range(cfg["frames"]):
                p = ASSETS / f"{cfg['prefix']}-{i}.png"
                if p.exists():
                    frames.append(QPixmap(str(p)))
            self._sprites[level] = frames

    def _apply_sprite(self):
        frames = self._sprites.get(self._sprite_level) or []
        if not frames:
            self.mascot.clear()
            return
        px = frames[self._sprite_frame % len(frames)]
        self.mascot.setPixmap(
            px.scaled(26, 26, Qt.KeepAspectRatio, Qt.FastTransformation)
        )
        self.clawd.setVisible(self._sprite_level != "braindead")

    def _advance_sprite(self):
        frames = self._sprites.get(self._sprite_level) or []
        if not frames:
            return
        self._sprite_frame = (self._sprite_frame + 1) % len(frames)
        self._apply_sprite()

    def update_data(self, data: dict):
        rl = (data.get("rateLimits") or {})
        session = (rl.get("session") or {})
        pct = float(session.get("percentUsed") or 0)
        self.pct_label.setText(f"{round(pct)}%")
        self.pct_label.setStyleSheet(f"color: {limit_color(pct)}; font-weight: 700;")
        self.bar.set_value(pct, bar_fill(pct, COLORS["amber"]))

        # Mascot
        dumb = (data.get("dumbness") or {})
        level = dumb.get("level") or "genius"
        if level != self._sprite_level:
            self._sprite_level = level
            self._sprite_frame = 0
            self._apply_sprite()
            interval = SPRITE_MAP.get(level, {}).get("interval", 200)
            self._sprite_timer.stop()
            self._sprite_timer.start(interval)
        elif not self._sprite_timer.isActive():
            self._sprite_timer.start(SPRITE_MAP.get(level, {}).get("interval", 200))

        # Status dot + text
        svc = (data.get("serviceStatus") or {})
        indicator = svc.get("indicator") or "none"
        desc = svc.get("description") or "Operational"
        short = {
            "none": "Operational",
            "minor": "Minor",
            "major": "Degraded",
            "critical": "Outage",
        }.get(indicator, desc)
        self.dot.set_color(status_color(indicator), pulsing=(indicator != "none"))
        self.status_label.setText(short)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
