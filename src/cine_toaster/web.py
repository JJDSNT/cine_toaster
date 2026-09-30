from __future__ import annotations

import json
import mimetypes
import os
import re
import subprocess
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .commands import dispatch
from .errors import CineToasterError, ResourceNotFoundError, ValidationError
from .events import read_events, tail_events
from .index import ProjectIndex
from .knowledge import coverage, load_practices, load_providers
from .blocking import blocking_frame, previs, public_frame, render_svg
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

    def _send_app(self, name: str) -> None:
        """The React app -- canvas and screenplay editor -- built by `make ui` (ADR 0015)."""

        root = ASSET_ROOT / "app"
        if not (root / "index.html").is_file():
            payload = (b"<!doctype html><meta charset=utf-8><body style='font:14px system-ui;padding:2em'>"
                       b"<h1>The canvas and editor are not built</h1><p>Run <code>make ui</code> (needs Node 20+). "
                       b"<code>toast doctor</code> reports it.</p>")
            self.send_response(HTTPStatus.NOT_FOUND)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        candidate = _safe_project_path(root, name)
        if candidate is None or not candidate.is_file():
            candidate = root / "index.html"  # client-side routes fall back to the app
        payload = candidate.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(candidate.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-cache" if candidate.name == "index.html" else "public, max-age=31536000, immutable")
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

    def _read_json_body(self, limit: int | None = None) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValidationError("Content-Length must be an integer") from error
        if length <= 0:
            raise ValidationError("A command needs a JSON body")
        if length > (limit or MAX_COMMAND_BODY_BYTES):
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
            from .commands import WORKFLOW_COMMANDS

            if command_type in WORKFLOW_COMMANDS:
                self.job_manager  # a workflow's jobs run in this runtime  # noqa: B018
            result = dispatch(self.project_root, command_type, payload)
            forget_production(self.project_root)
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
        if parsed.path == "/api/locations":
            # The production's sets (SPEC-0010): each with its plan drawn in the Core's terms,
            # the scenes shot there, and where it stands against the backlot.
            from .locations import status as backlot_status

            self._send_json(locations_view(self.project_root, cached_production(self.project_root),
                                           {item["id"]: item for item in backlot_status(self.project_root)}))
            return
        if parsed.path == "/api/titles":
            # The title catalog (CT-0031), with whether each item's engine can run here.
            from .titles import engine_missing, list_titles

            self._send_json([{**{key: item[key] for key in ("id", "name", "category", "says", "energy", "use_when",
                                                             "avoid_when", "params", "engine", "effect", "origin")},
                              "unavailable": engine_missing(item["engine"])} for item in list_titles(self.project_root)])
            return
        if parsed.path == "/api/title-preview":
            # One frame, drawn by the item's own engine; cached, since Blender takes seconds.
            from .titles import cached_preview, list_titles

            wanted = query.get("id", [""])[0]
            item = next((entry for entry in list_titles(self.project_root) if entry["id"] == wanted), None)
            if item is None:
                self._send_json({"error": {"code": "not_found", "message": f"No title {wanted!r}"}}, HTTPStatus.NOT_FOUND)
                return
            try:
                path = cached_preview(item, text=query.get("text", [""])[0][:80], root=self.project_root)
            except (ValidationError, OSError, subprocess.CalledProcessError) as error:
                self._send_json({"error": {"code": "unavailable", "message": getattr(error, "message", str(error))}},
                                HTTPStatus.SERVICE_UNAVAILABLE)
                return
            self._send_file(path)
            return
        if parsed.path == "/api/camera-move-preview":
            # A move on the preview stage, as blocking frames (CT-0027): derived, never stored.
            from .camera_moves import list_moves, preview

            wanted = query.get("id", [""])[0]
            move = next((item for item in list_moves(self.project_root) if item["id"] == wanted), None)
            if move is None:
                self._send_json({"error": {"code": "not_found", "message": f"No camera move {wanted!r}"}},
                                HTTPStatus.NOT_FOUND)
                return
            self._send_json(preview(move))
            return
        if parsed.path == "/api/camera-moves":
            # The camera-move catalog (CT-0027): built in, external, the production's.
            from .camera_moves import list_moves

            self._send_json(list_moves(self.project_root))
            return
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
                self._send_json(cached_production(self.project_root))
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
                scene = self._scene(scene_id)
            except (FileNotFoundError, ProjectFormatError) as error:
                self._send_json({"error": str(error)}, HTTPStatus.NOT_FOUND)
                return
            if scene is None:
                self._send_json({"error": "Scene not found"}, HTTPStatus.NOT_FOUND)
                return
            self._send_json(scene)
            return

        if parsed.path in ("/api/brief", "/api/brief-review"):
            # A scene's generation brief, derived from its records (plan step 4),
            # and the review project for one shot's local take.
            from .brief import production_brief, take_review

            try:
                found = production_brief(self.project_root, query.get("scene", [""])[0], cached_production(self.project_root))
            except (FileNotFoundError, ProjectFormatError) as error:
                self._send_json({"error": str(error)}, HTTPStatus.NOT_FOUND)
                return
            if found is None:
                self._send_json({"error": "Scene not found"}, HTTPStatus.NOT_FOUND)
                return
            scene, brief = found
            if parsed.path == "/api/brief":
                self._send_json(brief.public_dict())
                return
            review = take_review(scene, brief, query.get("shot", [""])[0], query.get("take", [""])[0] or None)
            if review is None:
                self._send_json({"error": "That shot has no take with a video"}, HTTPStatus.NOT_FOUND)
                return
            self._send_json(review)
            return

        if parsed.path in ("/api/pictures", "/api/picture-plan"):
            # Master pictures made by editing a source with the cast (CT-0037).
            from . import spend
            from .jobs import _picture_plan
            from .pictures import scene_pictures

            scene_id = query.get("scene", [""])[0]
            try:
                if parsed.path == "/api/pictures":
                    production = cached_production(self.project_root)
                    scene = next((item for item in production["scenes"] if item["id"] == scene_id), None)
                    if scene is None:
                        self._send_json({"error": "Scene not found"}, HTTPStatus.NOT_FOUND)
                        return
                    self._send_json(scene_pictures(self.project_root, scene))
                    return
                plan, _, _ = _picture_plan(self.project_root, {"scene": scene_id, "shot": query.get("shot", [""])[0]})
            except CineToasterError as error:
                self._send_json(error.public_dict(), HTTPStatus(error.http_status))
                return
            ledger = spend.load()
            self._send_json({**plan.public_dict(self.project_root), "spent_usd": spend.spent(ledger),
                             "limit_usd": float(ledger.get("limit_usd") or 0)})
            return

        if parsed.path == "/api/generation-plan":
            # What a block's generation would send and cost, before anyone pays (CT-0037).
            from . import spend
            from .generation import hourly_rate, plan_block

            try:
                plan = plan_block(self.project_root, cached_production(self.project_root),
                                  query.get("scene", [""])[0], query.get("block", [""])[0],
                                  rate=hourly_rate(self.project_root, os.environ.get("RUNPOD_LTX_ENDPOINT_ID", "")))
            except CineToasterError as error:
                self._send_json(error.public_dict(), HTTPStatus(error.http_status))
                return
            ledger = spend.load()
            self._send_json({**plan.public_dict(self.project_root), "spent_usd": spend.spent(ledger),
                             "limit_usd": float(ledger.get("limit_usd") or 0)})
            return

        if parsed.path == "/api/budget":
            # What paid generation may spend and has spent (CT-0037); read-only here.
            from . import spend

            ledger = spend.load()
            self._send_json({"limit_usd": float(ledger.get("limit_usd") or 0), "spent_usd": spend.spent(ledger),
                             "recent": ledger.get("entries", [])[-5:]})
            return

        if parsed.path == "/api/screenplay":
            from .screenplay_edit import screenplay_files

            try:
                self._send_json(screenplay_files(self.project_root, cached_production(self.project_root)))
            except (FileNotFoundError, ProjectFormatError) as error:
                self._send_json({"error": str(error)}, HTTPStatus.NOT_FOUND)
            return

        if parsed.path == "/api/graph":
            # The production canvas: records as nodes and edges, no positions (plan step 7).
            from .graph import production_graph

            try:
                self._send_json(production_graph(cached_production(self.project_root), self.project_root))
            except (FileNotFoundError, ProjectFormatError) as error:
                self._send_json({"error": str(error)}, HTTPStatus.NOT_FOUND)
            return

        if parsed.path == "/api/previs":
            # The shot as a light animatic, sampled from the blocking frame
            # over its duration (CT-0029). Derived on request, never stored.
            try:
                scene = self._scene(query.get("scene", [""])[0])
            except (FileNotFoundError, ProjectFormatError) as error:
                self._send_json({"error": str(error)}, HTTPStatus.NOT_FOUND)
                return
            shot_id = query.get("shot", [""])[0]
            shot = next((item for item in (scene or {}).get("shots", []) if item["id"] == shot_id), None)
            result = previs(scene, shot) if shot else None
            if result is None:
                self._send_json({"error": "No camera pose for that shot"}, HTTPStatus.NOT_FOUND)
                return
            self._send_json(result)
            return

        if parsed.path == "/api/blocking-frame":
            # What a shot's camera sees at its start or end, computed from the
            # scene geometry (CT-0025). Derived on every request, never stored.
            scene_id = query.get("scene", [""])[0]
            shot_id = query.get("shot", [""])[0]
            at = query.get("at", ["start"])[0]
            try:
                scene = self._scene(scene_id)
            except (FileNotFoundError, ProjectFormatError) as error:
                self._send_json({"error": str(error)}, HTTPStatus.NOT_FOUND)
                return
            shot = next((item for item in (scene or {}).get("shots", []) if item["id"] == shot_id), None)
            try:
                frame = blocking_frame(scene, shot, at) if shot else None
            except ValueError as error:
                self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
                return
            if frame is None:
                self._send_json({"error": "No camera pose for that shot"}, HTTPStatus.NOT_FOUND)
                return
            if query.get("format", [""])[0] == "json":
                self._send_json(public_frame(frame))
                return
            payload = render_svg(frame).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)
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
                production = cached_production(self.project_root)
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

    def _proxy_assistant(self, parsed) -> bool:
        """`/api/copilotkit` goes to the Copilot Runtime when the assistant is on (ADR 0018)."""

        from .assistant_host import PROXY_PREFIX, proxy

        if not parsed.path.startswith(PROXY_PREFIX):
            return False
        host = getattr(self.server, "assistant", None)
        if host is None:
            self._send_json({"error": {"code": "assistant_off",
                                       "message": "The assistant is off; start the runtime with --assistant."}},
                            HTTPStatus.SERVICE_UNAVAILABLE)
            return True
        proxy(self, host.copilot_port)
        return True

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if self._proxy_assistant(parsed):
            return
        if parsed.path == "/api/commands":
            self._handle_command()
            return
        if parsed.path == "/api/jobs" or parsed.path.startswith("/api/jobs/"):
            self._handle_job_post(parsed)
            return
        if parsed.path == "/api/screenplay":
            self._handle_screenplay_edit()
            return
        if parsed.path == "/api/sequence-review":
            from .commands import Actor, review_sequence_version

            try:
                payload = self._read_json_body()
                result = review_sequence_version(
                    self.project_root, sequence_id=str(payload.get("sequence_id", "")),
                    version_id=str(payload.get("version_id", "")), verdict=str(payload.get("verdict", "")),
                    actor=Actor(id=str((payload.get("actor") or {}).get("id") or "control-room")),
                    note=str(payload.get("note") or ""),
                )
                forget_production(self.project_root)
            except CineToasterError as error:
                self._send_json(error.public_dict(), HTTPStatus(error.http_status))
                return
            self._send_json(result)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def _handle_screenplay_edit(self) -> None:
        """A person's edit to one screenplay file (ADR 0016)."""

        from .screenplay_edit import MAX_SCREENPLAY_BYTES, edit_screenplay

        try:
            payload = self._read_json_body(limit=MAX_SCREENPLAY_BYTES * 2)
            actor = payload.get("actor") or {}
            result = edit_screenplay(
                self.project_root,
                str(payload.get("path", "")),
                payload.get("text"),
                str(payload.get("revision", "")),
                actor=str(actor.get("id") if isinstance(actor, dict) else actor or "unknown"),
                rationale=str(payload.get("rationale") or ""),
            )
            forget_production(self.project_root)
        except CineToasterError as error:
            self._send_json(error.public_dict(), HTTPStatus(error.http_status))
            return
        self._send_json(result)

    # --- jobs (SPEC-0008) ---------------------------------------------------

    @property
    def job_manager(self):
        """The runtime's Job Manager: one per server, created on first use."""

        from .jobs import JobManager

        server = self.server
        with _JOB_MANAGER_LOCK:
            if getattr(server, "job_manager", None) is None:
                from .workflows import attach

                server.job_manager = JobManager()  # type: ignore[attr-defined]
                attach(server.job_manager)
        return server.job_manager  # type: ignore[attr-defined]

    def _scene(self, scene_id: str) -> dict | None:
        production = cached_production(self.project_root)
        return next((scene for scene in production["scenes"] if scene["id"] == scene_id), None)

    def _project_id(self) -> str:
        server = self.server
        if getattr(server, "project_id", None) is None:
            server.project_id = load_production(self.project_root)["id"]  # type: ignore[attr-defined]
        return server.project_id  # type: ignore[attr-defined]

    def _handle_job_get(self, parsed) -> None:
        from .jobs import public_job

        try:
            if parsed.path == "/api/jobs":
                self._send_json([public_job(job) for job in self.job_manager.list(project_id=self._project_id(), limit=30)])
                return
            job = self.job_manager.get(parsed.path.removeprefix("/api/jobs/"))
            if job["project_id"] != self._project_id():
                raise ResourceNotFoundError("No such job in this production")
            self._send_json(public_job(job))
        except CineToasterError as error:
            self._send_json(error.public_dict(), HTTPStatus(error.http_status))

    def _handle_job_post(self, parsed) -> None:
        from .jobs import public_job

        try:
            manager = self.job_manager
            if parsed.path == "/api/jobs":
                payload = self._read_json_body()
                job = manager.submit(str(payload.get("kind", "")), self.project_root, payload.get("params") or {})
                self._send_json(public_job(job), HTTPStatus.ACCEPTED)
                return
            job_id, _, action = parsed.path.removeprefix("/api/jobs/").partition("/")
            if manager.get(job_id)["project_id"] != self._project_id():
                raise ResourceNotFoundError("No such job in this production")
            if action == "cancel":
                job = manager.cancel(job_id)
            elif action == "retry":
                job = manager.retry(job_id)
            elif action == "adopt":
                length = int(self.headers.get("Content-Length", "0") or 0)
                payload = self._read_json_body() if length else {}
                job = manager.adopt(job_id, overwrite=bool(payload.get("overwrite")))
                forget_production(self.project_root)
            else:
                raise ValidationError(f"Unknown job action {action!r}", available=["cancel", "retry", "adopt"])
            self._send_json(public_job(job))
        except CineToasterError as error:
            self._send_json(error.public_dict(), HTTPStatus(error.http_status))

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if self._proxy_assistant(parsed):
            return
        if parsed.path == "/":
            self._send_static("index.html")
        elif parsed.path in ("/canvas", "/canvas/") or parsed.path.startswith("/canvas/"):
            # The canvas moved into the app with the screenplay editor (ADR 0016).
            self.send_response(HTTPStatus.MOVED_PERMANENTLY)
            self.send_header("Location", "/app/")
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif parsed.path in ("/app", "/app/") or parsed.path.startswith("/app/"):
            self._send_app(parsed.path.removeprefix("/app").lstrip("/") or "index.html")
        elif parsed.path.startswith("/static/"):
            self._send_static(parsed.path.removeprefix("/static/"))
        elif parsed.path == "/api/events/stream":
            self._stream_events(parsed)
        elif parsed.path == "/api/jobs" or parsed.path.startswith("/api/jobs/"):
            self._handle_job_get(parsed)
        elif parsed.path.startswith("/api/"):
            self._handle_api(parsed)
        elif parsed.path.startswith("/media/"):
            self._send_project_file(parsed.path.removeprefix("/media/"))
        elif parsed.path.startswith("/transition-assets/"):
            self._send_transition_file(parsed.path.removeprefix("/transition-assets/"))
        else:
            self.send_error(HTTPStatus.NOT_FOUND)


