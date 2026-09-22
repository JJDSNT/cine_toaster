from __future__ import annotations

import json
import mimetypes
import re
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .commands import dispatch
from .errors import CineToasterError, ValidationError
from .events import read_events, tail_events
from .index import ProjectIndex
from .knowledge import coverage, load_practices, load_providers
from .project import ProjectFormatError, load_production, load_scene, writing_room
from .transitions import list_transitions, public_transition, transition_asset_path


MAX_COMMAND_BODY_BYTES = 64 * 1024
STREAM_POLL_SECONDS = 0.5
STREAM_MAX_SECONDS = 300


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
        print(f"[control-room] {self.address_string()} - {format % args}")

    def _send_json(self, value: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _send_static(self, name: str) -> None:
        candidate = _safe_project_path(ASSET_ROOT, name)
        path = candidate if candidate is not None else ASSET_ROOT / name
        if candidate is None or not path.is_file():
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

    def _send_file(self, path: Path | None) -> None:
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

    def _send_project_file(self, relative_path: str) -> None:
        self._send_file(_safe_project_path(self.project_root, relative_path))

    def _send_transition_file(self, relative_path: str) -> None:
        parts = relative_path.split("/", 1)
        if len(parts) != 2:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        transition_id, filename = map(unquote, parts)
        self._send_file(
            transition_asset_path(transition_id, filename, self.project_root)
        )

    def _read_json_body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValidationError("Content-Length must be an integer") from error
        if length <= 0:
            raise ValidationError("A command needs a JSON body")
        if length > MAX_COMMAND_BODY_BYTES:
            raise ValidationError("Command body is too large")
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValidationError(f"Command body is not valid JSON: {error}") from error
        if not isinstance(payload, dict):
            raise ValidationError("A command body must be a JSON object")
        return payload

    def _handle_command(self) -> None:
        """Run one application command.

        The handler translates HTTP into a command call and back. It contains no
        domain rules of its own, so the CLI and the browser cannot diverge.
        """

        try:
            payload = self._read_json_body()
            command_type = str(payload.get("command", "")).strip()
            if not command_type:
                raise ValidationError("A command name is required")
            result = dispatch(self.project_root, command_type, payload)
        except CineToasterError as error:
            self._send_json(error.public_dict(), HTTPStatus(error.http_status))
            return
        except ProjectFormatError as error:
            self._send_json(
                {"error": {"code": "invalid_project", "message": str(error)}},
                HTTPStatus.UNPROCESSABLE_ENTITY,
            )
            return
        self._send_json(result.public_dict())

    def _stream_events(self, parsed) -> None:
        """Push committed events to the browser so the board stays live.

        The log is tailed from disk rather than from memory, so a selection made
        from the CLI in another terminal shows up in the open interface too.
        """

        query = parse_qs(parsed.query)
        try:
            offset = int(query.get("offset", ["-1"])[0])
        except ValueError:
            offset = -1
        if offset < 0:
            _, offset = read_events(self.project_root)

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()

        deadline = time.monotonic() + STREAM_MAX_SECONDS
        try:
            self.wfile.write(b": connected\n\n")
            self.wfile.flush()
            while time.monotonic() < deadline:
                events, offset = read_events(self.project_root, offset=offset)
                for event in events:
                    payload = json.dumps(event, ensure_ascii=False)
                    self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                if events:
                    self.wfile.flush()
                else:
                    self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
                time.sleep(STREAM_POLL_SECONDS)
        except (BrokenPipeError, ConnectionResetError):
            return

    def _handle_api(self, parsed) -> None:
        query = parse_qs(parsed.query)
        if parsed.path == "/api/transitions":
            self._send_json(
                [
                    public_transition(transition)
                    for transition in list_transitions(self.project_root)
                ]
            )
            return

        if parsed.path == "/api/transition":
            transition_id = query.get("id", [""])[0]
            transition = next(
                (
                    item
                    for item in list_transitions(self.project_root)
                    if item["id"] == transition_id
                ),
                None,
            )
            if transition is None:
                self._send_json({"error": "Transition not found"}, HTTPStatus.NOT_FOUND)
                return
            self._send_json(public_transition(transition))
            return

        if parsed.path == "/api/production":
            try:
                self._send_json(load_production(self.project_root))
            except FileNotFoundError:
                self._send_json(
                    {"error": "This directory has no project.toml operational manifest"},
                    HTTPStatus.NOT_FOUND,
                )
            except ProjectFormatError as error:
                self._send_json({"error": str(error)}, HTTPStatus.UNPROCESSABLE_ENTITY)
            return

        if parsed.path == "/api/scene":
            scene_id = query.get("id", [""])[0]
            try:
                scene = load_scene(self.project_root, scene_id)
            except (FileNotFoundError, ProjectFormatError) as error:
                self._send_json({"error": str(error)}, HTTPStatus.NOT_FOUND)
                return
            if scene is None:
                self._send_json({"error": "Scene not found"}, HTTPStatus.NOT_FOUND)
                return
            self._send_json(scene)
            return

        if parsed.path == "/api/events":
            try:
                limit = int(query.get("limit", ["50"])[0])
            except ValueError:
                limit = 50
            self._send_json(tail_events(self.project_root, limit=limit))
            return

        if parsed.path == "/api/findings":
            try:
                production = load_production(self.project_root)
            except (FileNotFoundError, ProjectFormatError) as error:
                self._send_json({"error": str(error)}, HTTPStatus.NOT_FOUND)
                return
            self._send_json(
                [
                    {**finding, "scene_title": scene["title"]}
                    for scene in production["scenes"]
                    for finding in scene["findings"]
                ]
            )
            return

        if parsed.path == "/api/writing":
            self._send_json(writing_room(self.project_root))
            return

        if parsed.path == "/api/knowledge":
            root = self.project_root
            self._send_json(
                {
                    "coverage": coverage(root).public_dict(),
                    "practices": [item.public_dict() for item in load_practices(root)],
                    "providers": [item.public_dict() for item in load_providers(root)],
                }
            )
            return

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
        if urlparse(self.path).path == "/api/events/stream":
            # A HEAD request must not open a long-lived stream.
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.end_headers()
            return
        self.do_GET()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/commands":
            self._handle_command()
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_static("index.html")
        elif parsed.path.startswith("/static/"):
            self._send_static(parsed.path.removeprefix("/static/"))
        elif parsed.path == "/api/events/stream":
            self._stream_events(parsed)
        elif parsed.path.startswith("/api/"):
            self._handle_api(parsed)
        elif parsed.path.startswith("/media/"):
            self._send_project_file(parsed.path.removeprefix("/media/"))
        elif parsed.path.startswith("/transition-assets/"):
            self._send_transition_file(parsed.path.removeprefix("/transition-assets/"))
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
        print("\nStopping control room.")
    finally:
        server.server_close()
