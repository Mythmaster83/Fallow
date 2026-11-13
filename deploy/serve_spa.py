"""Serve dist/ like Cloudflare does: unknown paths fall back to index.html.

Usage: python deploy/serve_spa.py [port] [dir]
"""

import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class SpaHandler(SimpleHTTPRequestHandler):
    def send_head(self):  # type: ignore[override]
        path = Path(self.translate_path(self.path))
        if not path.exists():
            self.path = "/index.html"
        return super().send_head()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8502
    root = sys.argv[2] if len(sys.argv) > 2 else "dist"
    ThreadingHTTPServer(("", port), partial(SpaHandler, directory=root)).serve_forever()
