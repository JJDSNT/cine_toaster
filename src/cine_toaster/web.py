from __future__ import annotations

import json
import mimetypes
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .index import ProjectIndex


ASSET_ROOT = Path(__file__).with_name("web_assets")
RANGE_PATTERN = re.compile(r"bytes=(\d*)-(\d*)")


def _safe_project_path(root: Path, relative_path: str) -> Path | None:
    try:
        candidate = (root / unquote(relative_path)).resolve()
        candidate.relative_to(root)
    except (OSError, ValueError):
        return None
    return candidate


class ProjectBrowserHandler(BaseHTTPRequestHandler):
    server_version = "CineToaster/0.1"

    @property
    def project_index(self) -> ProjectIndex:
        return self.server.project_index  # type: ignore[attr-defined]

    @property
    def project_root(self) -> Path:
        return self.server.project_root  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: object) -> None:
        print(f"[browser] {self.address_string()} - {format % args}")

    def _send_json(self, value: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _send_static(self, name: str) -> None:
        path = ASSET_ROOT / name
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        payload = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(payload)

    def _send_project_file(self, relative_path: str) -> None:
        path = _safe_project_path(self.project_root, relative_path)
        if path is None or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        size = path.stat().st_size
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        range_header = self.headers.get("Range")
        start, end = 0, max(0, size - 1)
        status = HTTPStatus.OK

        if range_header and (match := RANGE_PATTERN.fullmatch(range_header.strip())):
            raw_start, raw_end = match.groups()
            if raw_start:
                start = int(raw_start)
                end = int(raw_end) if raw_end else end
            elif raw_end:
                suffix_length = int(raw_end)
                start = max(0, size - suffix_length)
            if start >= size or end < start:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
            end = min(end, size - 1)
            status = HTTPStatus.PARTIAL_CONTENT

        length = 0 if size == 0 else end - start + 1
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        if status == HTTPStatus.PARTIAL_CONTENT:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Cache-Control", "private, max-age=60")
        self.end_headers()

        if self.command == "HEAD" or length == 0:
            return
        with path.open("rb") as handle:
            handle.seek(start)
            remaining = length
            while remaining:
                chunk = handle.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def _handle_api(self, parsed) -> None:
        query = parse_qs(parsed.query)
        if parsed.path == "/api/project":
            self._send_json(self.project_index.summary().public_dict())
            return

        if parsed.path == "/api/items":
            parent_id = query.get("parent", [self.project_index.summary().id])[0]
            self._send_json(
                [item.public_dict() for item in self.project_index.children(parent_id)]
            )
            return

        if parsed.path == "/api/item":
            item_id = query.get("id", [""])[0]
            item = self.project_index.get(item_id)
            if item is None:
                self._send_json({"error": "Item not found"}, HTTPStatus.NOT_FOUND)
                return
            self._send_json(
                {
                    **item.public_dict(),
                    "ancestors": [
                        ancestor.public_dict()
                        for ancestor in self.project_index.ancestors(item)
                    ],
                }
            )
            return

        if parsed.path == "/api/search":
            text = query.get("q", [""])[0]
            kind = query.get("kind", [None])[0]
            self._send_json(self.project_index.search(text, kind=kind, limit=200))
            return

        self._send_json({"error": "Unknown endpoint"}, HTTPStatus.NOT_FOUND)

    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_static("index.html")
        elif parsed.path == "/static/app.js":
            self._send_static("app.js")
        elif parsed.path == "/static/style.css":
            self._send_static("style.css")
        elif parsed.path.startswith("/api/"):
            self._handle_api(parsed)
        elif parsed.path.startswith("/media/"):
            self._send_project_file(parsed.path.removeprefix("/media/"))
        else:
            self.send_error(HTTPStatus.NOT_FOUND)


def serve_project(
    root: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8787,
) -> None:
    project_index = ProjectIndex(root)
    server = ThreadingHTTPServer((host, port), ProjectBrowserHandler)
    server.project_index = project_index  # type: ignore[attr-defined]
    server.project_root = root.expanduser().resolve()  # type: ignore[attr-defined]
    print(f"Cine Toaster browsing {server.project_root}")
    print(f"Open http://{host}:{port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping browser.")
    finally:
        server.server_close()

