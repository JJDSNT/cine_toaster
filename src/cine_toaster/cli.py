from __future__ import annotations

import argparse
import getpass
import json
import os
import shutil
import sys
from pathlib import Path

from .commands import (
    clear_selection,
    record_assembly,
    restore_assembly,
    review_assembly,
    select_take,
)
from .errors import CineToasterError
from .events import tail_events
from .index import ProjectIndex, build_index, index_path_for
from .knowledge import coverage, load_practices, load_providers, practices_for_check
from .model import ProjectItem
from .project import load_production
from .state import ASSEMBLY_VERDICTS, Actor
from .web import serve_project


SOURCE_REPOSITORY_ROOT = Path(__file__).parents[2]
SOURCE_EXAMPLES = SOURCE_REPOSITORY_ROOT / "examples"
PACKAGED_DEMO_PROJECTS = Path(__file__).with_name("demo_projects")
DEFAULT_DEMO_TEMPLATE = "the-last-signal"
DEMO_TEMPLATES = {
    "the-last-signal": {
        "title": "The Last Signal",
        "source": SOURCE_EXAMPLES / "demo-project",
        "packaged": PACKAGED_DEMO_PROJECTS / "the-last-signal",
    },
    "amiga-demo-reel": {
        "title": "Amiga Demo Reel",
        "source": SOURCE_EXAMPLES / "amiga-demo-reel",
        "packaged": PACKAGED_DEMO_PROJECTS / "amiga-demo-reel",
    },
}


def demo_template_path(template_id: str) -> Path:
    template = DEMO_TEMPLATES[template_id]
    source = template["source"]
    return source if source.is_dir() else template["packaged"]


def _source_checkout_root() -> Path | None:
    root = SOURCE_REPOSITORY_ROOT.resolve()
    if (root / ".git").exists() and (root / "pyproject.toml").is_file():
        return root
    return None


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} TiB"


def _ensure_index(root: Path, *, refresh: bool = False) -> ProjectIndex:
    if refresh or not index_path_for(root).exists():
        summary = build_index(root)
        print(
            f"Indexed {summary.file_count} files and {summary.directory_count} directories "
            f"({_human_size(summary.total_bytes)}).",
            file=sys.stderr,
        )
    return ProjectIndex(root)


def _print_tree(index: ProjectIndex, parent: ProjectItem, depth: int, prefix: str = "") -> None:
    if depth <= 0:
        return
    children = index.children(parent.id)
    for position, child in enumerate(children):
        last = position == len(children) - 1
        branch = "└── " if last else "├── "
        marker = "/" if child.is_directory else ""
        print(f"{prefix}{branch}{child.name}{marker}  [{child.kind}]")
        if child.is_directory:
            extension = "    " if last else "│   "
            _print_tree(index, child, depth - 1, prefix + extension)


def command_index(args: argparse.Namespace) -> int:
    summary = build_index(args.project)
    value = summary.public_dict()
    value["index_path"] = str(index_path_for(args.project))
    if args.json:
        print(json.dumps(value, ensure_ascii=False, indent=2))
    else:
        print(f"Project: {summary.name}")
        print(f"Adapter: {summary.adapter}")
        print(f"Files: {summary.file_count}")
        print(f"Directories: {summary.directory_count}")
        print(f"Media size: {_human_size(summary.total_bytes)}")
        print(f"Index: {index_path_for(args.project)}")
    return 0


def command_tree(args: argparse.Namespace) -> int:
    index = _ensure_index(args.project, refresh=args.refresh)
    start = index.get_by_path(args.path)
    if start is None:
        print(f"Path not found in project index: {args.path}", file=sys.stderr)
        return 2
    print(f"{start.name}/  [{start.kind}]")
    _print_tree(index, start, args.depth)
    return 0


def command_find(args: argparse.Namespace) -> int:
    index = _ensure_index(args.project, refresh=args.refresh)
    results = index.search(args.query, kind=args.kind, limit=args.limit)
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0
    for result in results:
        print(f"{result['relative_path']}  [{result['kind']}]")
        if snippet := result.get("snippet"):
            print(f"  {snippet}")
    if not results:
        print("No matches.")
    return 0


def command_stats(args: argparse.Namespace) -> int:
    index = _ensure_index(args.project, refresh=args.refresh)
    summary = index.summary()
    value = summary.public_dict()
    value["index_path"] = str(index.path)
    if args.json:
        print(json.dumps(value, ensure_ascii=False, indent=2))
    else:
        print(f"Project: {summary.name}")
        print(f"Root: {summary.root}")
        print(f"Adapter: {summary.adapter}")
        print(f"Indexed: {summary.indexed_at}")
        print(f"Items: {summary.item_count}")
        print(f"Files: {summary.file_count}")
        print(f"Directories: {summary.directory_count}")
        print(f"Media size: {_human_size(summary.total_bytes)}")
    return 0


def command_serve(args: argparse.Namespace) -> int:
    _ensure_index(args.project, refresh=not args.no_refresh)
    serve_project(args.project, host=args.host, port=args.port, assistant=args.assistant)
    return 0


def command_demo(args: argparse.Namespace) -> int:
    if args.list_templates:
        for template_id, template in DEMO_TEMPLATES.items():
            default = " (default)" if template_id == DEFAULT_DEMO_TEMPLATE else ""
            print(f"{template_id}\t{template['title']}{default}")
        return 0

    if args.destination is None:
        print("Destination is required unless --list is used.", file=sys.stderr)
        return 2

    destination = args.destination.expanduser().resolve()
    if destination.exists():
        print(f"Destination already exists: {destination}", file=sys.stderr)
        return 2
    checkout = _source_checkout_root()
    if (
        checkout is not None
        and _is_within(destination, checkout)
        and not args.allow_inside_repository
    ):
        print(
            "Refusing to create a runtime project inside the Cine Toaster "
            f"source repository: {destination}\n"
            "Choose a destination outside the checkout or pass "
            "--allow-inside-repository for intentional fixture development.",
            file=sys.stderr,
        )
        return 2
    template = DEMO_TEMPLATES[args.template]
    source = demo_template_path(args.template)
    if not source.is_dir():
        print(f"Demo project template is unavailable: {source}", file=sys.stderr)
        return 2
    shutil.copytree(source, destination)
    print(f"Created {template['title']} demo production at {destination}")
    print(f"Open it with: toast serve {destination}")
    return 0


def _resolve_actor(args: argparse.Namespace) -> Actor:
    name = args.actor or os.environ.get("CINE_TOASTER_ACTOR") or getpass.getuser()
    return Actor(id=name, kind=args.actor_kind)


def _print_take(take: dict[str, object], *, selected: bool) -> None:
    marker = "*" if selected else " "
    status = str(take["status"])
    label = f"{take['id']}  {take['label']}"
    suffix = "" if status == "candidate" else f"  [{status}]"
    print(f"    {marker} {label}{suffix}")
    if take["note"]:
        print(f"        {take['note']}")
    if take["media"]:
        print(f"        media: {take['media']}")


def command_shots(args: argparse.Namespace) -> int:
    production = load_production(args.project)
    scenes = production["scenes"]
    if args.scene:
        scenes = [scene for scene in scenes if scene["id"] == args.scene]
        if not scenes:
            print(f"Scene not found: {args.scene}", file=sys.stderr)
            return 2

    if args.json:
        print(json.dumps(scenes, ensure_ascii=False, indent=2))
        return 0

    for scene in scenes:
        print(f"{scene['id']}  {scene['title']}  (revision {scene['revision']})")
        for shot in scene["shots"]:
            camera = f"  camera {shot['camera']}" if shot["camera"] else ""
            print(f"  {shot['id']}  {shot['label']}  [{shot['status']}]{camera}")
            for take in shot["takes"]:
                _print_take(take, selected=bool(take.get("selected")))
            if not shot["takes"] and shot["take_count"]:
                print(f"      {shot['take_count']} unregistered alternatives")
        print()
    return 0


def command_take_select(args: argparse.Namespace) -> int:
    result = select_take(
        args.project,
        scene_id=args.scene,
        shot_id=args.shot,
        take_id=args.take,
        actor=_resolve_actor(args),
        expected_revision=args.expect_revision,
        rationale=args.rationale,
    )
    if args.json:
        print(json.dumps(result.public_dict(), ensure_ascii=False, indent=2))
    else:
        previous = f" (was {result.previous_take_id})" if result.previous_take_id else ""
        print(
            f"Selected {result.take_id} for {result.shot_id}{previous} "
            f"-> revision {result.revision}"
        )
    return 0


def command_take_clear(args: argparse.Namespace) -> int:
    result = clear_selection(
        args.project,
        scene_id=args.scene,
        shot_id=args.shot,
        actor=_resolve_actor(args),
        expected_revision=args.expect_revision,
        rationale=args.rationale,
    )
    if args.json:
        print(json.dumps(result.public_dict(), ensure_ascii=False, indent=2))
    else:
        print(
            f"Cleared the selection on {result.shot_id} "
            f"(was {result.previous_take_id}) -> revision {result.revision}"
        )
    return 0


