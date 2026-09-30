"""Cine Toaster as an MCP server: Claude Code working on a film through the product (CT-0045).

A person who works with Claude Code, as SINGULAR was made, connects it here
instead of letting it edit files and write scripts of its own. Every tool is
a query or one of the application's commands, the same the control room, the
CLI and the assistant use, so what Claude Code does lands with records,
lineage, revisions and the budget ceiling:

- reads, which change nothing;
- decisions over the breakdown (cuts, references, voices in the cut),
  recorded with the actor `claude-code` (an agent);
- workflows and jobs (assemble, slice, revoice), and paid generation only
  with a spending cap the caller states and the budget allows.

What stays a person's is not offered: approving or refusing a picture
(gates, SPEC-0009), choosing a take, approving the storyboard. Authored
files (breakdowns, the screenplay) are not written by any tool here.

The server runs in its own process, on one project, over stdio:

    toast mcp <project> [--env-file ~/confyui/.env]
    claude mcp add cine-toaster -- toast mcp <project>
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .errors import CineToasterError, ValidationError

ACTOR = {"id": "claude-code", "kind": "agent"}

INSTRUCTIONS = (
    "Cine Toaster holds a film as files: breakdowns, a screenplay, cast sheets, takes. Work on it through these "
    "tools, not by editing its files: every change here is a recorded decision with a revision. Start with "
    "film_overview, then read_scene or read_shot. Cuts, references and voices are decisions over the breakdown; "
    "workflows and jobs make pictures, video, takes and versions. Paid generation needs max_usd at or above the "
    "estimate plan_generation gives, and the budget ceiling holds whatever you pass. Approving or refusing a "
    "picture, choosing a take and approving the storyboard are the director's: explain the candidates, never "
    "decide. A long job returns an id: follow it with wait_for_job."
)


class LocalRuntime:
    """The runtime in this process, with the reading surface the assistant's reads expect."""

    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()

    def production(self) -> dict[str, Any]:
        from .project import load_production

        return load_production(self.root)

    def scene(self, scene_id: str) -> dict[str, Any]:
        scene = next((item for item in self.production()["scenes"] if item["id"] == scene_id), None)
        if scene is None:
            raise ValidationError(f"No scene {scene_id!r}")
        return scene

    def screenplay(self) -> dict[str, Any]:
        from .screenplay_edit import screenplay_files

        return screenplay_files(self.root, self.production())

    def budget(self) -> dict[str, Any]:
        from . import spend

        ledger = spend.load()
        return {"limit_usd": float(ledger.get("limit_usd") or 0), "spent_usd": spend.spent(ledger),
                "recent": ledger.get("entries", [])[-5:]}

    def command(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        from .commands import dispatch

        return dispatch(self.root, name, {"actor": ACTOR, **payload}).public_dict()


def _answer(call):
    """A refusal is an answer the model can act on, not a crash."""

    try:
        return call()
    except CineToasterError as error:
        return {"refused": error.message, **({"details": error.details} if getattr(error, "details", None) else {})}


def build(root: Path, manager=None):
    """The MCP server for one project. `manager` is the job manager (one is made if omitted)."""

    from mcp.server.mcpserver import MCPServer
    from mcp_types import ToolAnnotations

    from . import spend
    from .agents.reads import overview, read
    from .jobs import JobManager, public_job
    from .workflows import attach

    runtime = LocalRuntime(root)
    jobs = manager or JobManager()
    attach(jobs)  # a workflow started here moves on when its jobs finish
    server = MCPServer("cine-toaster", instructions=INSTRUCTIONS)
    reading = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
    deciding = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
    working = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False)
    paying = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True)

    # --- reads -------------------------------------------------------------------

    @server.tool(annotations=reading)
    def film_overview() -> str:
        """The whole film: scenes with shots, chosen takes, findings, waiting gates, runs; sequences, cast, budget."""
        return overview(runtime.production(), runtime.budget())

    @server.tool(annotations=reading)
    def read_scene(scene: str) -> str:
        """One scene's records: blocks, workflow runs, gates, pictures, findings, location."""
        return read(runtime, "scene", {"scene": scene})

    @server.tool(annotations=reading)
    def read_shot(scene: str, shot: str) -> str:
        """One shot: action, camera, lines, master picture, and its takes with where they came from."""
        return read(runtime, "shot", {"scene": scene, "shot": shot})

    @server.tool(annotations=reading)
    def read_cast() -> str:
        """Every cast member: what the sheet decides, voice, variants, how many scenes."""
        return read(runtime, "cast", {})

    @server.tool(annotations=reading)
    def search_screenplay(text: str) -> str:
        """Screenplay lines containing a text."""
        return read(runtime, "screenplay", {"text": text})

    @server.tool(annotations=reading)
    def read_budget() -> str:
        """The generation budget: the ceiling, what is spent, the latest entries."""
        return read(runtime, "budget", {})

    @server.tool(annotations=reading)
    def check_scene(scene: str) -> list[dict[str, Any]] | dict[str, Any]:
        """What the checks find in a scene: continuity, cuts, moves, set pieces, plates (code, severity, message)."""
        return _answer(lambda: [{key: finding.get(key) for key in ("code", "severity", "message", "shots")}
                                for finding in runtime.scene(scene).get("findings") or []])

    @server.tool(annotations=reading)
    def list_locations() -> list[dict[str, Any]]:
        """The production's sets: room, cameras, marks, set pieces, plates, and the scenes shot there."""
        from .web import locations_view

        return [{key: item.get(key) for key in ("id", "label", "description", "plan", "references", "appearances")}
                for item in locations_view(runtime.root, runtime.production(), {})]

    @server.tool(annotations=reading)
    def list_camera_moves() -> list[dict[str, Any]]:
        """The camera-move catalog: a shot names one with `move: {id: …}` in its breakdown."""
        from .camera_moves import list_moves

        return [{"id": move["id"], "name": move["name"], "category": move["category"], "says": move["says"],
                 "implies": move["implies"]} for move in list_moves(runtime.root)]

    @server.tool(annotations=reading)
    def plan_generation(scene: str, target: str, seed: int = 1) -> dict[str, Any]:
        """What generating a block (its id) or a lone shot (P7) would send and cost. Nothing is sent or paid."""

        def plan() -> dict[str, Any]:
            planned, _single = _generation_plan(runtime, scene, target, seed)
            return {**planned.public_dict(runtime.root), "spent_usd": spend.spent(),
                    "limit_usd": float(spend.load().get("limit_usd") or 0)}

        return _answer(plan)

    @server.tool(annotations=reading)
    def plan_picture(scene: str, shot: str, seed: int = 1) -> dict[str, Any]:
        """What a master picture edit (derive) would use and cost. Nothing is sent or paid."""
        from .jobs import _picture_plan

        return _answer(lambda: _picture_plan(runtime.root, {"scene": scene, "shot": shot, "seed": seed})[0]
                       .public_dict(runtime.root))

    # --- decisions over the breakdown ---------------------------------------------------

    @server.tool(annotations=deciding)
    def set_cut(scene: str, shot: str, cut_type: str, reason: str = "", transition: str = "",
                why: str = "") -> dict[str, Any]:
        """Decide the cut into `shot` (hard, match, action, j, l, smash, jump, continuation), optionally with a catalog transition."""
        cut = {"type": cut_type, "reason": reason, "transition": {"id": transition} if transition else None}
        return _answer(lambda: runtime.command("set_cut", {"scene_id": scene, "shot_id": shot, "cut": cut,
                                                            "rationale": why}))

    @server.tool(annotations=deciding)
    def set_cuts(scene: str, cuts: list[dict[str, Any]], why: str = "") -> dict[str, Any]:
        """Decide several cuts of one scene together, all or none: cuts = [{shot, cut_type, reason?, transition?}]."""
        payload = [{"shot": item.get("shot"), "cut": {
            "type": item.get("cut_type") or item.get("type") or "hard", "reason": item.get("reason", ""),
            "transition": {"id": item["transition"]} if item.get("transition") else None}} for item in cuts]
        return _answer(lambda: runtime.command("set_cuts", {"scene_id": scene, "cuts": payload, "rationale": why}))

    @server.tool(annotations=deciding)
    def clear_cut(scene: str, shot: str, why: str = "") -> dict[str, Any]:
        """Return the cut into `shot` to what the breakdown says."""
        return _answer(lambda: runtime.command("clear_cut", {"scene_id": scene, "shot_id": shot, "rationale": why}))

    @server.tool(annotations=deciding)
    def set_reference(scene: str, shot: str, made_from: str = "", faces: list[str] | None = None,
                      why: str = "") -> dict[str, Any]:
        """Decide what a shot's picture is made from (a shot, a master, a file, or location:CAM-A) and, for a derived picture, whose faces it takes."""
        payload: dict[str, Any] = {"scene_id": scene, "shot_id": shot, "from": made_from, "rationale": why}
        if faces is not None:
            payload["with"] = faces
        return _answer(lambda: runtime.command("set_reference", payload))

    @server.tool(annotations=deciding)
    def clear_reference(scene: str, shot: str, why: str = "") -> dict[str, Any]:
        """Return a shot's references to what the breakdown says."""
        return _answer(lambda: runtime.command("clear_reference", {"scene_id": scene, "shot_id": shot,
                                                                    "rationale": why}))

    @server.tool(annotations=deciding)
    def set_voice_in_cut(scene: str, shot: str, converted: bool = True, why: str = "") -> dict[str, Any]:
        """Decide whether the cut hears this shot's speech in the cast's own recorded voices (converted at assembly)."""
        return _answer(lambda: runtime.command("set_voice", {"scene_id": scene, "shot_id": shot,
                                                              "converted": converted, "rationale": why}))

    # --- workflows and jobs ------------------------------------------------------------

    @server.tool(annotations=working)
    def start_workflow(scene: str, target: str) -> dict[str, Any]:
        """Start the built-in workflow for a block (its id) or a lone shot (P7): master picture, the director's approval, video, takes."""
        def start() -> dict[str, Any]:
            key = "shot" if any(shot["id"] == target for shot in runtime.scene(scene)["shots"]) else "block"
            return runtime.command("start_workflow", {"scene_id": scene, key: target,
                                                       **({"template": "shot"} if key == "shot" else {})})

        return _answer(start)

    @server.tool(annotations=working)
    def resume_workflow(scene: str, workflow: str) -> dict[str, Any]:
        """Move a stopped workflow run on."""
        return _answer(lambda: runtime.command("resume_workflow", {"scene_id": scene, "workflow_id": workflow}))

    def submit(kind: str, params: dict[str, Any]) -> dict[str, Any]:
        return _answer(lambda: {key: public_job(jobs.submit(kind, runtime.root, params)).get(key)
                                for key in ("id", "kind", "state", "message")})

    @server.tool(annotations=working)
    def assemble_scene(scene: str, version: str = "", summary: str = "") -> dict[str, Any]:
        """Assemble a new version of a scene from its chosen takes (a job; follow it with wait_for_job)."""
        return submit("assemble", {"scene": scene, "version": version, "summary": summary})

    @server.tool(annotations=working)
    def slice_block(scene: str, block: str, clip: str = "") -> dict[str, Any]:
        """Slice a generated block clip into takes of its shots (a job)."""
        return submit("slice_block", {"scene": scene, "block": block, **({"clip": clip} if clip else {})})

    @server.tool(annotations=working)
    def revoice_take(scene: str, shot: str, take: str = "") -> dict[str, Any]:
        """Convert a take's speech to the cast's recorded voices, as a new take (a job, on this machine's CPU)."""
        return submit("convert_voice", {"scene": scene, "shot": shot, **({"take": take} if take else {})})

    @server.tool(annotations=paying)
    def generate(scene: str, target: str, max_usd: float, seed: int = 1) -> dict[str, Any]:
        """Generate a block (its id) or a lone shot (P7) as video: paid. max_usd must cover plan_generation's estimate."""
        def run() -> dict[str, Any]:
            planned, single = _generation_plan(runtime, scene, target, seed)
            _within(planned.estimate_usd, max_usd)
            unit = "shot" if single else "block"
            job = public_job(jobs.submit("generate_block", runtime.root, {"scene": scene, unit: target, "seed": seed}))
            return {field: job.get(field) for field in ("id", "kind", "state", "message")} | {
                "estimate_usd": planned.estimate_usd}

        return _answer(run)

    @server.tool(annotations=paying)
    def make_picture(scene: str, shot: str, max_usd: float, seed: int = 1) -> dict[str, Any]:
        """Make a shot's master picture by editing its source with the cast (derive): paid. max_usd must cover plan_picture's estimate."""
        from .jobs import _picture_plan

        def run() -> dict[str, Any]:
            planned = _picture_plan(runtime.root, {"scene": scene, "shot": shot, "seed": seed})[0]
            _within(planned.estimate_usd, max_usd)
            job = public_job(jobs.submit("derive_picture", runtime.root, {"scene": scene, "shot": shot, "seed": seed}))
            return {key: job.get(key) for key in ("id", "kind", "state", "message")} | {"estimate_usd": planned.estimate_usd}

        return _answer(run)

    @server.tool(annotations=reading)
    def job_status(job_id: str) -> dict[str, Any]:
        """A job's state, progress and message."""
        return _answer(lambda: {key: public_job(jobs.get(job_id)).get(key)
                                for key in ("id", "kind", "state", "progress", "message", "error")})

    @server.tool(annotations=working)
    async def wait_for_job(job_id: str, seconds: int = 300, adopt: bool = True) -> dict[str, Any]:
        """Wait for a job (up to `seconds`, at most 600); when it succeeded, bring its files into the film (adopt) and return what it made."""
        import anyio

        deadline = time.monotonic() + max(1, min(int(seconds), 600))
        while True:
            try:
                job = jobs.get(job_id)
            except CineToasterError as error:
                return {"refused": error.message}
            if job["state"] in ("succeeded", "failed", "cancelled") or time.monotonic() > deadline:
                break
            await anyio.sleep(0.5)
        answer = {key: job.get(key) for key in ("id", "kind", "state", "progress", "message", "error")}
        if job["state"] == "succeeded" and adopt and not job.get("adopted_at"):
            adopted = _answer(lambda: jobs.adopt(job_id))
            if "refused" in adopted:
                return {**answer, **adopted}
            job = adopted
        if job["state"] == "succeeded":
            answer["result"] = (job.get("result") or {}).get("summary")
        return answer

    @server.tool(annotations=working)
    def cancel_job(job_id: str) -> dict[str, Any]:
        """Stop a running job."""
        return _answer(lambda: {key: public_job(jobs.cancel(job_id)).get(key) for key in ("id", "state", "message")})

    return server


def _generation_plan(runtime: LocalRuntime, scene_id: str, target: str, seed: int):
    import os

    from .generation import hourly_rate, plan_block, plan_shot

    production = runtime.production()
    rate = hourly_rate(runtime.root, os.environ.get("RUNPOD_LTX_ENDPOINT_ID", ""))
    scene = next((item for item in production["scenes"] if item["id"] == scene_id), None)
    if scene is None:
        raise ValidationError(f"No scene {scene_id!r}")
    single = not any(block["id"] == target for block in scene.get("blocks") or []) \
        and any(shot["id"] == target for shot in scene["shots"])
    planned = (plan_shot(runtime.root, production, scene_id, target, seed=seed, rate=rate) if single
               else plan_block(runtime.root, production, scene_id, target, seed=seed, rate=rate))
    return planned, single


def _within(estimate: float, cap: float) -> None:
    if cap < estimate:
        raise ValidationError(f"The estimate is US$ {estimate:.3f}, above the US$ {cap:.3f} this call allows; "
                              "nothing was sent")


def serve(root: Path) -> None:
    build(root).run("stdio")
