# -*- coding: utf-8 -*-
"""純標準庫伺服器(無需安裝任何套件)。啟動:python3 server.py → http://localhost:8000"""
import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from app import core  # noqa: E402
PORT = int(os.environ.get("PORT", 8000))


class Handler(BaseHTTPRequestHandler):
    def _json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        if u.path == "/" or u.path == "/index.html":
            with open(os.path.join(ROOT, "static", "index.html"), "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif u.path == "/api/suggest-chars":
            self._json(core.suggest_chars(int(q.get("year", 2026)), q.get("gender", "")))
        elif u.path == "/api/suggest-names":
            try:
                self._json(core.suggest_names(q.get("surname", ""),
                                              int(q.get("year", 2026)),
                                              q.get("gender", ""),
                                              int(q.get("length", 2)),
                                              rarity=int(q.get("rarity", 1)),
                                              luck=int(q.get("luck", 1)),
                                              max_strokes=int(q.get("max_strokes", 0)),
                                              like=q.get("like", ""),
                                              dislike=q.get("dislike", "")))
            except ValueError as e:
                self._json({"detail": str(e)}, 400)
        elif u.path == "/api/rules":
            self._json(core.zodiac_rules(int(q.get("year", 2026))))
        else:
            self._json({"detail": "not found"}, 404)

    def do_POST(self):
        u = urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        try:
            req = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self._json({"detail": "invalid JSON"}, 400)
        if u.path == "/api/analyze":
            try:
                self._json(core.analyze(req.get("surname", ""), req.get("given", ""),
                                        int(req.get("year", 2026)),
                                        bool(req.get("use_modern", False))))
            except ValueError as e:
                self._json({"detail": str(e)}, 400)
        else:
            self._json({"detail": "not found"}, 404)

    def log_message(self, fmt, *args):
        pass  # 安靜模式


if __name__ == "__main__":
    print(f"寶寶取名助手 → http://localhost:{PORT}")
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