def _foreground_job(kind: str, project: Path, params: dict, output: Path | None, *, quiet: bool = False) -> dict | None:
    """Run a job in this process, show its progress, and adopt its result (SPEC-0008).

    The CLI goes through the same Job Manager as the control room, so a
    render started here is recorded, can be cancelled from elsewhere, and is
    reconciled if this process dies.
    """

    from .jobs import JobManager

    manager = JobManager()
    job = manager.submit(kind, project, params)
    shown = {"line": ""}

    def show(current: dict) -> None:
        if quiet or not sys.stderr.isatty():
            return
        line = f"  {current['progress']:5.0%}  {current['message']}"[:78]
        if line != shown["line"]:
            print("\r" + line.ljust(78), end="", file=sys.stderr, flush=True)
            shown["line"] = line

    try:
        job = manager.wait(job["id"], on_progress=show)
    except KeyboardInterrupt:
        manager.cancel(job["id"])
        job = manager.wait(job["id"])
    finally:
        if shown["line"]:
            print(file=sys.stderr)
        manager.shutdown()
    if job["state"] != "succeeded":
        print(f"{kind} {job['state']}: {job.get('error') or job['message']}  (job {job['id']})", file=sys.stderr)
        return None
    return manager.adopt(job["id"], overwrite=True, destination=output)


def command_build(args: argparse.Namespace) -> int:
    """Render the production's composed shots into one watchable file."""

    job = _foreground_job("build", args.project, {"engine": args.engine}, args.output, quiet=args.json)
    if job is None:
        return 1
    result = job["result"]["summary"]
    adopted = job["message"].removeprefix("Adopted: ")
    if args.json:
        print(json.dumps({**result, "output": adopted, "job": job["id"]}, indent=2))
    else:
        print(
            f"Built {adopted}\n"
            f"  {result['shots']} shot(s), {result['transitions']} transition(s), "
            f"{result['duration_seconds']:.1f}s, "
            f"{'with audio' if result['audio'] else 'silent'}\n"
            f"  engine {result['engine']}: {result['shaders']} transition(s) ran their own shader\n"
            f"  {result['stills']} still(s) kept for the storyboard\n"
            f"  job {job['id']}"
        )
    return 0


def command_assemble(args: argparse.Namespace) -> int:
    """Assemble a new version of a scene from its selected takes, as a job."""

    from .jobs import JobManager

    manager = JobManager()
    try:
        job = manager.submit("assemble", args.project, {"scene": args.scene, "version": args.version or "",
                                                        "summary": args.summary or ""})
        job = manager.wait(job["id"])
        if job["state"] != "succeeded":
            print(f"assemble {job['state']}: {job.get('error') or job['message']}  (job {job['id']})", file=sys.stderr)
            return 1
        job = manager.adopt(job["id"])
    finally:
        manager.shutdown()
    summary = job["result"]["summary"]
    print(f"{args.scene} {job['params']['version']}: {len(summary['segments'])} shot(s), "
          f"{summary['duration_seconds']:.1f} s -> {job['message'].removeprefix('Adopted: ')}")
    for segment in summary["segments"]:
        print(f"  {segment['shot']:5} take {segment['take']:12} {segment['start']:.2f}–{segment['end']:.2f} s  ({segment['join']})")
    for note in summary["notes"]:
        print(f"  note: {note}")
    return 0


def command_slice(args: argparse.Namespace) -> int:
    """Slice a block's clip into one take per shot, by where the model really cut (CT-0037)."""

    from .jobs import JobManager

    manager = JobManager()
    try:
        params = {"scene": args.scene, "block": args.block} | ({"clip": args.clip} if args.clip else {})
        job = manager.wait(manager.submit("slice_block", args.project, params)["id"])
        if job["state"] != "succeeded":
            print(f"slice {job['state']}: {job.get('error') or job['message']}  (job {job['id']})", file=sys.stderr)
            return 1
        if not args.dry_run:
            job = manager.adopt(job["id"])
    finally:
        manager.shutdown()
    summary = job["result"]["summary"]
    print(f"{args.scene} block {summary['block']}: cuts {summary['method']}" + (f" ({summary['note']})" if summary["note"] else ""))
    for item in summary["slices"]:
        print(f"  {item['shot']:5} take {item['take']:12} {item['seconds'][0]:.3f}–{item['seconds'][1]:.3f} s")
    print("  (not adopted: --dry-run)" if args.dry_run else "  adopted as takes; choose between them in the control room")
    return 0


def command_budget(args: argparse.Namespace) -> int:
    """What paid generation may spend, and what it has spent (CT-0037)."""

    from . import spend

    if args.budget_command == "set":
        spend.set_limit(args.usd)
    data = spend.load()
    if args.json:
        print(json.dumps({**data, "spent_usd": spend.spent(data)}, indent=2))
        return 0
    limit = float(data.get("limit_usd") or 0)
    print(f"Spent US$ {spend.spent(data):.2f} of US$ {limit:.2f}" if limit else
          f"No budget set (spent US$ {spend.spent(data):.2f}); nothing will be generated. Set one: toast budget set <usd>")
    for entry in data["entries"][-10:]:
        print(f"  {entry['at'][:19]}  US$ {entry['usd']:.4f}  {entry.get('status', ''):10} {entry['what']}")
    print(f"Ledger: {spend.ledger_path()}")
    return 0


def command_generate(args: argparse.Namespace) -> int:
    """Generate a block of shots as one paid generation, within the budget (CT-0037)."""

    from . import spend
    from .generation import hourly_rate, plan_block
    from .jobs import JobManager
    from .providers.runpod import load_credentials

    root = Path(args.project).expanduser().resolve()
    if args.env_file:
        load_credentials(Path(args.env_file).expanduser())  # never printed
    from .generation import plan_shot

    production = load_production(root)
    rate = hourly_rate(root, os.environ.get("RUNPOD_LTX_ENDPOINT_ID", ""))
    # A block's id, or a shot outside any block (its result is a take of that shot).
    scene = next((item for item in production["scenes"] if item["id"] == args.scene), {"blocks": [], "shots": []})
    is_block = any(block["id"] == args.block for block in scene.get("blocks") or [])
    single = not is_block and any(shot["id"] == args.block for shot in scene["shots"])
    plan = (plan_shot(root, production, args.scene, args.block, seed=args.seed, rate=rate) if single
            else plan_block(root, production, args.scene, args.block, seed=args.seed, rate=rate))
    if args.json and args.dry_run:
        print(json.dumps(plan.public_dict(root), indent=2, ensure_ascii=False))
        return 0
    print(f"{plan.scene} block {plan.block}: {', '.join(plan.shots)}, {plan.seconds} s, seed {plan.seed}")
    print(f"  starts from {plan.image.relative_to(root)}")
    for guide in plan.guides:
        print(f"  guide at frame {guide.frame:4}: {guide.path.relative_to(root)} ({guide.role})")
    for note in plan.notes:
        print(f"  note: {note}")
    print(f"  estimate US$ {plan.estimate_usd:.3f}; spent US$ {spend.spent():.2f} of US$ {spend.load().get('limit_usd') or 0:.2f}")
    print("\n" + plan.prompt + "\n")
    if args.dry_run:
        print("Nothing was sent (--dry-run).")
        return 0
    manager = JobManager()
    try:
        target = {"shot": plan.block} if single else {"block": plan.block}
        job = manager.submit("generate_block", root, {"scene": plan.scene, **target, "seed": plan.seed})
        try:
            job = manager.wait(job["id"])
        except KeyboardInterrupt:
            manager.cancel(job["id"])
            job = manager.wait(job["id"])
        if job["state"] != "succeeded":
            print(f"generate {job['state']}: {job.get('error') or job['message']}  (job {job['id']})", file=sys.stderr)
            return 1
        job = manager.adopt(job["id"])
    finally:
        manager.shutdown()
    summary = job["result"]["summary"]
    print(f"Made {summary['clip']} for US$ {summary['cost_usd']:.3f} (estimated {summary['estimate_usd']:.3f}).")
    print(f"Slice it: toast slice {args.project} {plan.scene} {plan.block} --clip {summary['clip'].rsplit('/', 1)[-1]}")
    return 0


def _show_run(run: dict) -> None:
    marks = {"done": "✓", "skipped": "–", "running": "…", "waiting": "?", "failed": "✗", "pending": " "}
    print(f"{run['id']}  block {run['subject']['block']} of {run['subject']['scene']}: {run['state']}")
    for step in run["steps"]:
        detail = step.get("note") or ", ".join(step.get("outputs") or [])
        print(f"  [{marks.get(step['state'], ' ')}] {step['label']:28} {step['state']:8} {detail}")


def _drive(root: Path, scene_id: str, act) -> int:
    """Run a workflow command in this process and stay while its jobs run.

    The workflow moves inside the runtime that owns its jobs; here that is
    this command, until the run waits for a person, ends, or Ctrl+C.
    """

    import time

    from .commands import dispatch
    from .jobs import JobManager
    from .project import scene_directory
    from .state import load_scene_state
    from .workflows import attach

    manager = JobManager()
    attach(manager)
    try:
        run_id = act(dispatch)
        while True:
            run = load_scene_state(scene_directory(root, scene_id), scene_id).workflows[run_id]
            if run["state"] != "running":
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("Stopped here; the run continues from where it is: toast workflow resume", file=sys.stderr)
        return 130
    finally:
        manager.shutdown()
    _show_run(run)
    gate = next((step.get("gate") for step in run["steps"] if step["state"] == "waiting"), None)
    if gate:
        state = load_scene_state(scene_directory(root, scene_id), scene_id)
        print(f"\nWaiting for a person: gate {gate}. Candidates:")
        for path in state.gates[gate]["candidates"]:
            print(f"  {path}")
        print(f"Decide: toast gate decide {root} {scene_id} {gate} --approve <path> | --changes | --reject")
    return 0 if run["state"] in ("waiting", "done") else 1


