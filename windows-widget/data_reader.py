"""Watch ~/.claude/widget-data.json and emit parsed payload to Qt slots."""

from __future__ import annotations
import json
from pathlib import Path
from PySide6.QtCore import QObject, QFileSystemWatcher, QTimer, Signal

DATA_PATH = Path.home() / ".claude" / "widget-data.json"
MAX_SIZE = 1_048_576  # 1 MB


class DataReader(QObject):
    changed = Signal(dict)

    def __init__(self, path: Path = DATA_PATH, parent=None):
        super().__init__(parent)
        self._path = path
        self._last_mtime = 0.0
        self._last_payload: dict = {}

        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(self._on_file_event)
        self._watcher.directoryChanged.connect(self._on_file_event)

        if self._path.exists():
            self._watcher.addPath(str(self._path))
        parent_dir = self._path.parent
        if parent_dir.exists():
            self._watcher.addPath(str(parent_dir))

        # Polling fallback — QFileSystemWatcher on Windows misses atomic replaces
        self._poll = QTimer(self)
        self._poll.setInterval(2000)
        self._poll.timeout.connect(self._on_file_event)
        self._poll.start()

    @property
    def payload(self) -> dict:
        return self._last_payload

    def force_reload(self):
        self._last_mtime = 0.0
        self._on_file_event()

    def _on_file_event(self, *_):
        try:
            if not self._path.exists():
                return
            stat = self._path.stat()
            if stat.st_size > MAX_SIZE:
                return
            if stat.st_mtime == self._last_mtime:
                return
            text = self._path.read_text(encoding="utf-8")
            data = json.loads(text)
            if not isinstance(data, dict):
                return
            self._last_mtime = stat.st_mtime
            self._last_payload = data
            self.changed.emit(data)

            # Re-add watcher if file was atomically replaced (inode changed)
            if str(self._path) not in self._watcher.files():
                self._watcher.addPath(str(self._path))
        except (OSError, json.JSONDecodeError):
            return