_JOB_MANAGER_LOCK = threading.Lock()

#: How long one loaded production answers requests. A canvas asks for a
#: hundred thumbnails at once; each used to reload the whole production. A
#: command clears it at once, and edits made by hand show within this window.
PRODUCTION_TTL_SECONDS = 2.0
_PRODUCTION_CACHE: dict[Path, tuple[float, dict]] = {}
_PRODUCTION_LOCK = threading.Lock()


def locations_view(root: Path, production: dict, backlot: dict) -> list[dict]:
    from .errors import ValidationError as _Invalid
    from .geometry import parse_geometry
    from .project import _geometry_document

    found = []
    for location_id, location in sorted((production.get("locations") or {}).items()):
        geography = {key: location[key] for key in ("room", "marks", "cameras", "set_pieces") if location.get(key)}
        try:
            plan = parse_geometry(_geometry_document(geography)).public_dict() if geography else None
        except _Invalid as error:
            plan = {"error": error.message}
        found.append({**location, "plan": plan, "backlot": backlot.get(location_id)})
    return found


def cached_production(root: Path) -> dict:
    """The loaded production, shared by a burst of requests (read-only for callers)."""

    with _PRODUCTION_LOCK:
        entry = _PRODUCTION_CACHE.get(root)
        if entry and time.monotonic() - entry[0] < PRODUCTION_TTL_SECONDS:
            return entry[1]
        production = load_production(root)
        _PRODUCTION_CACHE[root] = (time.monotonic(), production)
        return production