def command_workflow(args: argparse.Namespace) -> int:
    """The built-in workflow: picture, a person's approval, video, takes (SPEC-0009)."""

    from .project import scene_directory
    from .state import load_scene_state

    root = Path(args.project).expanduser().resolve()
    actor = {"id": args.actor, "kind": "human"}
    if args.workflow_command == "list":
        scenes = [args.scene] if args.scene else [scene["id"] for scene in load_production(root)["scenes"]]
        for scene_id in scenes:
            for run in load_scene_state(scene_directory(root, scene_id), scene_id).workflows.values():
                _show_run(run)
        return 0
    if args.workflow_command == "start":
        def act(dispatch):
            before = set(load_scene_state(scene_directory(root, args.scene), args.scene).workflows)
            scene = next(item for item in load_production(root)["scenes"] if item["id"] == args.scene)
            blocks = {block["id"] for block in scene.get("blocks") or []}
            target = {"block": args.block} if args.block in blocks else {"shot": args.block}
            dispatch(root, "start_workflow", {"scene_id": args.scene, **target, "actor": actor})
            after = load_scene_state(scene_directory(root, args.scene), args.scene).workflows
            return next(run_id for run_id in after if run_id not in before)
        return _drive(root, args.scene, act)
    command = "resume_workflow" if args.workflow_command == "resume" else "cancel_workflow"

    def act(dispatch):
        dispatch(root, command, {"scene_id": args.scene, "workflow_id": args.workflow, "actor": actor})
        return args.workflow
    return _drive(root, args.scene, act)


def command_gate(args: argparse.Namespace) -> int:
    """Decide a human gate: approve one candidate, ask for another, or reject (SPEC-0009)."""

    from .project import scene_directory
    from .state import load_scene_state

    root = Path(args.project).expanduser().resolve()
    state = load_scene_state(scene_directory(root, args.scene), args.scene)
    gate = state.gates.get(args.gate)
    if gate is None:
        raise SystemExit(f"No gate {args.gate} in {args.scene}")
    outcome = "approved" if args.approve else "changes_requested" if args.changes else "rejected"

    def act(dispatch):
        dispatch(root, "decide_gate", {"scene_id": args.scene, "gate_id": args.gate, "outcome": outcome,
                                        "chosen": args.approve or "", "rationale": args.why,
                                        "reasons": args.reason or [],
                                        "actor": {"id": args.actor, "kind": "human"}})
        return gate["workflow"]
    return _drive(root, args.scene, act)


def command_backlot(args: argparse.Namespace) -> int:
    """Locations shared across productions: list, pin a copy, see what moved (SPEC-0010)."""

    from .locations import backlot, pin, status

    if args.backlot_command == "list":
        offered = backlot()
        if not offered:
            print("The backlot is empty (set CINE_TOASTER_BACKLOT to one or more folders of locations).")
        for location in offered.values():
            print(f"{location['id']:22} {location['label']:30} {location['source']}")
        return 0
    root = Path(args.project).expanduser().resolve()
    if args.backlot_command == "pin":
        record = pin(root, args.location, update=args.update)
        print(f"Pinned {record['id']} into {record['directory']} (digest {record['digest']})")
        return 0
    for item in status(root):
        state = ("the backlot moved on (pin --update to take it)" if item["backlot_moved_on"]
                 else "up to date" if item["in_backlot"] else "no longer in the backlot")
        print(f"{item['id']:22} {state}{'; edited in this production' if item['edited_here'] else ''}")
    return 0


def command_moves(args: argparse.Namespace) -> int:
    """The camera-move catalog (CT-0027)."""

    from .camera_moves import list_moves

    moves = list_moves(Path(args.project).expanduser().resolve() if args.project else None)
    if args.json:
        print(json.dumps(moves, indent=2, ensure_ascii=False))
        return 0
    category = ""
    for move in moves:
        if move["category"] != category:
            category = move["category"]
            print(f"\n{category}")
        implied = move["implies"]
        geometry = f"{implied['kind']} {implied['direction']}".strip() or "(not in the plan)"
        print(f"  {move['id']:18} {move['name']:18} {geometry:14} {move['says']}")
    return 0


def command_storyboard(args: argparse.Namespace) -> int:
    """The phase gate: approve a scene's storyboard as what will be produced, or reopen it."""

    from .commands import dispatch

    root = Path(args.project).expanduser().resolve()
    command = "approve_storyboard" if args.storyboard_command == "approve" else "reopen_storyboard"
    result = dispatch(root, command, {"scene_id": args.scene, "rationale": args.why,
                                      "actor": {"id": args.actor, "kind": "human"}})
    phase = next(item for item in load_production(root)["scenes"] if item["id"] == args.scene)["phase"]
    print(f"{result.type}: {args.scene} is now {'in production' if phase['phase'] == 'production' else 'fitting its storyboard'}"
          f" (revision {result.revision})")
    return 0


def command_cut(args: argparse.Namespace) -> int:
    """Decide the cut into a shot, over what the breakdown says; or return to it (plan step 13)."""

    from .commands import dispatch

    root = Path(args.project).expanduser().resolve()
    payload = {"scene_id": args.scene, "shot_id": args.shot, "rationale": args.why,
               "actor": {"id": args.actor, "kind": "human"}}
    if args.cut_command == "clear":
        result = dispatch(root, "clear_cut", payload)
    else:
        transition = {"id": args.transition, "duration_ms": args.ms, "reason": args.transition_why} if args.transition else None
        payload["cut"] = {"type": args.type, "chain": "frame" if args.chain else "", "reason": args.reason,
                          "transition": transition}
        result = dispatch(root, "set_cut", payload)
    cut = next(item for item in load_production(root)["scenes"] if item["id"] == args.scene)
    record = next((item for item in cut["cuts"] if item["to"] == args.shot), {})
    print(f"{result.type}: into {args.shot} is now {record.get('type', 'hard')}"
          + (f" with {record['transition']['id']}" if record.get("transition") else "")
          + f" (revision {result.revision})")
    for finding in record.get("findings") or []:
        print(f"  {finding['severity']}: {finding['message']}")
    return 0


def command_reference(args: argparse.Namespace) -> int:
    """Decide what a shot's picture is made from, over the breakdown; or return to it (CT-0046)."""

    from .commands import dispatch

    root = Path(args.project).expanduser().resolve()
    payload = {"scene_id": args.scene, "shot_id": args.shot, "rationale": args.why,
               "actor": {"id": args.actor, "kind": "human"}}
    if args.reference_command == "clear":
        result = dispatch(root, "clear_reference", payload)
    else:
        payload["from"] = args.made_from
        if args.cast is not None:
            payload["with"] = [name.strip() for name in args.cast.split(",") if name.strip()]
        result = dispatch(root, "set_reference", payload)
    scene = next(item for item in load_production(root)["scenes"] if item["id"] == args.scene)
    shot = next(item for item in scene["shots"] if item["id"] == args.shot)
    made = ", ".join(dict.fromkeys(str(item.get("ref")) for item in shot.get("from") or [])) or "nothing"
    faces = ", ".join((shot.get("derive") or {}).get("with") or [])
    print(f"{result.type}: {args.shot} is made from {made}" + (f", with {faces}" if faces else "")
          + f" (revision {result.revision})")
    return 0


def command_picture(args: argparse.Namespace) -> int:
    """A master picture made by editing its source with the cast, within the budget."""

    from . import spend
    from .jobs import _picture_plan
    from .providers.runpod import load_credentials

    root = Path(args.project).expanduser().resolve()
    if args.env_file:
        load_credentials(Path(args.env_file).expanduser())  # never printed
    plan, _, _ = _picture_plan(root, {"scene": args.scene, "shot": args.shot, "seed": args.seed})
    if args.json and args.dry_run:
        print(json.dumps(plan.public_dict(root), indent=2, ensure_ascii=False))
        return 0
    from .pictures import relative

    print(f"{plan.scene} {plan.shot}: edit {relative(root, plan.source)} at {plan.size[0]}x{plan.size[1]}, seed {plan.seed}")
    for ref in plan.references:
        print(f"  identity: {ref['member']}" + (f" ({ref['variant']})" if ref["variant"] else "")
              + f" from {relative(root, ref['path'])}")
    for note in plan.notes:
        print(f"  note: {note}")
    print(f"  estimate US$ {plan.estimate_usd:.3f}; spent US$ {spend.spent():.2f} of US$ {spend.load().get('limit_usd') or 0:.2f}")
    print("\n" + plan.prompt + "\n")
    if args.dry_run:
        print("Nothing was sent (--dry-run).")
        return 0
    from .jobs import JobManager

    manager = JobManager()
    try:
        job = manager.submit("derive_picture", root, {"scene": plan.scene, "shot": plan.shot, "seed": plan.seed})
        try:
            job = manager.wait(job["id"])
        except KeyboardInterrupt:
            manager.cancel(job["id"])
            job = manager.wait(job["id"])
        if job["state"] != "succeeded":
            print(f"picture {job['state']}: {job.get('error') or job['message']}  (job {job['id']})", file=sys.stderr)
            return 1
        job = manager.adopt(job["id"])
    finally:
        manager.shutdown()
    summary = job["result"]["summary"]
    print(f"Made {summary['picture']} for US$ {summary['cost_usd']:.3f}; edges kept from the source: "
          f"{summary['edge_score']} (under 17: recomposed). A moved subject can still score well: look at it.")
    return 0


