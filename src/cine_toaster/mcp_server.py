"""Cine Toaster as an MCP server: Claude Code working on a film through the product (CT-0045).

A person who works on a film with Claude Code connects it here
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

    toast mcp <project> [--env-file <credentials>]
    claude mcp add cine-toaster -- toast mcp <project>
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .errors import CineToasterError, ValidationError
from .production_context import WORK_POLICY, work_structure

ACTOR = {"id": "claude-code", "kind": "agent"}

INSTRUCTIONS = (
    "Cine Toaster holds a film as files: breakdowns, a screenplay, cast sheets, takes. Work on it through these "
    "tools, not by editing its files: every change here is a recorded decision with a revision. Creation / Inception "
    "precedes writing: read_creation shows concept and screenplay candidates and reference inputs; "
    "save_creation_candidate appends a version without replacing or approving the film screenplay. "
    "Early reference exploration may consume quota; distinguish it from approved shot production. Start with "
    "film_overview, then read_scene or read_shot; how_to_make_a_film is the whole guide. A scene goes through two "
    "phases. Phase 1 fits the screenplay and the storyboard together; planning itself needs no generation. "
    "Optional exploratory image generation may consume quota or money and must be disclosed. "
    "A person then approves the scene's storyboard (each scene shows its phase), and phase 2 produces it: "
    "master pictures, clips as takes, scene versions, sequences, every result kept as a version. Do not spend on "
    "a scene whose storyboard is not approved without saying so. list_practices and read_practice give the "
    "filmmaking practices the checks enforce. Cuts, references and voices are decisions over the breakdown; "
    "workflows and jobs make pictures, video, takes and versions. Paid generation needs max_usd at or above the "
    "estimate plan_generation gives, and the budget ceiling holds whatever you pass. Approving or refusing a "
    "picture, choosing a take and approving the storyboard are the director's: explain the candidates, never "
    "decide. A long job returns an id: follow it with wait_for_job. "
    "When launching the GUI for this director on a trusted LAN, prefer toast serve PROJECT --host 0.0.0.0 "
    "--assistant, and report http://<LAN_IP>:8787/app/creation.html using the computer's actual LAN IP, "
    "checking the startup LAN URL and read-only forwarding diagnostics. "
    "not localhost or 0.0.0.0 as the phone destination. The runtime is unauthenticated: never expose it "
    "to the internet. Check WSL NAT/mirrored networking and authorised firewall/forwarding separately; "
    "do not claim phone reachability from a loopback check or change system networking silently."
)


INSTRUCTIONS += ('\nUse read_work_structure for exact sequence/scene scope and read_production_work '
                 'for explicit pending agent-owned requests and blockers. A pending request is not a running job.\n') + WORK_POLICY


class LocalRuntime:
    """The runtime in this process, with the reading surface the assistant's reads expect."""

    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()

    def production(self) -> dict[str, Any]:
        from .project import load_production

        return load_production(self.root)

    def creation(self) -> dict[str, Any]:
        from .creation import creation_view

        return creation_view(self.root)

    def scene(self, scene_id: str) -> dict[str, Any]:
        scene = next((item for item in self.production()["scenes"] if item["id"] == scene_id), None)
        if scene is None:
            raise ValidationError(f"No scene {scene_id!r}")
        return scene

    def storyboard(self, scene: str = "") -> dict[str, Any]:
        from .storyboard import storyboard_view
        return storyboard_view(self.root, scene)

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
    def plan_reference_exploration(title: str, request: str, parents: list[str] | None = None,
                                    concept: str = "") -> dict[str, Any]:
        """Preview exact prompt, saved input hashes, provider availability and quota use. Sends nothing."""
        from .creation_jobs import plan_reference
        return _answer(lambda: plan_reference(runtime.root, {"title": title, "request": request,
                              "parents": parents or [], "concept": concept}))

    @server.tool(annotations=paying)
    def start_reference_exploration(plan: dict[str, Any], accept_quota: bool = False) -> dict[str, Any]:
        """Generate one exploratory image from an inspected plan only after explicit quota consent.
        Returns a job id; wait_for_job with adopt=False retains a staged result for review.
        A kept result creates a new reference and never replaces any existing image."""
        return _answer(lambda: public_job(jobs.submit("generate_reference", runtime.root,
                              {**plan, "accept_quota": accept_quota})))

    @server.tool(annotations=reading)
    def read_creation() -> dict[str, Any]:
        """Concept and screenplay candidate history, pinned inputs and the film's exploratory references."""
        from .creation import creation_view
        return creation_view(runtime.root)

    @server.tool(annotations=working)
    def assess_inception(title: str, summary: str, readiness: list[dict], proposal: dict,
                          references: list[str], expected_revision: int) -> dict[str, Any]:
        """Record the agent's assessment, not a human approval. Readiness items name destination
        (screenplay/storyboard/masters), status (ready/needs_work/not_assessed), summary and gaps
        (description, owner=agent/human, next_action). Proposal names destination, question, scope,
        why and next_step. Explain sufficiency; do not infer it from image counts. Pins current
        material and presents Approve / Request changes to the human; never starts paid generation."""
        from .creation_review import record_inception_assessment
        from .state import Actor
        return _answer(lambda: record_inception_assessment(runtime.root, title=title, summary=summary,
            readiness=readiness, proposal=proposal, references=references, expected_revision=expected_revision,
            actor=Actor(**ACTOR)))

    @server.tool(annotations=reading)
    def read_storyboard_candidates(scene: str = "") -> dict[str, Any]:
        """Retained story drawings, exact input versions and changes; not masters or approvals."""
        return _answer(lambda: runtime.storyboard(scene))

    @server.tool(annotations=working)
    def save_storyboard_candidate(scene: str, shot: str, image: str, title: str, expected_revision: int,
                                  references: list[str] | None = None, based_on: str = "", note: str = "",
                                  provenance: dict | None = None) -> dict[str, Any]:
        """Import an explicitly requested drawing already inside this film. Keep older versions;
        never approve a storyboard, choose a cast master or publish a finished shot image."""
        from .storyboard import register_storyboard_candidate
        from .state import Actor
        def save():
            root = runtime.root.resolve()
            path = (root / image).resolve()
            if not path.is_relative_to(root):
                raise ValidationError("Storyboard import image must be inside this production")
            return register_storyboard_candidate(root, scene=scene, shot=shot, image=path, title=title,
                expected_revision=expected_revision, actor=Actor(**ACTOR), references=references,
                based_on=based_on, note=note, provenance=provenance)
        return _answer(save)

    @server.tool(annotations=working)
    def record_exploration_round(title: str, references: list[str], expected_revision: int,
                                 rationale: str, source: str, follows: str = "",
                                 corrections: list[dict[str, str]] | None = None, based_on: str = "") -> dict[str, Any]:
        """Record an explicitly described creative pass and its intended corrections.
        Corrections name previous/current reference ids. Never infer these from image similarity,
        treat them as provider image inputs or approve the new pass automatically."""
        from .creation import save_exploration_round
        from .state import Actor
        return _answer(lambda: save_exploration_round(runtime.root, title=title, references=references,
            expected_revision=expected_revision, actor=Actor(**ACTOR), rationale=rationale, source=source,
            follows=follows, corrections=corrections, based_on=based_on))

    @server.tool(annotations=working)
    def save_creation_candidate(kind: str, title: str, text: str, expected_revision: int,
                                references: list[str] | None = None, concept: str = "",
                                based_on: str = "", rationale: str = "") -> dict[str, Any]:
        """Save an explicitly requested candidate version with pinned inputs; never edit the film's current
        screenplay or approve anything. A screenplay candidate must name a saved concept version."""
        from .creation import save_creation_draft
        from .state import Actor
        return _answer(lambda: save_creation_draft(runtime.root, kind=kind, title=title, text=text,
                       expected_revision=expected_revision, actor=Actor(**ACTOR), references=references,
                       concept=concept, based_on=based_on, rationale=rationale))

    @server.tool(annotations=reading)
    def film_overview() -> str:
        """The whole film: scenes with shots, chosen takes, findings, waiting gates, runs; sequences, cast, budget."""
        return overview(runtime.production(), runtime.budget())

    @server.tool(annotations=reading)
    def read_work_structure(sequence: str = "", scene: str = "") -> dict[str, Any]:
        """Canonical ordered sequences and the production work/review contract.

        Focusing a scene does not narrow sequence review. No readiness/approval
        is inferred, and missing groupings are not invented from scene numbers.
        """
        return _answer(lambda: work_structure(runtime.production(), sequence=sequence, scene=scene))

    @server.tool(annotations=reading)
    def read_production_work() -> dict[str, Any]:
        """Explicit pending sequence reviews: owner, exact scope, source changes and agent-owned gaps, not live jobs."""
        from .sequence_work import sequence_work_view
        return _answer(lambda: sequence_work_view(runtime.root))

    @server.tool(annotations=working)
    def request_sequence_review(sequence: str, title: str, rationale: str,
                                expected_revision: int, expected_source_digest: str) -> dict[str, Any]:
        """Record an explicitly authorised sequence review task; never approve, generate or claim dispatch/completion.

        Use revision/source_digest from read_production_work. Missing review capabilities remain visible blockers.
        """
        from .sequence_work import request_sequence_review as request_review
        from .state import Actor
        return _answer(lambda: request_review(runtime.root, sequence=sequence, title=title, rationale=rationale,
                       expected_revision=expected_revision, expected_source_digest=expected_source_digest,
                       actor=Actor(**ACTOR)))

    @server.tool(annotations=reading)
    def read_intake() -> dict[str, Any]:
        """The format interview: the format's intake sheet, what was asked, and the person's answers (SPEC-0020)."""
        from .intake import intake_view
        return _answer(lambda: intake_view(runtime.root))

    @server.tool(annotations=working)
    def ask_intake_questions(questions: list[dict[str, str]], expected_revision: int) -> dict[str, Any]:
        """Ask the person what only they can tell and the records do not say: at most a few, each with why.

        Each question: {item (a sheet item id, or a new id), question, why, based_on (an answer id when asking
        again)}. You never answer: the person does, in the decision inbox or `toast intake --answer`.
        """
        from .intake import ask_intake
        from .state import Actor
        return _answer(lambda: ask_intake(runtime.root, questions=questions, expected_revision=expected_revision,
                                          actor=Actor(**ACTOR)))

    @server.tool(annotations=reading)
    def read_scene(scene: str) -> str:
        """One scene's records: blocks, workflow runs, gates, pictures, findings, location."""
        return read(runtime, "scene", {"scene": scene})

    @server.tool(annotations=reading)
    def read_shot(scene: str, shot: str) -> str:
        """One shot: action, camera, lines, master picture, and its takes with where they came from."""
        return read(runtime, "shot", {"scene": scene, "shot": shot})

    @server.tool(annotations=reading)
    def how_to_make_a_film() -> str:
        """The guide to making a film here: the production's folder, the two phases and the storyboard gate between
        them, the commands for each step, and what is the director's (docs/making-a-film.md)."""
        from .new_production import guide_text

        return guide_text()

    @server.tool(annotations=reading)
    def list_practices() -> list[dict[str, Any]]:
        """The filmmaking practices this production follows -- Cine Toaster's and its own -- and which checks
        enforce each (a finding's code names the check)."""
        from .knowledge import load_practices

        return [{"id": item.id, "title": item.title, "domain": item.domain, "status": item.status,
                 "enforced_by": list(item.enforced_by), "origin": item.origin}
                for item in load_practices(runtime.root)]

    @server.tool(annotations=reading)
    def read_practice(practice: str) -> dict[str, Any]:
        """One practice in full: what it says, why, and what enforces it."""
        from .knowledge import load_practices

        found = next((item for item in load_practices(runtime.root) if item.id == practice), None)
        if found is None:
            return {"refused": f"No practice {practice!r}; list_practices gives the ids"}
        return {"id": found.id, "title": found.title, "domain": found.domain, "status": found.status,
                "body": found.body, "enforced_by": list(found.enforced_by), "evidence": list(found.evidence)}

    @server.tool(annotations=reading)
    def list_references() -> list[dict[str, Any]]:
        """What the film looks at -- draft boards, probes, paintings -- each with who or what made it, its prompt,
        the references it came from, its licence and what is wrong with its record. Not material of the film;
        adding one is the director's (toast references add)."""
        from .references import load_references

        return [{key: value for key, value in item.items() if key != "path"} for item in load_references(runtime.root)]

    @server.tool(annotations=paying)
    def generate_reference(title: str, prompt: str, from_references: list[str] | None = None, name: str = "",
                           notes: list[str] | None = None, cast: str = "", style: str = "") -> dict[str, Any]:
        """Make one picture through Codex's image generation (the director's ChatGPT subscription quota, no
        dollars) from a description and the pictures of earlier references, and keep it as a new reference
        recorded as asked by claude-code. A reference is something to look at -- a probe, a trial of an era or
        a face -- never material of the film. The description says what to take from each reference. Takes a
        couple of minutes."""
        from .references import generate_reference as make

        try:
            folder = make(runtime.root, prompt=prompt, title=title, parents=list(from_references or []),
                          requested_by=ACTOR["id"], notes=list(notes or []), name=name, cast=cast, style=style)
        except CineToasterError as error:
            return {"refused": str(error)}
        return {"reference": folder.name, "image": str(folder / "image.png")}

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
    def list_titles() -> list[dict[str, Any]]:
        """The title catalog: a shot names one with `title: {id: …, text: …}` in its breakdown."""
        from .titles import engine_missing, list_titles as catalog

        return [{"id": item["id"], "name": item["name"], "category": item["category"], "says": item["says"],
                 "engine": item["engine"], "params": item["params"], "unavailable": engine_missing(item["engine"])}
                for item in catalog(runtime.root)]

    @server.tool(annotations=reading)
    def list_effects() -> dict[str, Any]:
        """The VFX catalog and the production's stock elements: a shot lists effects with `effects: [{id: …}]`."""
        from .vfx import list_effects as catalog, list_elements

        return {"effects": [{"id": item["id"], "name": item["name"], "category": item["category"], "says": item["says"],
                             "params": item["params"], "element_category": item["element_category"]}
                            for item in catalog(runtime.root)],
                "elements": list_elements(runtime.root)}

    @server.tool(annotations=reading)
    def continuity_ledger(scene: str = "", shot: str = "") -> dict[str, Any]:
        """The continuity ledger: what holds from scene to scene (cast variant, declared facts such as wardrobe,
        props, time, weather), and its breaks. With a scene (and a shot), what holds there."""
        from .continuity import ledger, state_at

        production = runtime.production()
        if scene:
            return state_at(production, scene, shot)
        report = ledger(production)
        return {"scenes": report["scenes"],
                "findings": {key: [item.public_dict() for item in value] for key, value in report["findings"].items()}}

    @server.tool(annotations=reading)
    def production_status(sequence: str = "") -> dict[str, Any]:
        """Where the production stands, by sequence and scene: shots with a take, waiting for a choice or for
        generation; the latest version and its verdict; blockers; the decisions that come next."""
        from .producer import production_status as status

        return status(runtime.production(), sequence)

    @server.tool(annotations=reading)
    def list_styles() -> list[dict[str, Any]]:
        """The style catalog -- direction, animation techniques, formats (viral vertical, commercial, trailer...).
        A production names one with `style:` in project.yaml, a scene may name another. Choosing it is the
        director's."""
        from .styles import list_styles as catalog

        return [{key: item[key] for key in ("id", "name", "kind", "says", "camera", "editing", "performance",
                                            "format", "prompt", "use_when", "avoid_when")}
                for item in catalog(runtime.root)]

    @server.tool(annotations=reading)
    def list_emotions() -> list[dict[str, Any]]:
        """The emotion catalog: a shot names `emotion: {id, who, intensity: subtle|clear|overwhelming,
        arc: holds|builds|fades|breaks}`. How a character feels is the director's to decide."""
        from .emotions import list_emotions as catalog

        return [{key: item[key] for key in ("id", "name", "family", "says", "near", "signals", "ask")}
                for item in catalog(runtime.root)]

    @server.tool(annotations=reading)
    def list_sounds() -> list[dict[str, Any]]:
        """The sound catalog: a shot places `sounds: [{id: …, at: …}]`; a scene names `ambience` and `music`."""
        from .sounds import list_sounds as catalog

        return [{key: item[key] for key in ("id", "name", "category", "says", "params", "licence", "credit",
                                            "status", "exists")} for item in catalog(runtime.root)]

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
                split: float = 0.0, why: str = "") -> dict[str, Any]:
        """Decide the cut into `shot` (hard, match, action, j, l, smash, jump, continuation), optionally with a
        catalog transition; a j or l cut may say how many seconds its sound crosses the picture cut (`split`)."""
        cut = {"type": cut_type, "reason": reason, "transition": {"id": transition} if transition else None,
               "split": split or None}
        return _answer(lambda: runtime.command("set_cut", {"scene_id": scene, "shot_id": shot, "cut": cut,
                                                            "rationale": why}))

    @server.tool(annotations=deciding)
    def set_cuts(scene: str, cuts: list[dict[str, Any]], why: str = "") -> dict[str, Any]:
        """Decide several cuts of one scene together, all or none: cuts = [{shot, cut_type, reason?, transition?, split?}]."""
        payload = [{"shot": item.get("shot"), "cut": {
            "type": item.get("cut_type") or item.get("type") or "hard", "reason": item.get("reason", ""),
            "split": item.get("split") or None,
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
    def assemble_scene(scene: str, version: str = "", summary: str = "", stems: bool = False,
                       otio: bool = False) -> dict[str, Any]:
        """Assemble a new version of a scene from its chosen takes (a job; follow it with wait_for_job).
        With stems, the sound is also written in its parts (dialogue, room, effects, ambience, music) for a DAW;
        with otio, the cut as OpenTimelineIO, to finish it in an editor."""
        return submit("assemble", {"scene": scene, "version": version, "summary": summary, "stems": stems,
                                   "otio": otio})

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
