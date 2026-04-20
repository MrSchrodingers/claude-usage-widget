"""Local HTTP listener for the Chrome extension to drop claude.ai cookies in."""

from __future__ import annotations
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

COOKIE_PATH = Path.home() / ".claude" / "widget-cookies.txt"
BRIDGE_HOST = "127.0.0.1"
BRIDGE_PORT = 47600
MAX_BODY = 65536


class _Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self):
        if self.path != "/cookies":
            self.send_response(404); self.end_headers(); return
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY:
            self.send_response(400); self.end_headers(); return
        try:
            raw = self.rfile.read(length).decode("utf-8")
            data = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_response(400); self.end_headers(); return
        cookies = (data.get("cookies") or "").strip()
        if not cookies or "sessionKey=" not in cookies:
            self.send_response(400); self.end_headers(); return
        try:
            COOKIE_PATH.parent.mkdir(parents=True, exist_ok=True)
            COOKIE_PATH.write_text(cookies, encoding="utf-8")
        except OSError:
            self.send_response(500); self.end_headers(); return
        self.send_response(204)
        self._cors()
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
