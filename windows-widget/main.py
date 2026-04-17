"""Entry point — wires CompactBar + PopupWindow + DataReader (floating topmost, no AppBar)."""

from __future__ import annotations
import atexit
import ctypes
import signal
import sys
from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from compact_bar import CompactBar  # noqa: E402
from data_reader import DataReader  # noqa: E402
from popup_window import PopupWindow  # noqa: E402


MUTEX_NAME = "Local\\ClaudeUsageWidget_SingleInstance"
_mutex_handle = None


def _acquire_single_instance() -> bool:
    global _mutex_handle
    kernel32 = ctypes.windll.kernel32
    ERROR_ALREADY_EXISTS = 183
    handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if not handle:
        return True
    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        return False
    _mutex_handle = handle
    atexit.register(_release_mutex)
    return True


def _release_mutex():
    global _mutex_handle
    if _mutex_handle:
        try:
            ctypes.windll.kernel32.CloseHandle(_mutex_handle)
        except Exception:
            pass
        _mutex_handle = None


class WidgetApp:
    def __init__(self, app: QApplication):
        self.app = app

        self.compact = CompactBar()
        self.compact.show()

        self.popup = PopupWindow()

        self.reader = DataReader()
        self.reader.changed.connect(self._on_data)
        self.reader.force_reload()

        self.compact.clicked.connect(self._toggle_popup)

        self.tray = self._build_tray()

        app.aboutToQuit.connect(self._cleanup)

    def _build_tray(self) -> QSystemTrayIcon:
        icon_path = ROOT / "assets" / "sprites" / "claude-logo.png"
        icon = QIcon(str(icon_path)) if icon_path.exists() else QIcon()
        tray = QSystemTrayIcon(icon, self.app)
        tray.setToolTip("Claude Usage Monitor")

        menu = QMenu()
        show_action = QAction("Open popup", menu)
        show_action.triggered.connect(self._toggle_popup)
        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self.app.quit)
        menu.addAction(show_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        tray.setContextMenu(menu)

        tray.activated.connect(
            lambda reason: self._toggle_popup() if reason == QSystemTrayIcon.Trigger else None
        )
        tray.show()
        return tray

    def _on_data(self, data: dict):
        self.compact.update_data(data)
        self.popup.update_data(data)

    def _toggle_popup(self):
        geo = self.compact.frameGeometry()
        anchor = QRect(geo.left(), geo.top(), geo.width(), geo.height())
        self.popup.toggle_near(anchor)

    def _cleanup(self):
        _release_mutex()


def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

    if not _acquire_single_instance():
        sys.exit(0)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("Claude Usage Monitor")

    signal.signal(signal.SIGINT, lambda *_: app.quit())

    widget = WidgetApp(app)  # noqa: F841
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