def command_revoice(args: argparse.Namespace) -> int:
    """A take's speech in the cast member's own voice, as a new take (CT-0040)."""

    from .jobs import JobManager
    from .voice import plan_conversion

    root = Path(args.project).expanduser().resolve()
    if args.in_cut or args.take_sound:
        from .commands import dispatch

        result = dispatch(root, "set_voice", {"scene_id": args.scene, "shot_id": args.shot, "converted": bool(args.in_cut),
                                              "rationale": args.why, "actor": {"id": args.actor, "kind": "human"}})
        print(f"{result.type}: {args.shot} is heard "
              + ("in the cast's own voices in every version assembled from now on"
                 if args.in_cut else "with its take's own sound") + f" (revision {result.revision})")
        return 0
    plan = plan_conversion(root, load_production(root), args.scene, args.shot, args.take or "")
    for item in plan.speakers:
        print(f"{plan.scene} {plan.shot} take {plan.take}: {item['who']}'s voice -> {item['reference'].relative_to(root)}")
    if len(plan.speakers) > 1:
        print(f"  who speaks when: the {len(plan.lines)} declared lines aligned to "
              + (f"the words in {plan.words.name} (or heard from the take, if it leaves a line out)"
                 if plan.words else "words heard from the take"))
    if args.dry_run:
        print("Nothing was converted (--dry-run).")
        return 0
    manager = JobManager()
    try:
        job = manager.submit("convert_voice", root, {"scene": plan.scene, "shot": plan.shot, "take": plan.take})
        try:
            job = manager.wait(job["id"])
        except KeyboardInterrupt:
            manager.cancel(job["id"])
            job = manager.wait(job["id"])
        if job["state"] != "succeeded":
            print(f"voice {job['state']}: {job.get('error') or job['message']}  (job {job['id']})", file=sys.stderr)
            return 1
        job = manager.adopt(job["id"])
    finally:
        manager.shutdown()
    summary = job["result"]["summary"]
    similarity = summary.get("similarity") or {}
    print(f"Made {summary['media']}"
          + (f"; likeness to the reference {similarity['before']} -> {similarity['after']}" if similarity else ""))
    for who, measured in (summary.get("similarity_by_speaker") or {}).items():
        if measured and len(plan.speakers) > 1:
            print(f"  {who}: likeness {measured['before']} -> {measured['after']}")
    for who in summary.get("unplaced") or []:
        print(f"  {who} was not heard in this take; whatever they say in it was converted to another speaker's voice", file=sys.stderr)
    return 0


def command_assemble_sequence(args: argparse.Namespace) -> int:
    """Assemble a new version of a sequence from its scenes' versions, as a job."""

    from .jobs import JobManager

    manager = JobManager()
    try:
        job = manager.wait(manager.submit("assemble_sequence", args.project, {
            "sequence": args.sequence, "version": args.version or "", "summary": args.summary or ""})["id"])
        if job["state"] != "succeeded":
            print(f"assemble {job['state']}: {job.get('error') or job['message']}  (job {job['id']})", file=sys.stderr)
            return 1
        job = manager.adopt(job["id"])
    finally:
        manager.shutdown()
    summary = job["result"]["summary"]
    print(f"{args.sequence} {job['params']['version']}: {summary['duration_seconds']:.1f} s -> {job['message'].removeprefix('Adopted: ')}")
    for scene, version in summary["scenes"].items():
        print(f"  {scene:8} version {version}")
    for note in summary["notes"]:
        print(f"  note: {note}")
    return 0


def command_cast(args: argparse.Namespace) -> int:
    """The production's cast sheets, or drafts of them from what the scenes say (SPEC-0003)."""

    from .cast import propose
    from .project import _read_yaml, scene_files

    root = Path(args.project).expanduser().resolve()
    if args.cast_command == "propose":
        documents = []
        for path in scene_files(root):
            document = _read_yaml(path) or {}
            documents.append((str(document.get("scene") or document.get("cena") or path.parent.name), document))
        drafts = propose(documents)
        if not drafts:
            print("The scenes describe no characters or voices to draft from.")
            return 0
        print("Drafts only: nothing was written. Where scenes disagree, every version is listed.\n")
        for key, draft in sorted(drafts.items()):
            print(f"{key}  (cast/{key.lower()}/character.yaml)")
            for label, versions in (("description", draft["descriptions"]), ("voice", draft["voices"]),
                                    ("sheet chosen", draft["sheets"])):
                if not versions:
                    continue
                marker = "  <- differs across scenes" if len(versions) > 1 else ""
                print(f"  {label}:{marker}")
                for text, scenes in sorted(versions.items(), key=lambda item: -len(item[1])):
                    print(f"    [{', '.join(scenes)}] {text[:150]}")
            print()
        return 0
    production = load_production(root)
    if not production["cast"]:
        print("No cast sheets (cast/<id>/character.yaml). Try: toast cast propose", args.project)
        return 0
    for member in production["cast"].values():
        voice = (member.get("voice") or {}).get("described") or "no voice declared"
        master = next((ref for ref in member["references"] if ref["role"] == "master"), None)
        print(f"{member['id']:12} {member['label']:20} decides {', '.join(member['authoritative_for'])}")
        print(f"             voice: {voice}")
        print(f"             master: {master['path'] if master else '-'}"
              + (f"; variants: {', '.join(member['variants'])}" if member["variants"] else ""))
        for problem in member["problems"]:
            print(f"             problem: {problem}")
    return 0


def command_costs(args: argparse.Namespace) -> int:
    """Generation time and estimated cost, from the providers' job records."""

    from .costs import production_costs
    from .project import _read_yaml

    root = Path(args.project).expanduser().resolve()
    production = load_production(root)
    manifest = _read_yaml(root / "project.yaml")
    report = production_costs(production, manifest.get("generation_rates") or {})
    if args.json:
        print(json.dumps(report, indent=2))
        return 0
    for scene in report["scenes"]:
        if scene["jobs"]:
            print(f"  {scene['scene']:8} {scene['jobs']:4} generation(s)  {scene['seconds'] / 60:7.1f} min  ~US$ {scene['usd']:8.2f}")
    print(f"Total: {report['seconds'] / 60:.1f} GPU minutes, ~US$ {report['usd']:.2f}"
          + (f"  (rate assumed: US$ {report['assumed_rate_usd_per_hour']}/h; declare generation_rates in project.yaml)"
             if report["rate"] == "assumed" else ""))
    return 0


def command_jobs(args: argparse.Namespace) -> int:
    """Background work: list, inspect, cancel, retry, adopt (SPEC-0008)."""

    from .jobs import JobManager, public_job
    from .project import load_production

    manager = JobManager()
    try:
        if args.jobs_command == "list":
            project_id = load_production(args.project)["id"] if args.project else None
            jobs = manager.list(project_id=project_id, limit=args.limit)
            if args.json:
                print(json.dumps([public_job(job) for job in jobs], indent=2))
            for job in [] if args.json else jobs:
                params = " ".join(f"{k}={v}" for k, v in job["params"].items())
                adopted = "  adopted" if job["adopted_at"] else ""
                print(f"{job['id']}  {job['state']:<11} {job['progress']:4.0%}  {job['kind']:<7} "
                      f"{job['project_id']}  {params}{adopted}")
            if not jobs and not args.json:
                print("No jobs.")
            return 0
        if args.jobs_command == "show":
            job = manager.get(args.job)
        elif args.jobs_command == "cancel":
            job = manager.cancel(args.job)
        elif args.jobs_command == "retry":
            job = manager.retry(args.job)
        else:
            job = manager.adopt(args.job, overwrite=args.overwrite)
        print(json.dumps(public_job(job), indent=2))
        return 0
    finally:
        manager.shutdown(wait=False)


def command_voice(args: argparse.Namespace) -> int:
    """Speak the lines the production has already cast and placed."""

    from .providers.piper import DEFAULT_VOICE, VOICES_DIRECTORY, PiperNarration

    root = args.project.expanduser().resolve()
    production = load_production(root)

    pending: list[tuple[str, str, dict]] = []
    for scene in production["scenes"]:
        if args.scene and scene["id"] != args.scene:
            continue
        for shot in scene["shots"]:
            for line in shot["lines"]:
                target = (line.get("mix") or {}).get("file")
                if not target:
                    continue
                pending.append((scene["id"], shot["id"], {**line, "target": target}))

    if not pending:
        print("No lines with a mix destination. Nothing to speak.")
        return 0

    narrator = PiperNarration(root / VOICES_DIRECTORY, args.voice or DEFAULT_VOICE)
    made = 0
    for scene_id, shot_id, line in pending:
        destination = root / line["target"]
        if destination.is_file() and not args.force:
            print(f"  keep   {line['target']}  (exists; --force to remake)")
            continue
        if destination.suffix.lower() != ".wav":
            print(
                f"  refuse {line['target']}  "
                f"offline narration writes WAV; declare a .wav file"
            )
            continue
        text = line.get("en") or line.get("text") or ""
        result = narrator.speak(text=text, output=destination)
        made += 1
        print(
            f"  spoke  {scene_id} {shot_id}  {result.duration_seconds:.1f}s  "
            f"{result.media.relative_to(root)}  [{result.model}]"
        )
    print(f"\n{made} line(s) spoken, {len(pending) - made} not made. Cost: $0.00, offline.")
    return 0


def command_doctor(args: argparse.Namespace) -> int:
    """Say what works on this machine, and what to type for what does not."""

    from . import doctor

    capabilities = doctor.examine()
    if args.json:
        print(json.dumps([item.public_dict() for item in capabilities], indent=2))
    else:
        print(doctor.report(capabilities))
    return 1 if doctor.blocked(capabilities) else 0


