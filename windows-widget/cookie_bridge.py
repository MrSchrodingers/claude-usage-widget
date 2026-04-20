"""Local HTTP listener for the Chrome extension to drop claude.ai cookies in.

Security posture
----------------
- Binds to 127.0.0.1 only: never reachable from the network.
- Accepts requests only from `chrome-extension://` origins, rejecting web pages
  that might try to POST through the user's browser. (Any installed extension is
  trusted; a malicious extension implies a larger compromise.)
- No CORS headers for wildcard origins: MV3 extensions with matching
  `host_permissions` bypass CORS without needing wildcard ACAO.
- Writes the cookie file with mode 0600 so the session token is not readable by
  other local users.
"""

from __future__ import annotations
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

COOKIE_PATH = Path.home() / ".claude" / "widget-cookies.txt"
BRIDGE_HOST = "127.0.0.1"
BRIDGE_PORT = 47600
MAX_BODY = 65536


def _origin_is_extension(origin: str) -> bool:
    return origin.startswith("chrome-extension://") or origin.startswith("moz-extension://")


class _Handler(BaseHTTPRequestHandler):
    def _reject(self, status: int):
        self.send_response(status)
        self.end_headers()

    def _authorize(self) -> bool:
        origin = self.headers.get("Origin", "")
        return _origin_is_extension(origin)

    def do_OPTIONS(self):
        if not self._authorize():
            self._reject(403); return
        origin = self.headers.get("Origin", "")
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "POST")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        if not self._authorize():
            self._reject(403); return
        if self.path != "/cookies":
            self._reject(404); return
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY:
            self._reject(400); return
        try:
            raw = self.rfile.read(length).decode("utf-8")
            data = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._reject(400); return
        cookies = (data.get("cookies") or "").strip()
        if not cookies or "sessionKey=" not in cookies:
            self._reject(400); return
        try:
            COOKIE_PATH.parent.mkdir(parents=True, exist_ok=True)
            # Create with 0600 before writing so the token is never briefly world-readable.
            fd = os.open(str(COOKIE_PATH), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(cookies)
        except OSError:
            self._reject(500); return
        self.send_response(204)
        origin = self.headers.get("Origin", "")
        self.send_header("Access-Control-Allow-Origin", origin)
        self.end_headers()

    def log_message(self, *_):
        pass


def start_bridge_server():
    """Start listener in a daemon thread; silently no-op if port is busy."""
    def _run():
        try:
            srv = HTTPServer((BRIDGE_HOST, BRIDGE_PORT), _Handler)
            srv.serve_forever()
        except OSError:
            return
    threading.Thread(target=_run, daemon=True).start()