def forget_production(root: Path) -> None:
    with _PRODUCTION_LOCK:
        _PRODUCTION_CACHE.pop(root, None)


def serve_project(
    root: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8787,
    assistant: bool = False,
) -> None:
    project_index = ProjectIndex(root)
    server = ThreadingHTTPServer((host, port), ProjectBrowserHandler)
    server.project_index = project_index  # type: ignore[attr-defined]
    server.project_root = root.expanduser().resolve()  # type: ignore[attr-defined]
    # The runtime owns its jobs, so they outlive any page that started them;
    # starting it reconciles work an earlier runtime left unfinished.
    from .jobs import JobManager

    from .workflows import attach

    server.job_manager = JobManager()  # type: ignore[attr-defined]
    # Workflows move when their jobs finish, inside the runtime that runs them (SPEC-0009).
    attach(server.job_manager)
    for job in server.job_manager.reconciled:
        print(f"Job {job['id']} ({job['kind']}) was interrupted: {job['message']}")
    server.assistant = None  # type: ignore[attr-defined]
    if assistant:
        # ADR 0018: the assistant and its Copilot Runtime, beside the control room.
        from .assistant_host import AssistantHost, unavailable_reason

        reason = unavailable_reason()
        if reason:
            print(f"Assistant not started: {reason}")
        else:
            server.assistant = AssistantHost(f"http://127.0.0.1:{port}", port + 1, port + 2)  # type: ignore[attr-defined]
            server.assistant.start()  # type: ignore[attr-defined]
            print(f"Assistant on (agent :{port + 1}, Copilot Runtime :{port + 2}); open /app/ to talk to it.")
    print(f"Cine Toaster browsing {server.project_root}")
    print(f"Open http://{host}:{port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping control room.")
    finally:
        server.server_close()
        server.job_manager.shutdown(wait=False)
        if server.assistant is not None:  # type: ignore[attr-defined]
            server.assistant.stop()  # type: ignore[attr-defined]