def command_check(args: argparse.Namespace) -> int:
    """Read the scene grammar before anything is generated."""

    production = load_production(args.project)
    scenes = production["scenes"]
    if args.scene:
        scenes = [scene for scene in scenes if scene["id"] == args.scene]

    findings = [
        {**finding, "scene_title": scene["title"]}
        for scene in scenes
        for finding in scene["findings"]
    ]
    if args.json:
        print(json.dumps(findings, ensure_ascii=False, indent=2))
    elif not findings:
        checked = len([scene for scene in scenes if scene["geometry"]["cameras"]])
        print(f"No continuity problems found in {checked} scene(s) with geometry.")
    else:
        for finding in findings:
            print(f"{finding['severity'].upper()}  {finding['scene_id']}  {finding['code']}")
            print(f"  {finding['message']}")
            if finding["shots"]:
                print(f"  shots: {', '.join(finding['shots'])}")
            print()
    return 1 if any(finding["severity"] == "error" for finding in findings) else 0


def command_brief(args: argparse.Namespace) -> int:
    """Derive a scene's generation brief from its records (plan step 4)."""

    from .brief import production_brief, take_review

    found = production_brief(args.project.expanduser().resolve(), args.scene)
    if found is None:
        print(f"No scene {args.scene!r}.", file=sys.stderr)
        return 1
    scene, brief = found
    if args.review:
        review = take_review(scene, brief, args.review, args.take)
        if review is None:
            print(f"{args.scene} {args.review} has no take with a video.", file=sys.stderr)
            return 1
        text = json.dumps(review, indent=2, ensure_ascii=False)
        if args.output:
            args.output.write_text(text + "\n", encoding="utf-8")
            print(f"Wrote {args.output} (review of {review['take']}: {len(review['cues'])} cue(s), video {review['video']})")
        else:
            print(text)
        return 0
    if args.json:
        print(json.dumps(brief.public_dict(), indent=2, ensure_ascii=False))
    else:
        print(brief.text(), end="")
        missing = brief.missing()
        if missing:
            print(f"\n{len(missing)} slot(s) missing: " + ", ".join(
                f"{slot.shot + ' ' if slot.shot else ''}{slot.tag}" for slot in missing), file=sys.stderr)
    return 0


def command_previs(args: argparse.Namespace) -> int:
    """Render a shot's light previs to video, as a job (CT-0029, SPEC-0008)."""

    job = _foreground_job("previs", args.project, {"scene": args.scene, "shot": args.shot}, args.output)
    if job is None:
        return 1
    summary = job["result"]["summary"]
    print(f"Wrote {job['message'].removeprefix('Adopted: ')} ({summary['frames']} frames, "
          f"{summary['duration_seconds']:g} s, job {job['id']})")
    return 0


def command_frame(args: argparse.Namespace) -> int:
    """Draw what a shot's camera sees, from the scene geometry (CT-0025)."""

    from .blocking import blocking_frame, public_frame, render_svg
    from .project import load_scene

    scene = load_scene(args.project.expanduser().resolve(), args.scene)
    if scene is None:
        print(f"No scene {args.scene!r}.", file=sys.stderr)
        return 1
    shot = next((item for item in scene["shots"] if item["id"] == args.shot), None)
    try:
        frame = blocking_frame(scene, shot, args.at) if shot else None
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2
    if frame is None:
        print(f"{args.scene} {args.shot} has no camera pose to look from.", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(public_frame(frame), indent=2))
    elif args.output:
        args.output.write_text(render_svg(frame), encoding="utf-8")
        print(f"Wrote {args.output}")
    else:
        print(render_svg(frame))
    return 0


def command_fdx(args: argparse.Namespace) -> int:
    """Final Draft interchange: import to a new Fountain file, export a derived .fdx (ADR 0014)."""

    from .fdx import export_fdx, import_fdx

    if args.script_command == "import-fdx":
        if args.output.exists():
            print(f"{args.output} exists. Import writes a new screenplay and never overwrites one.",
                  file=sys.stderr)
            return 1
        try:
            result = import_fdx(args.source.read_text(encoding="utf-8"))
        except ValueError as error:
            print(str(error), file=sys.stderr)
            return 1
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result.text, encoding="utf-8")
        print(f"Wrote {args.output}")
    else:
        production = load_production(args.project)
        from .project import screenplay_text

        script_path = production.get("script_path")
        if not production.get("script_files"):
            print(production.get("script_problem") or "This production has no screenplay to export.", file=sys.stderr)
            return 1
        result = export_fdx(screenplay_text(Path(args.project).expanduser().resolve(), production["script_files"]))
        args.output.write_text(result.text, encoding="utf-8")
        print(f"Wrote {args.output} from {script_path} (derived; never edit it as the screenplay)")
    print(result.report())
    return 0


def command_script(args: argparse.Namespace) -> int:
    """Show what each shot covers of the screenplay, or propose the links (SPEC-0006)."""

    from . import screenplay as script_model
    from .project import _read_screenplay

    production = load_production(args.project)
    scenes = production["scenes"]
    if args.scene:
        scenes = [scene for scene in scenes if scene["id"] == args.scene]

    if args.script_command == "show":
        for scene in scenes:
            link = scene["script"]
            if not link:
                print(f"{scene['id']}  not linked to the screenplay")
                continue
            print(f"{scene['id']}  {link['heading']}" + (f"  (occurrence {link['occurrence']})" if link["occurrence"] > 1 else ""))
            for shot in scene["shots"]:
                covered = shot.get("script")
                if not covered:
                    print(f"  {shot['id']}  covers nothing")
                    continue
                print(f"  {shot['id']}")
                # In screenplay order, the way the shot will play.
                for unit in covered["units"]:
                    if unit["kind"] == "speech":
                        extension = f" ({unit['extension']})" if unit["extension"] else ""
                        print(f"      {unit['speaker']}{extension}: {unit['text']}")
                    elif unit["kind"] != "heading":
                        print(f"      {unit['text']}")
            uncovered = [unit for unit in link["units"] if unit["kind"] == "speech" and not unit["shots"]]
            for unit in uncovered:
                print(f"  (uncovered) {unit['speaker']}: {unit['text']}")
        return 0

    screenplay = _read_screenplay(Path(args.project).expanduser().resolve(), production["script_files"])
    if screenplay is None:
        print("This production has no screenplay to link to.")
        return 1
    proposals = 0
    for scene in scenes:
        link = scene["script"]
        if link and link["linked"]:
            target = screenplay.find_scene(link["heading"], link["occurrence"])
        else:
            guess = script_model.suggest_scene(screenplay, scene["shots"])
            if guess is None:
                continue
            target, hits = guess
            proposals += 1
            print(f"{scene['id']}: {hits} line(s) match screenplay scene {target.heading!r}")
            print("  script:")
            print(f"    heading: {target.heading}")
            if target.occurrence > 1:
                print(f"    occurrence: {target.occurrence}")
        for suggestion in script_model.suggest_links(target, scene["shots"]):
            proposals += 1
            certainty = "exact" if suggestion["exact"] else "approximate"
            print(
                f"{scene['id']} {suggestion['shot_id']}: {suggestion['matched']}/{suggestion['lines']} "
                f"line(s) matched ({certainty})"
            )
            print("  covers:")
            print(f"    from: {json.dumps(suggestion['from'], ensure_ascii=False)}")
            print(f"    to: {json.dumps(suggestion['to'], ensure_ascii=False)}")
    if not proposals:
        print("Nothing to propose: every shot with lines is already linked, or no lines match.")
    else:
        print("\nThese are suggestions. Nothing was written; paste what you accept into the breakdown.")
    return 0


def command_events(args: argparse.Namespace) -> int:
    events = tail_events(args.project, limit=args.limit)
    if args.json:
        print(json.dumps(events, ensure_ascii=False, indent=2))
        return 0
    if not events:
        print("No recorded activity for this project yet.")
        return 0
    for event in events:
        payload = event.get("payload", {})
        detail = " ".join(
            f"{key}={value}"
            for key, value in payload.items()
            if key in {"scene_id", "shot_id", "take_id", "revision"}
        )
        print(f"{event['occurred_at']}  {event['type']}  {detail}")
    return 0


def command_knowledge(args: argparse.Namespace) -> int:
    """Show what the production has learned and what the software enforces."""

    project = args.project if args.project and Path(args.project).is_dir() else None
    practices = load_practices(project)
    providers = load_providers(project)
    report = coverage(project)

    if args.json:
        print(
            json.dumps(
                {
                    "coverage": report.public_dict(),
                    "practices": [practice.public_dict() for practice in practices],
                    "providers": [profile.public_dict() for profile in providers],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.show:
        practice = next((item for item in practices if item.id == args.show), None)
        if practice is None:
            print(f"No practice with id {args.show!r}", file=sys.stderr)
            return 2
        print(f"{practice.title}  [{practice.status}]")
        if practice.learned_on:
            print(f"Learned: {practice.learned_on}")
        if practice.cost:
            print(f"Cost:    {practice.cost}")
        print(f"Checked: {', '.join(practice.enforced_by) or 'no — depends on a person'}")
        for reference in practice.evidence:
            print(f"Evidence: {reference}")
        print()
        print(practice.body)
        return 0

    print(f"PRACTICES  {report.enforced}/{report.practices} enforced by a check "
          f"({report.percentage}%)")
    for practice in practices:
        marker = "checked" if practice.enforced else "      -"
        print(f"  {marker}  {practice.id:34} {practice.domain:12} {practice.title}")
    if report.unenforced:
        print()
        print("  Still depends on a person remembering:")
        for practice_id in report.unenforced:
            print(f"    {practice_id}")
    if report.checks_without_practice:
        print()
        print("  Checks with no recorded reasoning behind them:")
        for code in report.checks_without_practice:
            print(f"    {code}")

    if providers:
        print()
        print(f"PROVIDER PROFILES  {report.measured_claims}/{report.claims} claims measured")
        for profile in providers:
            version = f" {profile.version}" if profile.version else ""
            print(f"  {profile.id}{version}  ({len(profile.claims)} claims, {profile.origin})")
            for claim in profile.claims:
                when = f" {claim.measured_on}" if claim.measured_on else ""
                print(f"    [{claim.status}{when}] {claim.claim}")
    return 0


def command_why(args: argparse.Namespace) -> int:
    """Explain a finding: the rule behind it and what ignoring it has cost."""

    project = args.project if args.project and Path(args.project).is_dir() else None
    practices = practices_for_check(args.code, project)
    if args.json:
        print(json.dumps([practice.public_dict() for practice in practices], ensure_ascii=False, indent=2))
        return 0
    if not practices:
        print(f"No recorded reasoning for check {args.code!r}.")
        return 0
    for practice in practices:
        print(f"{practice.title}  [{practice.status}]")
        if practice.cost:
            print(f"Cost: {practice.cost}")
        print()
        print(practice.body)
        print()
    return 0


def _scene_or_fail(args: argparse.Namespace) -> dict[str, object]:
    production = load_production(args.project)
    scene = next(
        (item for item in production["scenes"] if item["id"] == args.scene), None
    )
    if scene is None:
        raise SystemExit(f"Scene not found: {args.scene}")
    return scene


def command_version_list(args: argparse.Namespace) -> int:
    scene = _scene_or_fail(args)
    assemblies = scene["assemblies"]
    if args.json:
        print(json.dumps(assemblies, ensure_ascii=False, indent=2))
        return 0
    if not assemblies:
        print("No versions recorded for this scene yet.")
        return 0
    print(f"{scene['id']}  {scene['title']}  (revision {scene['revision']})")
    for assembly in assemblies:
        mark = "APPROVED" if assembly["verdict"] == "approved" else assembly["verdict"].upper()
        when = assembly["created_at"][:16].replace("T", " ")
        duration = f"{assembly['duration_seconds']:.0f}s" if assembly["duration_seconds"] else "—"
        print(f"  {assembly['id']:8} {when}  {duration:>6}  {mark}")
        if assembly["summary"]:
            print(f"           {assembly['summary']}")
        if assembly["note"]:
            print(f"           note: {assembly['note']}")
    return 0


def command_version_record(args: argparse.Namespace) -> int:
    result = record_assembly(
        args.project,
        scene_id=args.scene,
        assembly_id=args.version,
        actor=_resolve_actor(args),
        media=args.media or "",
        summary=args.summary or "",
        duration_seconds=args.duration or 0.0,
        expected_revision=args.expect_revision,
    )
    print(f"Recorded version {args.version} of {args.scene} -> revision {result.revision}")
    return 0


def command_version_review(args: argparse.Namespace) -> int:
    result = review_assembly(
        args.project,
        scene_id=args.scene,
        assembly_id=args.version,
        verdict=args.verdict,
        actor=_resolve_actor(args),
        note=args.note,
        expected_revision=args.expect_revision,
    )
    print(f"{args.version} marked {args.verdict} -> revision {result.revision}")
    return 0


def command_version_restore(args: argparse.Namespace) -> int:
    result = restore_assembly(
        args.project,
        scene_id=args.scene,
        assembly_id=args.version,
        actor=_resolve_actor(args),
        rationale=args.rationale,
        expected_revision=args.expect_revision,
    )
    print(
        f"Selections restored from {args.version} -> revision {result.revision}. "
        "The version itself is unchanged."
    )
    return 0


def command_version_diff(args: argparse.Namespace) -> int:
    """Answer the question a director asks about two cuts."""

    scene = _scene_or_fail(args)
    by_id = {assembly["id"]: assembly for assembly in scene["assemblies"]}
    missing = [name for name in (args.first, args.second) if name not in by_id]
    if missing:
        print(f"Unknown version(s): {', '.join(missing)}", file=sys.stderr)
        return 2

    first, second = by_id[args.first], by_id[args.second]
    shots = sorted(set(first["takes"]) | set(second["takes"]))
    changes = [
        {"shot_id": shot_id, "from": first["takes"].get(shot_id, ""), "to": second["takes"].get(shot_id, "")}
        for shot_id in shots
        if first["takes"].get(shot_id, "") != second["takes"].get(shot_id, "")
    ]
    if args.json:
        print(json.dumps(changes, ensure_ascii=False, indent=2))
        return 0
    if not changes:
        print(f"{args.first} and {args.second} use the same takes.")
        return 0
    print(f"{args.first} -> {args.second}: {len(changes)} shot(s) changed")
    for change in changes:
        print(f"  {change['shot_id']:12} {change['from'] or '—':>10}  ->  {change['to'] or '—'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="toast",
        description="Operate filesystem-based film productions.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    index_parser = subparsers.add_parser("index", help="Build a disposable project index")
    index_parser.add_argument("project", type=Path)
    index_parser.add_argument("--json", action="store_true")
    index_parser.set_defaults(function=command_index)

    tree_parser = subparsers.add_parser("tree", help="Navigate the indexed project tree")
    tree_parser.add_argument("project", type=Path)
    tree_parser.add_argument("path", nargs="?", default="", help="Relative directory to start at")
    tree_parser.add_argument("--depth", type=int, default=3)
    tree_parser.add_argument("--refresh", action="store_true")
    tree_parser.set_defaults(function=command_tree)

    find_parser = subparsers.add_parser("find", help="Search names, paths, and text files")
    find_parser.add_argument("project", type=Path)
    find_parser.add_argument("query")
    find_parser.add_argument("--kind")
    find_parser.add_argument("--limit", type=int, default=50)
    find_parser.add_argument("--refresh", action="store_true")
    find_parser.add_argument("--json", action="store_true")
    find_parser.set_defaults(function=command_find)

    stats_parser = subparsers.add_parser("stats", help="Show index and project statistics")
    stats_parser.add_argument("project", type=Path)
    stats_parser.add_argument("--refresh", action="store_true")
    stats_parser.add_argument("--json", action="store_true")
    stats_parser.set_defaults(function=command_stats)

    serve_parser = subparsers.add_parser(
        "serve", help="Start the local production control room"
    )
    serve_parser.add_argument("project", type=Path)
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8787)
    serve_parser.add_argument("--no-refresh", action="store_true")
    serve_parser.add_argument("--assistant", action="store_true",
                              help="also run the directing assistant (the agents extra, Node, the Claude CLI; ADR 0018)")
    serve_parser.set_defaults(function=command_serve)

    demo_parser = subparsers.add_parser(
        "demo", help="List or copy a demo production to an external directory"
    )
    demo_parser.add_argument("destination", type=Path, nargs="?")
    demo_parser.add_argument(
        "--template",
        choices=tuple(DEMO_TEMPLATES),
        default=DEFAULT_DEMO_TEMPLATE,
        help=f"Demo template to copy (default: {DEFAULT_DEMO_TEMPLATE})",
    )
    demo_parser.add_argument(
        "--list",
        dest="list_templates",
        action="store_true",
        help="List available demo templates",
    )
    demo_parser.add_argument(
        "--allow-inside-repository",
        action="store_true",
        help="Allow intentional creation inside the Cine Toaster source checkout",
    )
    demo_parser.set_defaults(function=command_demo)

    shots_parser = subparsers.add_parser(
        "shots", help="List shots, registered takes, and the current selection"
    )
    shots_parser.add_argument("project", type=Path)
    shots_parser.add_argument("--scene", help="Limit the listing to one scene id")
    shots_parser.add_argument("--json", action="store_true")
    shots_parser.set_defaults(function=command_shots)

    take_parser = subparsers.add_parser("take", help="Decide between registered alternatives")
    take_actions = take_parser.add_subparsers(dest="take_command", required=True)

    select_parser = take_actions.add_parser("select", help="Adopt one take for a shot")
    select_parser.add_argument("project", type=Path)
    select_parser.add_argument("scene")
    select_parser.add_argument("shot")
    select_parser.add_argument("take")
    select_parser.add_argument("--rationale", default="", help="Why this take was chosen")
    select_parser.add_argument("--actor", help="Who is deciding (default: current user)")
    select_parser.add_argument(
        "--actor-kind", choices=("human", "agent", "system"), default="human"
    )
    select_parser.add_argument(
        "--expect-revision",
        type=int,
        help="Fail instead of overwriting a newer decision",
    )
    select_parser.add_argument("--json", action="store_true")
    select_parser.set_defaults(function=command_take_select)

    clear_parser = take_actions.add_parser("clear", help="Return a shot to undecided")
    clear_parser.add_argument("project", type=Path)
    clear_parser.add_argument("scene")
    clear_parser.add_argument("shot")
    clear_parser.add_argument("--rationale", default="")
    clear_parser.add_argument("--actor")
    clear_parser.add_argument(
        "--actor-kind", choices=("human", "agent", "system"), default="human"
    )
    clear_parser.add_argument("--expect-revision", type=int)
    clear_parser.add_argument("--json", action="store_true")
    clear_parser.set_defaults(function=command_take_clear)

    check_parser = subparsers.add_parser(
        "check", help="Check scene geometry for continuity problems"
    )
    check_parser.add_argument("project", type=Path)
    check_parser.add_argument("--scene")
    check_parser.add_argument("--json", action="store_true")
    check_parser.set_defaults(function=command_check)

    script_parser = subparsers.add_parser(
        "script", help="What each shot covers of the screenplay (SPEC-0006)"
    )
    script_actions = script_parser.add_subparsers(dest="script_command", required=True)
    for name, text in (
        ("show", "Show each shot's covered action and dialogue"),
        ("link", "Propose screenplay links from shots' authored lines; writes nothing"),
    ):
        action = script_actions.add_parser(name, help=text)
        action.add_argument("project", type=Path)
        action.add_argument("--scene")
        action.set_defaults(function=command_script)
    importer = script_actions.add_parser(
        "import-fdx", help="Convert a Final Draft .fdx into a new Fountain file, reporting what is lost"
    )
    importer.add_argument("source", type=Path)
    importer.add_argument("--output", type=Path, required=True, help="the new .fountain file (never overwritten)")
    importer.set_defaults(function=command_fdx)
    exporter = script_actions.add_parser(
        "export-fdx", help="Write the production's screenplay as a derived Final Draft .fdx"
    )
    exporter.add_argument("project", type=Path)
    exporter.add_argument("--output", type=Path, required=True)
    exporter.set_defaults(function=command_fdx)

    brief_parser = subparsers.add_parser(
        "brief", help="Derive a scene's generation brief from its records"
    )
    brief_parser.add_argument("project", type=Path)
    brief_parser.add_argument("scene")
    brief_parser.add_argument("--json", action="store_true", help="slots with their sources")
    brief_parser.add_argument(
        "--review", metavar="SHOT",
        help="write the SceneFlow-shaped review project for this shot's local take",
    )
    brief_parser.add_argument("--take", help="with --review: which take (default: the selected one)")
    brief_parser.add_argument("--output", type=Path)
    brief_parser.set_defaults(function=command_brief)

    previs_parser = subparsers.add_parser(
        "previs", help="Render a shot's light previs (animated blocking frame) to video"
    )
    previs_parser.add_argument("project", type=Path)
    previs_parser.add_argument("scene")
    previs_parser.add_argument("shot")
    previs_parser.add_argument("--output", type=Path, help="default: renders/previs/<scene>-<shot>.mp4 in the project")
    previs_parser.set_defaults(function=command_previs)

    assemble_parser = subparsers.add_parser(
        "assemble", help="Assemble a new, kept version of a scene from its selected takes"
    )
    assemble_parser.add_argument("project", type=Path)
    assemble_parser.add_argument("scene")
    assemble_parser.add_argument("--version", help="default: the next free v<n>")
    assemble_parser.add_argument("--summary", help="what changed in this version")
    assemble_parser.set_defaults(function=command_assemble)

    sequence_parser = subparsers.add_parser(
        "assemble-sequence", help="Assemble a new, kept version of a sequence from its scenes' versions"
    )
    sequence_parser.add_argument("project", type=Path)
    sequence_parser.add_argument("sequence")
    sequence_parser.add_argument("--version")
    sequence_parser.add_argument("--summary")
    sequence_parser.set_defaults(function=command_assemble_sequence)

    cast_parser = subparsers.add_parser("cast", help="Cast sheets: list them, or draft them from the scenes")
    cast_actions = cast_parser.add_subparsers(dest="cast_command", required=True)
    for name, text in (("list", "The cast sheets and their voices"),
                       ("propose", "Draft cast sheets from the scenes' own descriptions; writes nothing")):
        action = cast_actions.add_parser(name, help=text)
        action.add_argument("project", type=Path)
        action.set_defaults(function=command_cast)

    costs_parser = subparsers.add_parser("costs", help="Generation time and estimated cost, from job records")
    costs_parser.add_argument("project", type=Path)
    costs_parser.add_argument("--json", action="store_true")
    costs_parser.set_defaults(function=command_costs)

    backlot_parser = subparsers.add_parser("backlot", help="Locations shared across productions (SPEC-0010)")
    backlot_sub = backlot_parser.add_subparsers(dest="backlot_command", required=True)
    backlot_sub.add_parser("list", help="What the backlot offers (CINE_TOASTER_BACKLOT)")
    backlot_pin = backlot_sub.add_parser("pin", help="Copy a location into the production")
    backlot_pin.add_argument("project", type=Path)
    backlot_pin.add_argument("location")
    backlot_pin.add_argument("--update", action="store_true", help="replace the pinned copy with the backlot's")
    backlot_status = backlot_sub.add_parser("status", help="Pinned locations: moved on in the backlot, edited here")
    backlot_status.add_argument("project", type=Path)
    backlot_parser.set_defaults(function=command_backlot)

    moves_parser = subparsers.add_parser("moves", help="The camera-move catalog: guidance, implied geometry, model words")
    moves_parser.add_argument("project", type=Path, nargs="?", help="include this production's own moves")
    moves_parser.add_argument("--json", action="store_true")
    moves_parser.set_defaults(function=command_moves)

    board_parser = subparsers.add_parser("storyboard", help="Approve a scene's storyboard (the phase gate), or reopen it")
    board_sub = board_parser.add_subparsers(dest="storyboard_command", required=True)
    for name, text in (("approve", "What the storyboard defines will be produced"), ("reopen", "Back to fitting it")):
        item = board_sub.add_parser(name, help=text)
        item.add_argument("project", type=Path)
        item.add_argument("scene")
        item.add_argument("--why", help="kept with the decision")
        item.add_argument("--actor", default=os.environ.get("USER", "director"))
    board_parser.set_defaults(function=command_storyboard)

    cut_parser = subparsers.add_parser("cut", help="Decide the cut into a shot, over the breakdown (plan step 13)")
    cut_sub = cut_parser.add_subparsers(dest="cut_command", required=True)
    for name, text in (("set", "Decide the cut into a shot"), ("clear", "Return to what the breakdown says")):
        item = cut_sub.add_parser(name, help=text)
        item.add_argument("project", type=Path)
        item.add_argument("scene")
        item.add_argument("shot", help="the incoming shot: the cut is the join into it")
        item.add_argument("--why", help="why the decision was made (kept in the history)")
        item.add_argument("--actor", default=os.environ.get("USER", "director"))
        if name == "set":
            from .cuts import CUT_TYPES

            item.add_argument("--type", default="hard", choices=CUT_TYPES)
            item.add_argument("--chain", action="store_true", help="the shot opens on the previous shot's last frame")
            item.add_argument("--reason", default="", help="what the cut does")
            item.add_argument("--transition", help="a catalog transition id, e.g. cross-dissolve")
            item.add_argument("--ms", type=int, help="the transition's duration in milliseconds")
            item.add_argument("--transition-why", default="", help="why this transition")
    cut_parser.set_defaults(function=command_cut)

    reference_parser = subparsers.add_parser(
        "reference", help="Decide what a shot's picture is made from, over the breakdown (CT-0046)")
    reference_sub = reference_parser.add_subparsers(dest="reference_command", required=True)
    for name, text in (("set", "Decide what the shot is made from, and whose faces it takes"),
                       ("clear", "Return to what the breakdown says")):
        item = reference_sub.add_parser(name, help=text)
        item.add_argument("project", type=Path)
        item.add_argument("scene")
        item.add_argument("shot")
        item.add_argument("--why", help="why the decision was made (kept in the history)")
        item.add_argument("--actor", default=os.environ.get("USER", "director"))
        if name == "set":
            item.add_argument("--from", dest="made_from", default="",
                              help="a shot of the scene (number or id), a master, or a picture file")
            item.add_argument("--with", dest="cast", help="a derived picture's cast, comma-separated (empty: none)")
    reference_parser.set_defaults(function=command_reference)

    workflow_parser = subparsers.add_parser(
        "workflow", help="The built-in workflow: picture, a person's approval, video, takes (SPEC-0009)")
    workflow_sub = workflow_parser.add_subparsers(dest="workflow_command", required=True)
    workflow_start = workflow_sub.add_parser("start", help="Start the workflow for a generation block")
    workflow_start.add_argument("project", type=Path)
    workflow_start.add_argument("scene")
    workflow_start.add_argument("block", help="a generation block's id, or a shot outside any block (e.g. P7)")
    workflow_list = workflow_sub.add_parser("list", help="Every run, with its steps")
    workflow_list.add_argument("project", type=Path)
    workflow_list.add_argument("scene", nargs="?")
    for name, text in (("resume", "Move a run on, e.g. after the runtime restarted"), ("cancel", "Stop a run")):
        item = workflow_sub.add_parser(name, help=text)
        item.add_argument("project", type=Path)
        item.add_argument("scene")
        item.add_argument("workflow")
    for item in workflow_sub.choices.values():
        item.add_argument("--actor", default=os.environ.get("USER", "director"), help="who is acting (recorded)")
    workflow_parser.set_defaults(function=command_workflow)

    gate_parser = subparsers.add_parser("gate", help="Decide a human gate (SPEC-0009)")
    gate_sub = gate_parser.add_subparsers(dest="gate_command", required=True)
    gate_decide = gate_sub.add_parser("decide", help="Approve a candidate, ask for another, or reject")
    gate_decide.add_argument("project", type=Path)
    gate_decide.add_argument("scene")
    gate_decide.add_argument("gate")
    choice = gate_decide.add_mutually_exclusive_group(required=True)
    choice.add_argument("--approve", metavar="PATH", help="the candidate approved")
    choice.add_argument("--changes", action="store_true", help="ask for another version")
    choice.add_argument("--reject", action="store_true", help="end the run")
    gate_decide.add_argument("--why", help="the reason, kept with the decision (required to ask again or reject)")
    from .workflows import REJECTION_REASONS

    gate_decide.add_argument("--reason", action="append", choices=REJECTION_REASONS,
                             help="what is wrong (repeatable); counts across scenes and models")
    gate_decide.add_argument("--actor", default=os.environ.get("USER", "director"))
    gate_parser.set_defaults(function=command_gate)

    picture_parser = subparsers.add_parser(
        "picture", help="Make a master picture by editing its source (a render) with the cast, as a new version")
    picture_parser.add_argument("project", type=Path)
    picture_parser.add_argument("scene")
    picture_parser.add_argument("shot")
    picture_parser.add_argument("--seed", type=int, default=1)
    picture_parser.add_argument("--dry-run", action="store_true", help="show the source, the faces and the prompt; send nothing")
    picture_parser.add_argument("--json", action="store_true", help="with --dry-run, the plan as JSON")
    picture_parser.add_argument("--env-file", help="read RUNPOD_API_KEY and RUNPOD_QWEN_ENDPOINT_ID from this file")
    picture_parser.set_defaults(function=command_picture)

    voice_convert = subparsers.add_parser(
        "revoice", help="A take's speech in the cast member's own voice, as a new take (the room is kept)")
    voice_convert.add_argument("project", type=Path)
    voice_convert.add_argument("scene")
    voice_convert.add_argument("shot")
    voice_convert.add_argument("--take", help="which take (default: the selected one, else the first)")
    voice_convert.add_argument("--dry-run", action="store_true", help="say whose voice and which recording; convert nothing")
    in_cut = voice_convert.add_mutually_exclusive_group()
    in_cut.add_argument("--in-cut", action="store_true",
                        help="no new take: decide that the cut hears this shot in the cast's own voices, "
                             "converted when the scene is assembled, whichever take is chosen")
    in_cut.add_argument("--take-sound", action="store_true", help="undo --in-cut: the cut hears the take's own sound")
    voice_convert.add_argument("--why", help="the reason, kept with the decision")
    voice_convert.add_argument("--actor", default=os.environ.get("USER") or "director")
    voice_convert.set_defaults(function=command_revoice)

    budget_parser = subparsers.add_parser("budget", help="What paid generation may spend, and has spent")
    budget_parser.add_argument("--json", action="store_true")
    budget_sub = budget_parser.add_subparsers(dest="budget_command")
    budget_set = budget_sub.add_parser("set", help="Set the ceiling, in US dollars")
    budget_set.add_argument("usd", type=float)
    budget_parser.set_defaults(function=command_budget)

    generate_parser = subparsers.add_parser("generate", help="Generate a block of shots in one paid generation")
    generate_parser.add_argument("project", type=Path)
    generate_parser.add_argument("scene")
    generate_parser.add_argument("block")
    generate_parser.add_argument("--seed", type=int, default=1)
    generate_parser.add_argument("--dry-run", action="store_true", help="show the plan, the prompt and the estimate; send nothing")
    generate_parser.add_argument("--json", action="store_true", help="with --dry-run, the plan as JSON")
    generate_parser.add_argument("--env-file", help="read RUNPOD_API_KEY and RUNPOD_LTX_ENDPOINT_ID from this file")
    generate_parser.set_defaults(function=command_generate)

    slice_parser = subparsers.add_parser(
        "slice", help="Slice a generation block's clip into one take per shot"
    )
    slice_parser.add_argument("project", type=Path)
    slice_parser.add_argument("scene")
    slice_parser.add_argument("block")
    slice_parser.add_argument("--dry-run", action="store_true", help="find and cut, but do not adopt the takes")
    slice_parser.add_argument("--clip", help="which version of the block to slice (e.g. b2-1.mp4); default its own clip")
    slice_parser.set_defaults(function=command_slice)

    jobs_parser = subparsers.add_parser("jobs", help="Background work: list, show, cancel, retry, adopt")
    jobs_actions = jobs_parser.add_subparsers(dest="jobs_command", required=True)
    listing = jobs_actions.add_parser("list", help="Recent jobs, newest first")
    listing.add_argument("project", type=Path, nargs="?", help="only this production's jobs")
    listing.add_argument("--limit", type=int, default=20)
    listing.add_argument("--json", action="store_true")
    listing.set_defaults(function=command_jobs)
    for name, text in (("show", "One job's record"), ("cancel", "Ask a job to stop"),
                       ("retry", "Run a failed, cancelled or interrupted job again"),
                       ("adopt", "Copy a finished job's result into its production")):
        action = jobs_actions.add_parser(name, help=text)
        action.add_argument("job")
        if name == "adopt":
            action.add_argument("--overwrite", action="store_true")
        action.set_defaults(function=command_jobs)

    frame_parser = subparsers.add_parser(
        "frame", help="Draw a shot's blocking frame from the scene geometry, as SVG"
    )
    frame_parser.add_argument("project", type=Path)
    frame_parser.add_argument("scene")
    frame_parser.add_argument("shot")
    frame_parser.add_argument("--at", default="start", help="start, end, or a time through the shot from 0 to 1")
    frame_parser.add_argument("--output", type=Path)
    frame_parser.add_argument("--json", action="store_true", help="the frame's facts instead of the drawing")
    frame_parser.set_defaults(function=command_frame)

    build_parser = subparsers.add_parser(
        "build", help="Render the production's composed shots into a file"
    )
    build_parser.add_argument("project", type=Path)
    build_parser.add_argument("--output", type=Path)
    build_parser.add_argument("--json", action="store_true")
    build_parser.add_argument(
        "--engine", choices=("auto", "gl", "ffmpeg"), default="auto",
        help="gl runs each GLSL transition's own shader; ffmpeg its declared stand-in "
        "(default: gl when a GL context is available)",
    )
    build_parser.set_defaults(function=command_build)

    voice_parser = subparsers.add_parser(
        "voice", help="Speak the production's lines with an offline voice"
    )
    voice_parser.add_argument("project", type=Path)
    voice_parser.add_argument("--scene")
    voice_parser.add_argument("--voice", help="Piper voice id; the default is unremarkable")
    voice_parser.add_argument("--force", action="store_true", help="Remake existing audio")
    voice_parser.set_defaults(function=command_voice)

    doctor_parser = subparsers.add_parser(
        "doctor", help="Report what works on this machine and how to fix what does not"
    )
    doctor_parser.add_argument("--json", action="store_true")
    doctor_parser.set_defaults(function=command_doctor)

    events_parser = subparsers.add_parser("events", help="Show recorded production activity")
    events_parser.add_argument("project", type=Path)
    events_parser.add_argument("--limit", type=int, default=50)
    events_parser.add_argument("--json", action="store_true")
    events_parser.set_defaults(function=command_events)

    knowledge_parser = subparsers.add_parser(
        "knowledge", help="Show recorded practices, provider profiles, and coverage"
    )
    knowledge_parser.add_argument("project", type=Path, nargs="?")
    knowledge_parser.add_argument("--show", help="Print one practice in full")
    knowledge_parser.add_argument("--json", action="store_true")
    knowledge_parser.set_defaults(function=command_knowledge)

    why_parser = subparsers.add_parser(
        "why", help="Explain a check code using the recorded practice behind it"
    )
    why_parser.add_argument("code")
    why_parser.add_argument("project", type=Path, nargs="?")
    why_parser.add_argument("--json", action="store_true")
    why_parser.set_defaults(function=command_why)

    version_parser = subparsers.add_parser(
        "version", help="Assembled versions of a scene and what was thought of them"
    )
    version_actions = version_parser.add_subparsers(dest="version_command", required=True)

    def add_common(parser_: argparse.ArgumentParser) -> None:
        parser_.add_argument("project", type=Path)
        parser_.add_argument("scene")

    list_versions = version_actions.add_parser("list", help="List recorded versions")
    add_common(list_versions)
    list_versions.add_argument("--json", action="store_true")
    list_versions.set_defaults(function=command_version_list)

    record_version = version_actions.add_parser(
        "record", help="Register a rendered version with the takes it contains"
    )
    add_common(record_version)
    record_version.add_argument("version")
    record_version.add_argument("--media", help="Project-relative path to the render")
    record_version.add_argument("--summary", help="What changed in this version")
    record_version.add_argument("--duration", type=float)
    record_version.add_argument("--actor")
    record_version.add_argument(
        "--actor-kind", choices=("human", "agent", "system"), default="human"
    )
    record_version.add_argument("--expect-revision", type=int)
    record_version.set_defaults(function=command_version_record)

    review_version = version_actions.add_parser("review", help="Record a verdict on a version")
    add_common(review_version)
    review_version.add_argument("version")
    review_version.add_argument("verdict", choices=tuple(sorted(ASSEMBLY_VERDICTS)))
    review_version.add_argument("--note", default="")
    review_version.add_argument("--actor")
    review_version.add_argument(
        "--actor-kind", choices=("human", "agent", "system"), default="human"
    )
    review_version.add_argument("--expect-revision", type=int)
    review_version.set_defaults(function=command_version_review)

    restore_version = version_actions.add_parser(
        "restore", help="Roll selections back to the takes a version was built from"
    )
    add_common(restore_version)
    restore_version.add_argument("version")
    restore_version.add_argument("--rationale", default="")
    restore_version.add_argument("--actor")
    restore_version.add_argument(
        "--actor-kind", choices=("human", "agent", "system"), default="human"
    )
    restore_version.add_argument("--expect-revision", type=int)
    restore_version.set_defaults(function=command_version_restore)

    diff_versions = version_actions.add_parser(
        "diff", help="Show which shots changed take between two versions"
    )
    add_common(diff_versions)
    diff_versions.add_argument("first")
    diff_versions.add_argument("second")
    diff_versions.add_argument("--json", action="store_true")
    diff_versions.set_defaults(function=command_version_diff)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.function(args)
    except CineToasterError as error:
        print(f"{error.code}: {error.message}", file=sys.stderr)
        return 3
    except (FileNotFoundError, NotADirectoryError, PermissionError) as error:
        parser.error(str(error))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
