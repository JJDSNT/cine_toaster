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
from .errors import CineToasterError, ValidationError
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
    if args.agent_provider is not None and not args.assistant:
        raise ValidationError("--agent-provider requires --assistant")
    _ensure_index(args.project, refresh=not args.no_refresh)
    serve_project(args.project, host=args.host, port=args.port, assistant=args.assistant,
                  agent_provider=args.agent_provider)
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


def command_new(args: argparse.Namespace) -> int:
    """A new production, from nothing or from a screenplay (CT-0098)."""

    from .new_production import create_production

    destination = args.destination.expanduser().resolve()
    checkout = _source_checkout_root()
    if checkout is not None and _is_within(destination, checkout):
        print(f"Refusing to create a production inside the Cine Toaster source repository: {destination}\n"
              "A film lives outside the checkout.", file=sys.stderr)
        return 2
    try:
        created = create_production(destination, args.title, screenplay=args.screenplay,
                                    project_id=args.id or "", logline=args.logline or "")
        production = load_production(created.root)
    except CineToasterError as error:
        print(str(error), file=sys.stderr)
        return 2
    for note in created.notes:
        print(note)
    print(f"Created {production['title']} ({created.project_id}) at {created.root}")
    if created.scenes:
        print(f"{len(created.scenes)} scene(s) from the screenplay, each a breakdown with no shots yet.")
    else:
        print("No scenes yet: write the screenplay in story/screenplay.fountain, or the breakdowns in scenes/.")
    print("Next: toast serve {0}  |  toast check {0}  |  toast script show {0}".format(created.root))
    print("How a film is made here, in two phases: docs/making-a-film.md")
    return 0


def command_references(args: argparse.Namespace) -> int:
    """A film's references, with where each came from (CT-0100)."""

    from .references import add_reference, generate_reference, load_references, reference_images

    if args.references_command == "generate":
        try:
            if args.dry_run:
                from .providers.codex_image import instruction
                from .references import compose

                pictures = reference_images(args.project, args.parent or [])
                args.prompt, _ = compose(args.project, args.prompt, cast=args.cast or "", style=args.style or "")
                print(f"provider: {args.provider} (subscription quota, no dollars)")
                for picture in pictures:
                    print(f"reference: {picture}")
                print(f"instruction: {instruction(args.prompt, len(pictures))}")
                return 0
            folder = generate_reference(args.project, prompt=args.prompt, title=args.title,
                                        parents=args.parent or [], provider=args.provider,
                                        requested_by=args.requested_by or "", notes=args.note or [],
                                        name=args.name or "", cast=args.cast or "", style=args.style or "")
        except CineToasterError as error:
            print(str(error), file=sys.stderr)
            return 2
        print(f"Generated {folder.name}: {folder / 'image.png'}")
        return 0
    if args.references_command == "add":
        try:
            folder = add_reference(args.project, args.files, title=args.title, kind=args.kind,
                                   made_by=args.made_by or "", made_on=args.made_on or "", source=args.source or "",
                                   prompt=args.prompt or "", parents=args.parent or [], licence=args.licence or "",
                                   credit=args.credit or "", notes=args.note or [], name=args.name or "")
        except CineToasterError as error:
            print(str(error), file=sys.stderr)
            return 2
        print(f"Added {folder.name}")
        return 0
    references = load_references(args.project)
    if args.json:
        print(json.dumps(references, ensure_ascii=False, indent=2))
        return 1 if any(item["severity"] == "error" for ref in references for item in ref["findings"]) else 0
    if not references:
        print("No references yet: toast references add <film> <file> --title ... --kind generated|found|made")
    errors = 0
    for reference in references:
        made = ", ".join(str(reference[key]) for key in ("kind", "made_by", "made_on") if reference.get(key))
        print(f"{reference['id']}  {reference.get('title', '')}" + (f"  ({made})" if made else ""))
        for finding in reference["findings"]:
            errors += finding["severity"] == "error"
            print(f"  {finding['severity'].upper()}  {finding['code']}: {finding['message']}")
    return 1 if errors else 0


def command_creation(args: argparse.Namespace) -> int:
    from .creation import creation_view, save_creation_draft, save_exploration_round

    try:
        if args.creation_command == "list":
            result = creation_view(args.project)
        elif args.creation_command == "assess":
            from .creation_review import record_inception_assessment
            payload = json.loads(args.assessment_file.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValidationError("Assessment file must contain a JSON object")
            result = record_inception_assessment(args.project, title=payload.get("title"), summary=payload.get("summary"),
                readiness=payload.get("readiness"), proposal=payload.get("proposal"), references=payload.get("references", []),
                expected_revision=args.expected_revision, actor=_resolve_actor(args))
        elif args.creation_command == "decide":
            from .creation_review import decide_inception_assessment
            result = decide_inception_assessment(args.project, assessment=args.assessment, outcome=args.outcome,
                guidance=args.guidance, expected_revision=args.expected_revision, actor=_resolve_actor(args))
        elif args.creation_command == "round":
            pairs = []
            for value in args.correction or []:
                previous, separator, current = value.partition("=")
                if not separator:
                    raise ValidationError("--correction must be previous-reference=current-reference")
                pairs.append({"previous": previous, "current": current})
            result = save_exploration_round(args.project, title=args.title, references=args.reference or [],
                expected_revision=args.expected_revision, actor=_resolve_actor(args), rationale=args.why,
                source=args.source, follows=args.follows or "", corrections=pairs, based_on=args.based_on or "")
        else:
            result = save_creation_draft(
                args.project, kind=args.kind, title=args.title, text=args.text_file.read_text(encoding="utf-8"),
                expected_revision=args.expected_revision, actor=_resolve_actor(args),
                references=args.reference or [], concept=args.concept or "", based_on=args.based_on or "",
                rationale=args.why or "")
    except (CineToasterError, OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
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


def command_take_add(args: argparse.Namespace) -> int:
    from .commands import add_take

    result = add_take(args.project, scene_id=args.scene, shot_id=args.shot, source=args.file,
                      actor=_resolve_actor(args), name=args.name, kind=args.kind, origin=args.source or "",
                      licence=args.licence or "", credit=args.credit or "")
    if args.json:
        print(json.dumps(result.public_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"Added {result.event['payload']['media']} as take {result.take_id} of {result.shot_id}")
    return 0


def command_footage(args: argparse.Namespace) -> int:
    """Footage declared in the breakdown: what there is, and bringing it in (CT-0066)."""

    from .footage import fetch

    root = args.project.expanduser().resolve()
    production = load_production(root)
    if args.footage_command == "list":
        found = False
        for scene in production["scenes"]:
            for shot in scene["shots"]:
                footage = shot.get("footage")
                if not footage or (args.scene and scene["id"] != args.scene):
                    continue
                found = True
                state = "fetched" if shot.get("takes") else "not fetched"
                print(f"{scene['id']} {shot['id']:5} {state:12} {footage['in']:g} s + "
                      f"{footage['duration'] or shot.get('duration_seconds') or 0:g} s  {footage['licence']}"
                      f"  ({footage['credit'] or 'no credit'})\n      {footage['page'] or footage['url']}")
        if not found:
            print("No shot declares footage.")
        return 0
    results = fetch(root, production, _resolve_actor(args), scene_id=args.scene, report=print)
    if not results:
        print("No shot declares footage.")
        return 0
    for item in results:
        print(f"  {item.status:8} {item.scene} {item.shot}  {item.detail}")
    return 1 if any(item.status == "refused" for item in results) else 0


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


def command_still(args: argparse.Namespace) -> int:
    """A shot's frame as the cut draws it: its graph run at one instant (CT-0072)."""

    from .assembly import plan_scene, still
    from .project import STILLS_DIRECTORY, load_production

    root = args.project.expanduser().resolve()
    production = load_production(root)
    scene = next((item for item in production["scenes"] if item["id"] == args.scene), None)
    if scene is None:
        print(f"No scene {args.scene!r}.", file=sys.stderr)
        return 1
    destination = args.output or root / STILLS_DIRECTORY / args.scene / f"{args.shot}.png"
    try:
        plan = plan_scene(root, scene, production.get("words_sidecar") or "{stem}.words.json")
        still(root, plan, args.shot, destination, args.at)
    except ValidationError as error:
        print(str(error), file=sys.stderr)
        return 2
    for note in plan.notes:
        if note.startswith(f"{args.shot}:"):
            print(f"  {note}")
    print(f"Wrote {destination}")
    return 0


def command_assemble(args: argparse.Namespace) -> int:
    """Assemble a new version of a scene from its selected takes, as a job."""

    from .jobs import JobManager

    manager = JobManager()
    try:
        job = manager.submit("assemble", args.project, {"scene": args.scene, "version": args.version or "",
                                                        "summary": args.summary or "",
                                                        "stems": bool(getattr(args, "stems", False)),
                                                        "otio": bool(getattr(args, "otio", False))})
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
    if getattr(plan, "cost", "usd") == "usd":  # a block plan is always paid in dollars
        print(f"  estimate US$ {plan.estimate_usd:.3f}; spent US$ {spend.spent():.2f} of US$ {spend.load().get('limit_usd') or 0:.2f}")
    else:
        print(f"  cost: {plan.cost} (not dollars; the budget does not hold it)")
    print("\n" + plan.prompt + "\n")
    if plan.avoid:
        # What the generation must not do, apart from the directing words, and how the provider carries it.
        print(f"avoid ({plan.avoid_mechanism}):")
        for item in plan.avoid:
            print(f"  - {item}")
        if getattr(plan, "negative", ""):
            print(f"  negative conditioning sent: {plan.negative}")
        print()
    if getattr(plan, "continuity", None):
        # What the ledger says holds here (CT-0059): for the author to check against the prompt; not sent.
        print("continuity in force:")
        for line in plan.continuity:
            print(f"  {line}")
        print()
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
            target = ({"template": "masters"} if args.block == "masters" else
                      {"block": args.block} if args.block in blocks else {"shot": args.block})
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
    if args.storyboard_command == "animatic":
        from .storyboard_animatic import render
        result = render(root, args.sequence)
        print(f"{result['path']}: {result['shots']} shots, {result['seconds']} s (version {result['version']})")
        for label, items in (("no drawing yet", result["missing"]), ("no declared duration", result["undeclared_durations"])):
            if items:
                print(f"  {label}: {', '.join(items)}")
        return 0
    if args.storyboard_command in ("candidates", "add"):
        from .storyboard import register_storyboard_candidate, storyboard_view
        from .state import Actor
        if args.storyboard_command == "candidates":
            result = storyboard_view(root, args.scene)
        else:
            provenance = json.loads(args.provenance.read_text(encoding="utf-8")) if args.provenance else {}
            result = register_storyboard_candidate(root, scene=args.scene, shot=args.shot, image=args.image,
                title=args.title, expected_revision=args.expected_revision,
                actor=Actor(id=args.actor, kind=args.actor_kind), references=args.reference,
                based_on=args.based_on, note=args.note, provenance=provenance)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
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
                          "transition": transition, "split": args.split}
        result = dispatch(root, "set_cut", payload)
    cut = next(item for item in load_production(root)["scenes"] if item["id"] == args.scene)
    record = next((item for item in cut["cuts"] if item["to"] == args.shot), {})
    print(f"{result.type}: into {args.shot} is now {record.get('type', 'hard')}"
          + (f" with {record['transition']['id']}" if record.get("transition") else "")
          + f" (revision {result.revision})")
    for finding in record.get("findings") or []:
        print(f"  {finding['severity']}: {finding['message']}")
    return 0


def command_board(args: argparse.Namespace) -> int:
    """The 3D storyboard: still boards per shot, or the scene's animatic (CT-0049)."""

    from .board import animatic, boards, sheet
    from .project import load_scene

    root = Path(args.project).expanduser().resolve()
    scene = load_scene(root, args.scene)
    if scene is None:
        print(f"No scene {args.scene!r}", file=sys.stderr)
        return 1
    if args.board_command == "sheet":
        print(f"Made {sheet(root, scene).relative_to(root)}")
        return 0
    if args.board_command == "animatic":
        video = animatic(root, scene, width=args.width, height=args.height, step=args.step)
        print(f"Made {video.relative_to(root)}: the scene through its cameras, to check -- not given to any model")
        return 0
    for made in boards(root, scene, shots=args.shot or None, ends=args.end, width=args.width, height=args.height,
                       look=args.look):
        print(f"{made['shot']} {made['moment']}: {Path(made['board']).relative_to(root)} (+ depth)")
    print("A board is a composition to start a picture from: derive: {from: board, with: [...], request: ...}")
    return 0


def command_nerf(args: argparse.Namespace) -> int:
    """A shot's camera move as a nerfstudio camera path (CT-0047)."""

    from .nerf import export
    from .project import load_scene

    root = Path(args.project).expanduser().resolve()
    scene = load_scene(root, args.scene)
    shot = next((item for item in (scene or {}).get("shots", []) if item["id"] == args.shot), None)
    if shot is None:
        print(f"No shot {args.scene} {args.shot}", file=sys.stderr)
        return 1
    output = Path(args.output) if args.output else root / "exports" / "nerf" / args.scene / f"{args.shot}.json"
    made = export(root, scene, shot, output, frames=args.frames, width=args.width, height=args.height)
    print(f"Wrote {made['path']} ({made['frames']} frames)")
    if not made["placed"]:
        print("  The location declares no nerf: transform; the plan's metres are used as the NeRF's units.")
    print(f"  On the GPU machine: {made['command']}")
    return 0


def command_splat(args: argparse.Namespace) -> int:
    """A shot's camera move through its location's Gaussian splat, as a plate (CT-0047)."""

    from .project import load_scene
    from .splat import plate

    root = Path(args.project).expanduser().resolve()
    scene = load_scene(root, args.scene)
    shot = next((item for item in (scene or {}).get("shots", []) if item["id"] == args.shot), None)
    if shot is None:
        print(f"No shot {args.scene} {args.shot}", file=sys.stderr)
        return 1
    output = root / "renders" / "splat" / args.scene / f"{args.shot}.mp4"
    made = plate(root, scene, shot, output, frames=args.frames, width=args.width, height=args.height)
    print(f"Made {Path(made['video']).relative_to(root)} and its first frame {Path(made['still']).relative_to(root)}")
    camera = (shot.get("motion") or {}).get("camera_id") or "<camera>"
    print(f"To start pictures from it, list it in the location: references: [{{path: <copy of the still>, "
          f"kind: plate, camera: {camera}}}]")
    return 0


def command_usd(args: argparse.Namespace) -> int:
    """A scene's plan as an OpenUSD stage, for Blender, Unreal and Unity (CT-0047)."""

    from .project import load_scene
    from .usd_export import export

    root = Path(args.project).expanduser().resolve()
    scene = load_scene(root, args.scene)
    if scene is None:
        print(f"No scene {args.scene!r}", file=sys.stderr)
        return 1
    output = Path(args.output) if args.output else root / "exports" / "usd" / f"{args.scene}.usda"
    summary = export(scene, output)
    print(f"Wrote {summary['output']}: {len(summary['shots'])} shot cameras over {summary['frames']} frames at 24 fps")
    for item in summary["shots"]:
        print(f"  /Scene/Cameras/{item['shot']}  frames {item['first_frame']}-{item['first_frame'] + item['frames']}")
    return 0


def command_vfx(args: argparse.Namespace) -> int:
    """The VFX catalog and the production's elements; build the example elements (CT-0047)."""

    from .vfx import list_effects, list_elements

    root = Path(args.project).expanduser().resolve()
    if args.vfx_command == "examples":
        from .vfx_examples import build

        for element_id in build(root):
            print(f"made vfx_elements/{element_id}")
        return 0
    for item in list_effects(root):
        print(f"{item['id']:24} {item['category']:10} {item.get('engine', 'ffmpeg'):8} {item['says'][:70]}")
    elements = list_elements(root)
    if elements:
        print()
    for element in elements:
        state = "" if element["exists"] else "  (missing)"
        print(f"{element['id']:26} {element['category']:10} {element['format']:16} {element['blend']}{state}")
    return 0


def command_track(args: argparse.Namespace) -> int:
    """Tracks as production records (C7 step 5, CT-0080): measure, see, correct, revert."""

    from . import tracks

    root = args.project.expanduser().resolve()
    if args.track_command == "measure":
        done = tracks.measure_track(root, track_id=args.id, media=args.media, kind=args.kind, region=args.region,
                                    start=args.start, end=args.end, actor=_resolve_actor(args),
                                    rationale=args.rationale)
        state = tracks.status(root, args.id)
        weak = ", ".join(f"{a}-{b}" for a, b in state["weak"]) or "none"
        print(f"{args.id}: measurement {done['measurement']}, revision {done['revision']}; weak entries: {weak}")
        return 0
    if args.track_command == "status":
        print(json.dumps(tracks.status(root, args.id), indent=2))
        return 0
    if args.track_command == "correct":
        values = [[args.at[i], args.at[i + 1]] for i in range(0, len(args.at), 2)]
        done = tracks.correct_track(root, track_id=args.id, index=args.index, actor=_resolve_actor(args),
                                    **({"corners": values} if len(values) == 4 else {"points": values}),
                                    note=args.rationale, expected_revision=args.expect_revision)
        print(f"{args.id}: entry {args.index} corrected ({done['correction']}), revision {done['revision']}")
        return 0
    done = tracks.revert_corrections(root, track_id=args.id, actor=_resolve_actor(args), correction=args.correction,
                                     index=args.index, note=args.rationale)
    print(f"{args.id}: reverted {', '.join(done['reverted'])}, revision {done['revision']}")
    return 0


def _prompted_objects(args: argparse.Namespace) -> list[dict]:
    """`--object NAME[@FRAME]:X,Y[:X,Y...]` and `--box NAME[@FRAME]:X0,Y0,X1,Y1`, in the order given."""

    objects = []
    for given, kind in [(item, "points") for item in args.object or []] + [(item, "box") for item in args.box or []]:
        head, _, rest = given.partition(":")
        name, _, frame = head.partition("@")
        try:
            numbers = [[float(value) for value in pair.split(",")] for pair in rest.split(":") if pair]
        except ValueError:
            raise ValidationError(f"Not an object: {given!r} (NAME[@FRAME]:X,Y[:X,Y...])") from None
        if not name or not numbers:
            raise ValidationError(f"Not an object: {given!r} (NAME[@FRAME]:X,Y[:X,Y...])")
        objects.append({"name": name, "frame": int(frame or 0),
                        **({"points": numbers} if kind == "points" else {"box": numbers[0]})})
    return objects


def command_models(args: argparse.Namespace) -> int:
    """The models that estimate signals: the catalog, and fetching one -- the only act that downloads."""

    from . import models

    if args.models_command == "list":
        for item in models.describe():
            print(f"{item['model']:30} {item['kind']:15} {item['licence']:11} {item['revision']}  "
                  f"{'fetched' if item['fetched'] else 'not fetched'}")
        return 0
    done = models.fetch(args.name, again=args.again)
    print(f"{args.name}: {'fetched' if done['fetched'] else 'already here'} in {done['directory']}")
    return 0


def command_signal(args: argparse.Namespace) -> int:
    """Signals as production records (C8, CT-0081): estimate one with a model, compare, see."""

    from . import estimates, signals

    root = args.project.expanduser().resolve()
    if args.signal_command == "estimate":
        done = estimates.estimate(root, signal_id=args.id, model=args.model, media=args.media,
                                  actor=_resolve_actor(args), first=args.first, count=args.count,
                                  objects=_prompted_objects(args) or None, threads=args.threads, repeat=args.repeat,
                                  parameters={"input_size": args.input_size} if args.input_size else None)
        repeat = done["repeat"]
        print(f"{args.id}: {done['frames']} frames by {args.model}, revision {done['revision']}"
              + (f"; a second run {'identical' if repeat['identical'] else 'differed by ' + str(repeat['max_difference'])}"
                 if repeat else ""))
        return 0
    if args.signal_command == "align":
        from . import align

        done = align.align_depth(root, signal_id=args.id, estimate=args.estimate, reference=args.reference,
                                 camera=args.camera, actor=_resolve_actor(args), temporal=args.temporal,
                                 smoothness=args.smoothness, first=args.first, count=args.count,
                                 region=args.region, keep_labels=args.keep, leave_labels=args.leave,
                                 objects=args.objects)
        print(json.dumps({key: done[key] for key in ("signal", "revision", "residual", "held_out_frames",
                                                      "held_out_tail", "temporal_agreement", "modes_compared",
                                                      "occlusions_inverted") if key in done}, indent=2))
        return 0
    if args.signal_command == "compare":
        done = estimates.compare(root, signal_id=args.id, reference=args.reference, actor=_resolve_actor(args))
        print(json.dumps(done, indent=2))
        return 0
    print(json.dumps(signals.status(root, args.id), indent=2, default=str))
    return 0


def command_render(args: argparse.Namespace) -> int:
    """A 3D scene's passes rendered apart and recorded (C8 step 2, CT-0081)."""

    from . import renders

    root = args.project.expanduser().resolve()
    if args.render_command == "passes":
        done = renders.render_passes(root, render_id=args.id, camera=args.camera, first=args.first, last=args.last,
                                     size=tuple(args.size), fps=args.fps, actor=_resolve_actor(args),
                                     blend=args.blend, recipe=args.recipe, samples=args.samples,
                                     camera_id=args.camera_id)
        print(f"{args.id}: {done['frames']} frames by Blender {done['blender']}; signals {', '.join(done['signals'])}")
        return 0
    print(json.dumps(renders.status(root, args.id), indent=2, default=str))
    return 0


def command_sound(args: argparse.Namespace) -> int:
    """The sound catalog, and the sources recorded sound and music come from (CT-0048)."""

    from . import sound_sources
    from .providers.runpod import load_credentials
    from .sounds import list_sounds, preview

    if getattr(args, "env_file", None):
        load_credentials(Path(args.env_file).expanduser())  # never printed
    if args.sound_command == "search":
        search = {"freesound": sound_sources.freesound_search, "sonniss": sound_sources.sonniss_search,
                  "openverse": lambda terms, count: sound_sources.openverse_search(terms, count, music=not args.effects)}
        for item in search[args.source](args.terms, args.count):
            extra = item.get("pack") or item.get("by") or ""
            length = f"{item['seconds']:7.1f} s" if item.get("seconds") is not None else f"{item.get('megabytes', 0):6.1f} MB"
            print(f"{item['name'][:44]:44} {length}  {extra[:28]:28} {item['licence'][:30]}\n    {item['id']}")
        return 0
    root = Path(args.project).expanduser().resolve()
    if args.sound_command == "fetch":
        fetch = {"freesound": sound_sources.freesound_fetch, "sonniss": sound_sources.sonniss_fetch,
                 "openverse": sound_sources.openverse_fetch}[args.source]
        options = {"sound_id": args.as_id or "", "says": args.says or ""}
        if args.category:
            options["category"] = args.category
        manifest = fetch(root, args.item, **options)
        print(f"made {manifest.relative_to(root)}")
        return 0
    if args.sound_command == "import":
        made = sound_sources.import_library(root, Path(args.folder), prefix=args.prefix)
        print(f"registered {len(made)} sounds from {args.folder}")
        return 0
    catalog = {item["id"]: item for item in list_sounds(root)}
    if args.sound_command == "beats":
        from .beats import detect

        if args.id not in catalog:
            print(f"No sound {args.id!r} in the catalog", file=sys.stderr)
            return 1
        heard = detect(catalog[args.id])
        times = heard["beats"]
        print(f"{args.id}: {heard['tempo']:g} BPM, {len(times)} beats from {times[0]:.2f} s to {times[-1]:.2f} s "
              f"-> {Path(catalog[args.id]['directory']).relative_to(root) / 'beats.json'}")
        return 0
    if args.sound_command == "preview":
        if args.id not in catalog:
            print(f"No sound {args.id!r} in the catalog", file=sys.stderr)
            return 1
        output = Path(args.output or f"{args.id}.wav")
        print(preview(catalog[args.id], output, seconds=args.seconds))
        return 0
    for item in catalog.values():
        state = "" if item["exists"] else "  (missing)"
        status = f" [{item['status']}]" if item["status"] else ""
        print(f"{item['id']:28} {item['category']:9} {item['licence'][:22]:22}{status} {item['says'][:60]}{state}")
    return 0


def command_continuity(args: argparse.Namespace) -> int:
    """The continuity ledger (CT-0059): what holds from scene to scene, or at one shot."""

    from .continuity import describe, ledger, render_text, state_at

    production = load_production(Path(args.project).expanduser().resolve())
    if args.scene:
        state = state_at(production, args.scene, args.shot or "")
        if args.json:
            print(json.dumps(state, indent=2, ensure_ascii=False))
        else:
            print("\n".join(describe(state, args.scene)) or "Nothing declared holds here.")
        return 0
    report = ledger(production)
    if args.json:
        print(json.dumps({"scenes": report["scenes"],
                          "findings": {key: [item.public_dict() for item in value]
                                       for key, value in report["findings"].items()}}, indent=2, ensure_ascii=False))
    else:
        print(render_text(report))
    return 0


def command_intake(args: argparse.Namespace) -> int:
    """The format interview (SPEC-0020): what the format needs, what was asked, and your answers."""

    from .creation import load_creation
    from .intake import answer_intake, intake_view
    from .state import Actor

    root = Path(args.project).expanduser().resolve()
    if args.withdraw:
        from .intake import withdraw_intake
        question, reason = args.withdraw
        withdraw_intake(root, question=question, reason=reason, expected_revision=load_creation(root)["revision"],
                        actor=Actor(id="director", kind="human"))
    if args.answer:
        question, text = args.answer
        # Whoever types at this terminal is the person the question was put to.
        answer_intake(root, question=question, answer=text, expected_revision=load_creation(root)["revision"],
                      actor=Actor(id="director", kind="human"))
    view = intake_view(root)
    if args.json:
        print(json.dumps(view, indent=2, ensure_ascii=False))
        return 0
    form = view["format"]
    print(f"Format: {form['name']} ({form['source']})" if form else "Format: not known yet"
          + (f" -- the production says {view['production_says']!r}" if view["production_says"] else ""))
    for row in view["items"]:
        mark = {"answered": "answered", "open": "ASKED", "not_asked": "not asked"}[row["status"]]
        print(f"  [{mark}] {row['id']}: {row['ask']}" + (f"  (unlocks {row['unlocks']})" if row["unlocks"] else ""))
        if row["status"] == "open":
            print(f"      question {row['question']['id']}: {row['question']['question']}")
            print(f"      why: {row['question']['why']}")
        if row["answer"]:
            print(f"      you said: {row['answer']['answer']}")
    if view["open_count"]:
        print(f"Answer with: toast intake {args.project} --answer QUESTION_ID \"your words\"")
    return 0


def command_recipes(args: argparse.Namespace) -> int:
    """The generation recipes (ADR 0034): what each path makes, its configuration, models, costs, known failures."""

    from .providers.recipes import batch_plan, endpoint_config, health, recipes
    from .providers.runpod import load_credentials

    if args.env_file:
        load_credentials(Path(args.env_file).expanduser())  # never printed
    if args.batch:
        recipe, jobs = args.batch[0], int(args.batch[1])
        plan = batch_plan(recipe, jobs, seconds_each=args.seconds)
        if args.json:
            print(json.dumps(plan, indent=2, ensure_ascii=False))
            return 0
        print(f"{recipe}, {jobs} job(s) of about {plan['seconds_each']:.0f} s; {plan['warm_workers']} warm worker(s)"
              + (f", at most {plan['workers_max']}" if plan["workers_max"] else "")
              + (f", idle timeout {plan['idle_timeout_seconds']} s" if plan["idle_timeout_seconds"] is not None else ""))
        for label, key in (("together", "together"), ("one by one, worst case", "one_by_one_worst")):
            part = plan[key]
            print(f"  {label}: {part['cold_starts']} cold start(s), about {part['seconds']} s, cold US$ {part['cold_usd']}")
        for line in plan["advice"]:
            print(f"  - {line}")
        print(f"  ({plan['assumes']})")
        return 0
    if args.health:
        value, config = health(args.health), endpoint_config(args.health)
        if args.json:
            print(json.dumps({"health": value, "config": config}, indent=2, ensure_ascii=False))
            return 0
        print(f"{value['recipe']}: {value['warm_workers']} warm worker(s), queue {value['jobs'].get('inQueue', 0)}, "
              f"running {value['jobs'].get('inProgress', 0)}"
              + ("; a cold start is likely" if value["cold_start_likely"] else "")
              + (f"; {value['unhealthy']} unhealthy" if value["unhealthy"] else "")
              if value["readable"] else f"{value['recipe']}: not readable -- {value['reason']}")
        print(f"  workers {config['workers_min']}..{config['workers_max']}, idle timeout {config['idle_timeout_seconds']} s, "
              f"scaling {config['scaling']}, FlashBoot {config['flashboot']}" if config["readable"]
              else f"  configuration not readable -- {config['reason']}")
        if config.get("readable") and config.get("workers_max") == 0:
            print("  TAKES NO JOB: max workers is 0. Raise it to at least 1 before sending (min 0 costs nothing idle).")
        print(f"  scaling down now: {'safe' if value['scale_down']['safe'] else 'NOT safe'} ({value['scale_down']['reason']})")
        return 0
    found = recipes()
    if args.json:
        print(json.dumps(found, indent=2, ensure_ascii=False))
        return 0
    for item in found:
        print(f"{item['id']} ({item['kind']}, {item['transport']}): {item['does']}")
        print(f"  {'configured' if item['configured'] else 'missing ' + ', '.join(item['missing'])}; "
              + (f"US$ {item['rate_usd_per_hour']}/h" if item.get("rate_usd_per_hour") else f"cost: {item['cost']}"))
        for model in item["models"]:
            print(f"  needs {model['file']} ({model['loader']})")
        for failure in item["known_failures"]:
            print(f"  known: {failure['id']} -- {failure['workaround']}")
    return 0


def command_status(args: argparse.Namespace) -> int:
    """Where the production stands, sequence by sequence: the Producer's report (docs/production-agents.md)."""

    from .producer import production_status, render_text

    status = production_status(load_production(Path(args.project).expanduser().resolve()), args.sequence or "")
    print(json.dumps(status, indent=2, ensure_ascii=False) if args.json else render_text(status))
    return 0


def command_transcribe(args: argparse.Namespace) -> int:
    """Word timings for a scene's speaking takes that have none (CT-0054)."""

    job = _foreground_job("transcribe", Path(args.project), {"scene": args.scene, "language": args.language}, None)
    if job is None:
        return 1
    for item in job["result"]["summary"]["transcribed"]:
        print(f"  {item['shot']}: {item['take']}")
    return 0


def command_migrate(args: argparse.Namespace) -> int:
    """Migrate a production made outside Cine Toaster into its own format (CT-0054)."""

    from .migrate import migrate

    report = migrate(Path(args.source), Path(args.target), replace=args.replace,
                     proposals=Path(args.proposals).expanduser() if args.proposals else None, git=not args.no_git)
    print(f"{report.copied_files} files, {report.copied_bytes / 1e9:.2f} GB; {len(report.scenes)} scenes; "
          f"{len(report.converted)} converted, {len(report.approximated)} approximated, "
          f"{len(report.kept)} kinds of field kept as written. See {Path(args.target) / 'MIGRATION.md'}")
    return 0


def command_style(args: argparse.Namespace) -> int:
    """The style catalog: direction, animation techniques, formats (CT-0049)."""

    from .styles import list_styles

    root = Path(args.project).expanduser().resolve()
    catalog = {item["id"]: item for item in list_styles(root)}
    if args.style_command == "list":
        for item in catalog.values():
            aka = f" (aka {', '.join(item['aka'])})" if item["aka"] else ""
            print(f"{item['id']:24} {item['kind']:10} {item['name']}{aka}")
        return 0
    item = catalog.get(args.id)
    if item is None:
        print(f"No style {args.id!r} in the catalog", file=sys.stderr)
        return 1
    print(f"{item['name']} ({item['kind']}): {item['says']}")
    if item["inspired_by"]:
        print(f"  inspired by (for people, never sent to a model): {', '.join(item['inspired_by'])}")
    print(f"  framing: {'; '.join(item['framing'])}")
    print(f"  moves: prefer {', '.join(item['camera']['prefer']) or '-'}; avoid {', '.join(item['camera']['avoid']) or '-'}")
    editing = item["editing"]
    if editing["shot_seconds"]:
        print(f"  shots: {editing['shot_seconds'][0]:g}-{editing['shot_seconds'][1]:g} s; cuts {', '.join(editing['prefer_cuts']) or '-'}")
    print(f"  performance: {item['performance']['intensity']}, at most {item['performance']['max']} -- {item['performance']['notes']}")
    print(f"  colour: {item['colour']}\n  sound: {item['sound']}")
    form = {key: value for key, value in item["format"].items() if value}
    if form:
        print(f"  format: {form}")
    print(f"  prompt: {item['prompt']}")
    return 0


def command_emotion(args: argparse.Namespace) -> int:
    """The emotion catalog: what shows, what a model is asked, and the face as blendshapes (CT-0048)."""

    from .emotions import face, list_emotions

    root = Path(args.project).expanduser().resolve()
    catalog = {item["id"]: item for item in list_emotions(root)}
    if args.emotion_command == "list":
        for item in catalog.values():
            print(f"{item['id']:16} {item['family']:11} {item['says'][:80]}")
        return 0
    item = catalog.get(args.id)
    if item is None:
        print(f"No emotion {args.id!r} in the catalog", file=sys.stderr)
        return 1
    if args.emotion_command == "face":
        print(json.dumps(face(item, args.intensity), indent=2))
        return 0
    print(f"{item['name']} ({item['family']}): {item['says']}")
    for part in ("face", "body", "voice"):
        print(f"  {part}: {'; '.join(item['signals'][part])}")
    for level in ("subtle", "clear", "overwhelming"):
        print(f"  ask, {level}: {item['ask'][level]}")
        print(f"  voice, {level}: {item['voice'][level]}")
    return 0


def command_mcp(args: argparse.Namespace) -> int:
    """Serve the project to Claude Code over MCP, on stdio (CT-0045)."""

    import importlib.util

    if importlib.util.find_spec("mcp") is None:
        print("The MCP server needs the mcp extra: make install-mcp", file=sys.stderr)
        return 1
    from .mcp_server import serve
    from .providers.runpod import load_credentials

    if args.env_file:
        load_credentials(Path(args.env_file).expanduser())  # never printed
    serve(Path(args.project))
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
    if args.from_drawing:
        from .pictures import adopt_drawing

        made = adopt_drawing(root, args.scene, args.shot, offset=args.offset)
        print(f"Made {made['picture']} from the storyboard drawing {made['drawing']} (v{made['drawing_version']}), "
              f"cropped {made['crop']['from'][0]}x{made['crop']['from'][1]} to {made['crop']['box']}; nothing generated.")
        return 0
    if args.env_file:
        load_credentials(Path(args.env_file).expanduser())  # never printed
    plan, _, _ = _picture_plan(root, {"scene": args.scene, "shot": args.shot, "seed": args.seed})
    if args.json and args.dry_run:
        print(json.dumps(plan.public_dict(root), indent=2, ensure_ascii=False))
        return 0
    from .pictures import relative

    made_from = f"edit {relative(root, plan.source)}" if plan.source is not None else "compose from the description"
    sized = f" at {plan.size[0]}x{plan.size[1]}" if plan.size else ""
    print(f"{plan.scene} {plan.shot}: {made_from}{sized}, seed {plan.seed}; by {plan.provider} ({plan.provider_level})")
    for ref in plan.references:
        print(f"  identity: {ref['member']}" + (f" ({ref['variant']})" if ref["variant"] else "")
              + f" from {relative(root, ref['path'])}")
    for note in plan.notes:
        print(f"  note: {note}")
    print(f"  estimate US$ {plan.estimate_usd:.3f}; spent US$ {spend.spent():.2f} of US$ {spend.load().get('limit_usd') or 0:.2f}")
    print("\n" + plan.prompt + "\n")
    if plan.avoid:
        # What the generation must not do, apart from the directing words, and how the provider carries it.
        print(f"avoid ({plan.avoid_mechanism}):")
        for item in plan.avoid:
            print(f"  - {item}")
        if getattr(plan, "negative", ""):
            print(f"  negative conditioning sent: {plan.negative}")
        print()
    if getattr(plan, "continuity", None):
        # What the ledger says holds here (CT-0059): for the author to check against the prompt; not sent.
        print("continuity in force:")
        for line in plan.continuity:
            print(f"  {line}")
        print()
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
    paid = (f"for US$ {summary['cost_usd']:.3f}" if summary.get("cost", "usd") == "usd"
            else f"by {summary.get('provider')}, on subscription quota")
    print(f"Made {summary['picture']} {paid}" + (
        f"; edges kept from the source: {summary['edge_score']} (under 17: recomposed). "
        "A moved subject can still score well: look at it." if summary.get("edge_score") is not None else "."))
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

    if getattr(args, "scenes", False):
        # The whole sequence from its records: a new version of each scene, then of the sequence (CT-0065).
        sequence = next((item for item in load_production(args.project)["sequences"] if item["id"] == args.sequence), None)
        if sequence is None:
            print(f"There is no sequence {args.sequence!r} in this production.", file=sys.stderr)
            return 1
        for scene_id in sequence["scene_ids"]:
            made = command_assemble(argparse.Namespace(project=args.project, scene=scene_id, version=None,
                                                       summary=args.summary, stems=False))
            if made:
                return made

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


def command_finops(args: argparse.Namespace) -> int:
    """What Runpod billed, set against the jobs Cine Toaster ran (CT-0061). Reads only."""

    from datetime import UTC, datetime, timedelta

    from . import spend
    from .finops import reconcile, render_text
    from .jobs import state_root
    from .providers.runpod import load_credentials
    from .providers.runpod_billing import serverless_observations

    if args.env_file:
        load_credentials(Path(args.env_file).expanduser())  # never printed
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    start = now - timedelta(days=args.days)
    billing = serverless_observations(start.isoformat().replace("+00:00", "Z"), now.isoformat().replace("+00:00", "Z"))
    fetched_at = datetime.now(UTC).isoformat(timespec="seconds")
    entries = spend.load()["entries"]
    if args.project:
        # The film's own job records (whoever ran them) join the ledger: its billed hours are the film's.
        from .finops import film_jobs, merge
        from .project import _read_yaml

        root = Path(args.project).expanduser().resolve()
        entries = merge(entries, film_jobs(root, _read_yaml(root / "project.yaml").get("generation_rates") or {}))
    report = reconcile(billing, entries, fetched_at)
    # Operational state, disposable: the provider can always be asked again.
    cache = state_root() / "finops" / "runpod-latest.json"
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2) if args.json else render_text(report))
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

    from .narration import speak_lines

    narrators: dict[str, PiperNarration] = {}

    def speaker(voice: str) -> PiperNarration:
        # Voices are downloaded once into the production, where the film can be remade from.
        return narrators.setdefault(voice, PiperNarration(root / VOICES_DIRECTORY, voice))

    results = speak_lines(root, production, speaker, scene_id=args.scene,
                          default_voice=args.voice or DEFAULT_VOICE, force=args.force)
    if not results:
        print("No lines with a mix destination. Nothing to speak.")
        return 0
    for item in results:
        if item.made:
            print(f"  {item.status:<7}{item.scene} {item.shot}  {item.seconds:.1f}s  {item.file}  [{item.voice}]"
                  + (f"  ({item.reason})" if item.reason else ""))
        else:
            print(f"  {item.status:<7}{item.file}  ({item.reason})")
    made = sum(1 for item in results if item.made)
    print(f"\n{made} line(s) spoken, {len(results) - made} not made. Cost: $0.00, offline.")
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
                              help="also run the directing assistant (agents extra, Node, configured provider or current CLI; ADR 0018)")
    serve_parser.add_argument("--agent-provider", metavar="ADAPTER",
                              help="provider adapter for this host (codex-cli, claude-cli, claude-api); overrides CINE_TOASTER_MODEL and current-CLI fallback")
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

    new_parser = subparsers.add_parser(
        "new", help="Start a new production, empty or from a screenplay (.fountain or .fdx)")
    new_parser.add_argument("destination", type=Path, help="a new or empty directory, outside the checkout")
    new_parser.add_argument("--title", required=True)
    new_parser.add_argument("--screenplay", type=Path, help="one breakdown is made per scene it has")
    new_parser.add_argument("--id", help="the production's stable id (default: from the title)")
    new_parser.add_argument("--logline")
    new_parser.set_defaults(function=command_new)

    creation_parser = subparsers.add_parser("creation", help="Explore concepts and save versioned screenplay candidates")
    creation_actions = creation_parser.add_subparsers(dest="creation_command", required=True)
    creation_list = creation_actions.add_parser("list", help="Draft history, pinned inputs and references (JSON)")
    creation_list.add_argument("project", type=Path)
    creation_list.set_defaults(function=command_creation)
    creation_assess = creation_actions.add_parser("assess", help="Record the agent's destination-specific readiness judgment and proposal")
    creation_assess.add_argument("project", type=Path)
    creation_assess.add_argument("--assessment-file", type=Path, required=True)
    creation_assess.add_argument("--expected-revision", type=int, required=True)
    creation_assess.add_argument("--actor")
    creation_assess.add_argument("--actor-kind", choices=("agent", "system"), default="agent")
    creation_assess.set_defaults(function=command_creation)
    creation_decide = creation_actions.add_parser("decide", help="Human approval of an assessed direction, or request changes with guidance")
    creation_decide.add_argument("project", type=Path)
    creation_decide.add_argument("assessment")
    creation_decide.add_argument("--outcome", choices=("approved", "changes_requested"), required=True)
    creation_decide.add_argument("--guidance", default="")
    creation_decide.add_argument("--expected-revision", type=int, required=True)
    creation_decide.add_argument("--actor")
    creation_decide.add_argument("--actor-kind", choices=("human", "agent", "system"), default="human")
    creation_decide.set_defaults(function=command_creation)
    creation_save = creation_actions.add_parser("save", help="Save a new candidate; never replace the canonical screenplay")
    creation_save.add_argument("project", type=Path)
    creation_save.add_argument("--kind", choices=("concept", "screenplay"), required=True)
    creation_save.add_argument("--title", required=True)
    creation_save.add_argument("--text-file", type=Path, required=True)
    creation_save.add_argument("--expected-revision", type=int, required=True)
    creation_save.add_argument("--reference", action="append")
    creation_save.add_argument("--concept")
    creation_save.add_argument("--based-on")
    creation_save.add_argument("--why")
    creation_save.add_argument("--actor")
    creation_save.add_argument("--actor-kind", choices=("human", "agent", "system"), default="human")
    creation_save.set_defaults(function=command_creation)
    creation_round = creation_actions.add_parser("round", help="Record an exploration pass and explicit intended corrections; never approve it")
    creation_round.add_argument("project", type=Path)
    creation_round.add_argument("--title", required=True)
    creation_round.add_argument("--reference", action="append", required=True)
    creation_round.add_argument("--expected-revision", type=int, required=True)
    creation_round.add_argument("--why", required=True)
    creation_round.add_argument("--source", required=True)
    creation_round.add_argument("--follows")
    creation_round.add_argument("--based-on", help="revise this saved round version; retain the earlier version")
    creation_round.add_argument("--correction", action="append", help="previous-reference=current-reference")
    creation_round.add_argument("--actor")
    creation_round.add_argument("--actor-kind", choices=("human", "agent", "system"), default="human")
    creation_round.set_defaults(function=command_creation)

    references_parser = subparsers.add_parser(
        "references", help="What the film looks at -- drafts, probes, paintings -- with where each came from")
    references_actions = references_parser.add_subparsers(dest="references_command", required=True)
    references_list = references_actions.add_parser("list", help="Every reference and what is wrong with it")
    references_list.add_argument("project", type=Path)
    references_list.add_argument("--json", action="store_true")
    references_list.set_defaults(function=command_references)
    references_add = references_actions.add_parser("add", help="Copy files in as a new reference, with its record")
    references_add.add_argument("project", type=Path)
    references_add.add_argument("files", type=Path, nargs="+")
    references_add.add_argument("--title", required=True, help="what it is")
    references_add.add_argument("--kind", required=True, choices=("generated", "found", "made"))
    references_add.add_argument("--made-by", help="who or what made it: a person, a tool and its model")
    references_add.add_argument("--made-on", help="the date it was made (default: today)")
    references_add.add_argument("--source", help="where it came from: a URL, a book, a session")
    references_add.add_argument("--prompt", help="the prompt it was generated from")
    references_add.add_argument("--from", dest="parent", action="append", help="a reference it was made from")
    references_add.add_argument("--licence")
    references_add.add_argument("--credit")
    references_add.add_argument("--note", action="append", help="an observation; repeatable")
    references_add.add_argument("--name", help="the folder's name after the date (default: from the title)")
    references_add.set_defaults(function=command_references)
    references_generate = references_actions.add_parser(
        "generate", help="Make a picture from a description and earlier references, kept as a new reference")
    references_generate.add_argument("project", type=Path)
    references_generate.add_argument("--prompt", required=True, help="what to make, and what to take from each reference")
    references_generate.add_argument("--title", required=True, help="what it is")
    references_generate.add_argument("--from", dest="parent", action="append",
                                     help="a reference whose pictures it is shown, in order; repeatable")
    references_generate.add_argument("--cast", help="who: a cast member, MEMBER or MEMBER@variant (from the sheet)")
    references_generate.add_argument("--style", help="how it is drawn: a style id (the catalog or the film's styles/)")
    references_generate.add_argument("--provider", default="codex-image", choices=("codex-image",))
    references_generate.add_argument("--requested-by", help="who asked for it, when not the person at the terminal")
    references_generate.add_argument("--note", action="append")
    references_generate.add_argument("--name")
    references_generate.add_argument("--dry-run", action="store_true", help="show what would be sent; make nothing")
    references_generate.set_defaults(function=command_references)

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

    add_parser = take_actions.add_parser(
        "add", help="Bring a recording or a still in as a take, with its source, licence and credit")
    add_parser.add_argument("project", type=Path)
    add_parser.add_argument("scene")
    add_parser.add_argument("shot")
    add_parser.add_argument("file", type=Path)
    add_parser.add_argument("--name", help="what this take is called; needed when the shot already has one")
    add_parser.add_argument("--kind", choices=("captured", "archival"), default="captured",
                            help="filmed for this production, or someone else's footage (default: captured)")
    add_parser.add_argument("--source", help="where it came from: a URL, a library, a card")
    add_parser.add_argument("--licence", help="its licence (required for archival)")
    add_parser.add_argument("--credit", help="who must be credited, as the licence asks")
    add_parser.add_argument("--actor")
    add_parser.add_argument("--actor-kind", choices=("human", "agent", "system"), default="human")
    add_parser.add_argument("--json", action="store_true")
    add_parser.set_defaults(function=command_take_add)

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

    footage_parser = subparsers.add_parser(
        "footage", help="Footage from outside, declared in the breakdown: list it, fetch it (CT-0066)")
    footage_actions = footage_parser.add_subparsers(dest="footage_command", required=True)
    for name, text in (("list", "What the shots declare, and whether it is here"),
                       ("fetch", "Download each declared stretch and bring it in as its shot's take")):
        action = footage_actions.add_parser(name, help=text)
        action.add_argument("project", type=Path)
        action.add_argument("--scene")
        action.add_argument("--actor")
        action.add_argument("--actor-kind", choices=("human", "agent", "system"), default="human")
        action.set_defaults(function=command_footage)

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
    assemble_parser.add_argument("--stems", action="store_true",
                                 help="also the sound in its parts (dialogue, room, effects, ambience, music) for a DAW")
    assemble_parser.add_argument("--otio", action="store_true",
                                 help="also the cut as OpenTimelineIO (vN.otio), to finish it in an editor")
    assemble_parser.set_defaults(function=command_assemble)

    sequence_parser = subparsers.add_parser(
        "assemble-sequence", help="Assemble a new, kept version of a sequence from its scenes' versions"
    )
    sequence_parser.add_argument("project", type=Path)
    sequence_parser.add_argument("sequence")
    sequence_parser.add_argument("--version")
    sequence_parser.add_argument("--summary")
    sequence_parser.add_argument("--scenes", action="store_true",
                                 help="first assemble a new version of each of its scenes")
    sequence_parser.set_defaults(function=command_assemble_sequence)

    cast_parser = subparsers.add_parser("cast", help="Cast sheets: list them, or draft them from the scenes")
    cast_actions = cast_parser.add_subparsers(dest="cast_command", required=True)
    for name, text in (("list", "The cast sheets and their voices"),
                       ("propose", "Draft cast sheets from the scenes' own descriptions; writes nothing")):
        action = cast_actions.add_parser(name, help=text)
        action.add_argument("project", type=Path)
        action.set_defaults(function=command_cast)

    finops_parser = subparsers.add_parser(
        "finops", help="What Runpod billed, against the jobs Cine Toaster ran: allocated, unattributed (read only)")
    finops_parser.add_argument("--days", type=int, default=30)
    finops_parser.add_argument("--project", help="also the jobs this film keeps beside its takes (*.job.json)")
    finops_parser.add_argument("--env-file", help="read RUNPOD_API_KEY from this file")
    finops_parser.add_argument("--json", action="store_true")
    finops_parser.set_defaults(function=command_finops)

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
    listing = board_sub.add_parser("candidates", help="Read storyboard drawings, pinned inputs and missing/changed evidence")
    listing.add_argument("project", type=Path)
    listing.add_argument("--scene", default="")
    adding = board_sub.add_parser("add", help="Retain a new storyboard drawing; never approve or publish a master")
    adding.add_argument("project", type=Path)
    adding.add_argument("scene")
    adding.add_argument("shot")
    adding.add_argument("--image", type=Path, required=True)
    adding.add_argument("--title", required=True)
    adding.add_argument("--expected-revision", type=int, required=True)
    adding.add_argument("--reference", action="append", default=[])
    adding.add_argument("--based-on", default="")
    adding.add_argument("--note", default="")
    adding.add_argument("--provenance", type=Path, help="JSON object with prompt and actual generation inputs when known")
    adding.add_argument("--actor", default=os.environ.get("USER", "director"))
    adding.add_argument("--actor-kind", choices=("human", "agent"), default="human")
    animatic_parser = board_sub.add_parser(
        "animatic", help="A sequence's storyboard in time: each shot's latest drawing for its duration (a new file each run)")
    animatic_parser.add_argument("project", type=Path)
    animatic_parser.add_argument("sequence")
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
            item.add_argument("--split", type=float,
                              help="a j or l cut: seconds its sound crosses the picture cut (default 0.8)")
            item.add_argument("--transition-why", default="", help="why this transition")
    cut_parser.set_defaults(function=command_cut)

    board_parser = subparsers.add_parser("board", help="The 3D storyboard: boards per shot, or the scene's animatic")
    board_sub = board_parser.add_subparsers(dest="board_command", required=True)
    board_frames = board_sub.add_parser("frames", help="Still boards (and depth) per shot, from the plan as USD")
    board_frames.add_argument("project", type=Path)
    board_frames.add_argument("scene")
    board_frames.add_argument("--shot", action="append", help="only this shot (repeatable)")
    board_frames.add_argument("--end", action="store_true", help="also each shot's last moment")
    board_frames.add_argument("--width", type=int, default=1280)
    board_frames.add_argument("--height", type=int, default=720)
    board_frames.add_argument("--look", choices=("clay", "colour"), default="clay",
                              help="clay: one grey, like a maquette (default); colour: the plan's colours")
    board_sheet = board_sub.add_parser("sheet", help="The scene's boards as one labelled grid")
    board_sheet.add_argument("project", type=Path)
    board_sheet.add_argument("scene")
    board_animatic = board_sub.add_parser("animatic", help="The scene through its cameras, to check the breakdown")
    board_animatic.add_argument("project", type=Path)
    board_animatic.add_argument("scene")
    board_animatic.add_argument("--width", type=int, default=960)
    board_animatic.add_argument("--height", type=int, default=540)
    board_animatic.add_argument("--step", type=int, default=2, help="render every Nth frame (12 fps at 2)")
    board_parser.set_defaults(function=command_board)

    nerf_parser = subparsers.add_parser("nerf", help="A shot's camera move as a nerfstudio camera path (ns-render)")
    nerf_sub = nerf_parser.add_subparsers(dest="nerf_command", required=True)
    nerf_path = nerf_sub.add_parser("path", help="Write camera_path.json for ns-render camera-path")
    nerf_path.add_argument("project", type=Path)
    nerf_path.add_argument("scene")
    nerf_path.add_argument("shot")
    nerf_path.add_argument("--frames", type=int, default=24)
    nerf_path.add_argument("--width", type=int, default=1280)
    nerf_path.add_argument("--height", type=int, default=720)
    nerf_path.add_argument("--output")
    nerf_parser.set_defaults(function=command_nerf)

    splat_parser = subparsers.add_parser("splat", help="Gaussian splats: a shot's move through its location's splat")
    splat_sub = splat_parser.add_subparsers(dest="splat_command", required=True)
    splat_plate = splat_sub.add_parser("plate", help="Render the shot's camera move through the location's splat")
    splat_plate.add_argument("project", type=Path)
    splat_plate.add_argument("scene")
    splat_plate.add_argument("shot")
    splat_plate.add_argument("--frames", type=int, default=24)
    splat_plate.add_argument("--width", type=int, default=640)
    splat_plate.add_argument("--height", type=int, default=360)
    splat_parser.set_defaults(function=command_splat)

    usd_parser = subparsers.add_parser("usd", help="Export a scene's plan as an OpenUSD stage (CT-0047)")
    usd_sub = usd_parser.add_subparsers(dest="usd_command", required=True)
    usd_export_parser = usd_sub.add_parser("export", help="Room, set pieces, subjects and one camera per shot")
    usd_export_parser.add_argument("project", type=Path)
    usd_export_parser.add_argument("scene")
    usd_export_parser.add_argument("--output", help="the .usda/.usd/.usdc file (default exports/usd/<scene>.usda)")
    usd_parser.set_defaults(function=command_usd)

    vfx_parser = subparsers.add_parser("vfx", help="The VFX catalog and the production's stock elements (CT-0047)")
    vfx_sub = vfx_parser.add_subparsers(dest="vfx_command", required=True)
    for name, text in (("list", "Effects and elements"),
                       ("examples", "Render one example element per delivery form into vfx_elements/ (Blender, FFmpeg)")):
        item = vfx_sub.add_parser(name, help=text)
        item.add_argument("project", type=Path)
    vfx_parser.set_defaults(function=command_vfx)

    continuity_parser = subparsers.add_parser(
        "continuity", help="The continuity ledger: what holds from scene to scene (wardrobe, props, time), and its breaks")
    continuity_parser.add_argument("project", type=Path)
    continuity_parser.add_argument("--scene", help="what holds in this scene")
    continuity_parser.add_argument("--shot", help="... at this shot, after the scene's declared changes")
    continuity_parser.add_argument("--json", action="store_true")
    continuity_parser.set_defaults(function=command_continuity)

    recipes_parser = subparsers.add_parser(
        "recipes", help="Generation recipes: what each path makes, configuration, model files, costs, known failures")
    recipes_parser.add_argument("--health", metavar="RECIPE",
                                help="one endpoint's workers, queue, scaling, and whether scaling down is safe now")
    recipes_parser.add_argument("--batch", nargs=2, metavar=("RECIPE", "JOBS"),
                                help="cold starts and time for JOBS sent together versus one by one")
    recipes_parser.add_argument("--seconds", type=float, help="with --batch: seconds of GPU per job")
    recipes_parser.add_argument("--env-file", help="credentials and endpoint ids, never printed")
    recipes_parser.add_argument("--json", action="store_true")
    recipes_parser.set_defaults(function=command_recipes)

    intake_parser = subparsers.add_parser(
        "intake", help="The format interview: what the format needs, the agent's questions, and your answers")
    intake_parser.add_argument("project", type=Path)
    intake_parser.add_argument("--answer", nargs=2, metavar=("QUESTION", "TEXT"), help="answer one open question")
    intake_parser.add_argument("--withdraw", nargs=2, metavar=("QUESTION", "REASON"),
                               help="take back an open question that needs no answer")
    intake_parser.add_argument("--json", action="store_true")
    intake_parser.set_defaults(function=command_intake)

    status_parser = subparsers.add_parser(
        "status", help="Where the production stands: shots with a take or awaiting one, versions, blockers, next decisions")
    status_parser.add_argument("project", type=Path)
    status_parser.add_argument("--sequence", help="one sequence only")
    status_parser.add_argument("--json", action="store_true")
    status_parser.set_defaults(function=command_status)

    transcribe_parser = subparsers.add_parser(
        "transcribe", help="Word timings for a scene's speaking takes that have none, so trims and subtitles follow the speech")
    transcribe_parser.add_argument("project", type=Path)
    transcribe_parser.add_argument("scene")
    transcribe_parser.add_argument("--language", default="en", help="the language spoken in the takes")
    transcribe_parser.set_defaults(function=command_transcribe)

    migrate_parser = subparsers.add_parser("migrate", help="Migrate a production made outside Cine Toaster (CT-0054)")
    migrate_sub = migrate_parser.add_subparsers(dest="migrate_kind", required=True)
    migrate_singular = migrate_sub.add_parser("singular", help="SINGULAR's layout and vocabulary, into a new directory")
    migrate_singular.add_argument("source", help="the production as it is (never written)")
    migrate_singular.add_argument("target", help="the new directory")
    migrate_singular.add_argument("--replace", action="store_true", help="replace an earlier migration in target")
    migrate_singular.add_argument("--proposals", help="the art-direction proposals folder to bring along")
    migrate_singular.add_argument("--no-git", action="store_true", help="do not start git for the film's text")
    migrate_parser.set_defaults(function=command_migrate)

    style_parser = subparsers.add_parser("style", help="The style catalog: direction, animation techniques, formats (CT-0049)")
    style_sub = style_parser.add_subparsers(dest="style_command", required=True)
    style_list = style_sub.add_parser("list", help="Every style in the catalog")
    style_list.add_argument("project", type=Path)
    style_show = style_sub.add_parser("show", help="What a style means for moves, cuts, performance, format and the prompt")
    style_show.add_argument("project", type=Path)
    style_show.add_argument("id")
    style_parser.set_defaults(function=command_style)

    emotion_parser = subparsers.add_parser("emotion", help="The emotion catalog: describe, ask a model, put on a face (CT-0048)")
    emotion_sub = emotion_parser.add_subparsers(dest="emotion_command", required=True)
    emotion_list = emotion_sub.add_parser("list", help="Every feeling in the catalog")
    emotion_list.add_argument("project", type=Path)
    emotion_show = emotion_sub.add_parser("show", help="What shows, and what a model is asked at each intensity")
    emotion_show.add_argument("project", type=Path)
    emotion_show.add_argument("id")
    emotion_face = emotion_sub.add_parser("face", help="FACS action units and ARKit blendshape weights, as JSON")
    emotion_face.add_argument("project", type=Path)
    emotion_face.add_argument("id")
    emotion_face.add_argument("--intensity", default="clear", choices=("subtle", "clear", "overwhelming"))
    emotion_parser.set_defaults(function=command_emotion)

    track_parser = subparsers.add_parser("track", help="Tracks measured on media, kept, corrected and reused (C7, CT-0080)")
    track_sub = track_parser.add_subparsers(dest="track_command", required=True)
    track_measure = track_sub.add_parser("measure", help="Measure a track (again) on its media")
    track_measure.add_argument("project", type=Path)
    track_measure.add_argument("id")
    track_measure.add_argument("--media", required=True, help="The media, a path in the production")
    track_measure.add_argument("--kind", choices=("point", "plane"), required=True)
    track_measure.add_argument("--region", type=float, nargs=4, default=[0.0, 0.0, 1.0, 1.0],
                               metavar=("X0", "Y0", "X1", "Y1"))
    track_measure.add_argument("--start", type=float)
    track_measure.add_argument("--end", type=float)
    track_status = track_sub.add_parser("status", help="What a track is: stale, weak stretches, corrections")
    track_status.add_argument("project", type=Path)
    track_status.add_argument("id")
    track_correct = track_sub.add_parser("correct", help="Correct one entry (kept apart from the measurement)")
    track_correct.add_argument("project", type=Path)
    track_correct.add_argument("id")
    track_correct.add_argument("index", type=int)
    track_correct.add_argument("at", type=float, nargs="+", help="x y (a point) or four corners' x y")
    track_correct.add_argument("--expect-revision", type=int)
    track_revert = track_sub.add_parser("revert", help="Take corrections out of force, keeping them")
    track_revert.add_argument("project", type=Path)
    track_revert.add_argument("id")
    track_revert.add_argument("--correction")
    track_revert.add_argument("--index", type=int)
    for action in (track_measure, track_correct, track_revert):
        action.add_argument("--rationale", default="")
        action.add_argument("--actor", help="Who is deciding (default: current user)")
        action.add_argument("--actor-kind", choices=("human", "agent", "system"), default="human")
    track_parser.set_defaults(function=command_track)

    models_parser = subparsers.add_parser("models", help="Models that estimate signals: the catalog, and fetching "
                                                         "one at its pinned revision (C8, CT-0081)")
    models_sub = models_parser.add_subparsers(dest="models_command", required=True)
    models_sub.add_parser("list", help="The catalog: kind, licence, revision, fetched or not")
    models_fetch = models_sub.add_parser("fetch", help="Download a model at its pinned revision, checked by hash")
    models_fetch.add_argument("name")
    models_fetch.add_argument("--again", action="store_true", help="Fetch again even when it is here")
    models_parser.set_defaults(function=command_models)

    signal_parser = subparsers.add_parser("signal", help="Signals of media -- depth, segmentation -- as records "
                                                         "(C8, CT-0081)")
    signal_sub = signal_parser.add_subparsers(dest="signal_command", required=True)
    signal_estimate = signal_sub.add_parser("estimate", help="Estimate a signal of a medium with a model")
    signal_estimate.add_argument("project", type=Path)
    signal_estimate.add_argument("id")
    signal_estimate.add_argument("--model", required=True, help="A model of `toast models list`")
    signal_estimate.add_argument("--media", required=True, help="The medium, a path in the production")
    signal_estimate.add_argument("--first", type=int, default=0, help="Its first frame")
    signal_estimate.add_argument("--count", type=int, help="How many frames (default: to the end)")
    signal_estimate.add_argument("--object", action="append", help="SAM 2: NAME[@FRAME]:X,Y[:X,Y...] (pixels)")
    signal_estimate.add_argument("--box", action="append", help="SAM 2: NAME[@FRAME]:X0,Y0,X1,Y1 (pixels)")
    signal_estimate.add_argument("--input-size", type=int, help="Video Depth Anything: the model's input size")
    signal_estimate.add_argument("--threads", type=int)
    signal_estimate.add_argument("--repeat", action="store_true", help="Run twice and record what differed")
    signal_align = signal_sub.add_parser("align", help="Align a relative depth to a metric one over a stretch; "
                                                       "residuals and inverted occlusions recorded")
    signal_align.add_argument("project", type=Path)
    signal_align.add_argument("id")
    signal_align.add_argument("--estimate", required=True, help="The relative depth")
    signal_align.add_argument("--reference", required=True, help="The metric depth of the same pixels")
    signal_align.add_argument("--camera", required=True, help="The reference's camera, stated as seeing the medium")
    signal_align.add_argument("--temporal", choices=("regularized", "shared", "per_frame"), default="regularized")
    signal_align.add_argument("--smoothness", type=float, default=1.0)
    signal_align.add_argument("--first", type=int, default=0)
    signal_align.add_argument("--count", type=int)
    signal_align.add_argument("--region", help="A segmentation limiting the calibration")
    signal_align.add_argument("--keep", type=int, nargs="+", help="Its labels to calibrate on")
    signal_align.add_argument("--leave", type=int, nargs="+", help="Its labels to leave out")
    signal_align.add_argument("--objects", help="A segmentation of instances: each pair of objects ordered")
    signal_compare = signal_sub.add_parser("compare", help="Measure a signal against a reference; recorded as "
                                                           "measured quality")
    signal_compare.add_argument("project", type=Path)
    signal_compare.add_argument("id")
    signal_compare.add_argument("--reference", required=True)
    signal_status = signal_sub.add_parser("status", help="What a signal is: stale, quality, transformations")
    signal_status.add_argument("project", type=Path)
    signal_status.add_argument("id")
    for action in (signal_estimate, signal_align, signal_compare):
        action.add_argument("--actor", help="Who is deciding (default: current user)")
        action.add_argument("--actor-kind", choices=("human", "agent", "system"), default="human")
    signal_parser.set_defaults(function=command_signal)

    render_parser = subparsers.add_parser("render", help="A 3D scene's passes, rendered apart (C8, CT-0081)")
    render_sub = render_parser.add_subparsers(dest="render_command", required=True)
    render_passes = render_sub.add_parser("passes", help="Render a scene's picture, Z and object index; record them")
    render_passes.add_argument("project", type=Path)
    render_passes.add_argument("id")
    scene_given = render_passes.add_mutually_exclusive_group(required=True)
    scene_given.add_argument("--blend", help="A .blend in the production")
    scene_given.add_argument("--recipe", help="A recipe (JSON) in the production")
    render_passes.add_argument("--camera", required=True)
    render_passes.add_argument("--first", type=int, default=1)
    render_passes.add_argument("--last", type=int, required=True)
    render_passes.add_argument("--size", type=int, nargs=2, default=[1280, 720], metavar=("WIDTH", "HEIGHT"))
    render_passes.add_argument("--fps", default="24")
    render_passes.add_argument("--samples", type=int, default=16)
    render_passes.add_argument("--camera-id", help="The production's camera this render's camera is (a shot's, "
                                                   "matched); default <id>/<camera>")
    render_passes.add_argument("--actor", help="Who is deciding (default: current user)")
    render_passes.add_argument("--actor-kind", choices=("human", "agent", "system"), default="human")
    render_status = render_sub.add_parser("status", help="Whether a render still follows from its scene")
    render_status.add_argument("project", type=Path)
    render_status.add_argument("id")
    render_parser.set_defaults(function=command_render)

    sound_parser = subparsers.add_parser("sound", help="The sound catalog and its sources: Freesound, Sonniss, Openverse (CT-0048)")
    sound_sub = sound_parser.add_subparsers(dest="sound_command", required=True)
    sound_list = sound_sub.add_parser("list", help="Ambiences, effects, Foley and music, built in and the production's")
    sound_list.add_argument("project", type=Path)
    sound_preview = sound_sub.add_parser("preview", help="Hear one item alone, at its level (a WAV)")
    sound_preview.add_argument("project", type=Path)
    sound_preview.add_argument("id")
    sound_preview.add_argument("--seconds", type=float, default=0.0)
    sound_preview.add_argument("--output")
    sound_beats = sound_sub.add_parser("beats", help="Hear a music track's tempo and beats and keep them beside it")
    sound_beats.add_argument("project", type=Path)
    sound_beats.add_argument("id")
    sound_search = sound_sub.add_parser("search", help="Search a source; nothing is written")
    sound_search.add_argument("source", choices=("freesound", "sonniss", "openverse"))
    sound_search.add_argument("terms")
    sound_search.add_argument("--count", type=int, default=10)
    sound_search.add_argument("--effects", action="store_true", help="openverse: any audio, not only music")
    sound_search.add_argument("--env-file", help="FREESOUND_API_KEY (read, never printed)")
    sound_fetch = sound_sub.add_parser("fetch", help="Download one item into the production's sounds/ with its licence")
    sound_fetch.add_argument("project", type=Path)
    sound_fetch.add_argument("source", choices=("freesound", "sonniss", "openverse"))
    sound_fetch.add_argument("item", help="the id (Freesound, Openverse) or file path (Sonniss) a search printed")
    sound_fetch.add_argument("--as", dest="as_id", help="the id it takes in the catalog")
    sound_fetch.add_argument("--category", choices=("ambience", "effect", "foley", "music"))
    sound_fetch.add_argument("--says", help="what it is, in a line")
    sound_fetch.add_argument("--env-file", help="FREESOUND_API_KEY (read, never printed)")
    sound_import = sound_sub.add_parser("import", help="Register a library on disk described by its manifest.csv")
    sound_import.add_argument("project", type=Path)
    sound_import.add_argument("folder")
    sound_import.add_argument("--prefix", default="")
    sound_parser.set_defaults(function=command_sound)

    mcp_parser = subparsers.add_parser(
        "mcp", help="Serve a project to Claude Code over MCP (stdio): claude mcp add cine-toaster -- toast mcp <project>")
    mcp_parser.add_argument("project", type=Path)
    mcp_parser.add_argument("--env-file", help="credentials for paid generation (read, never printed)")
    mcp_parser.set_defaults(function=command_mcp)

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
    workflow_start.add_argument("block", help="a generation block's id, a shot outside any block (e.g. P7), "
                                "or `masters`: every master picture of the scene and its approval, no video")
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
    picture_parser.add_argument("--from-drawing", action="store_true",
                                help="the approved storyboard drawing as the next version, cropped to the film's frame")
    picture_parser.add_argument("--offset", type=float, default=0.5,
                                help="with --from-drawing: where the crop sits, 0 (left/top) to 1 (right/bottom)")
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

    still_parser = subparsers.add_parser(
        "still", help="Draw a shot's frame as the cut draws it (a card, a composite), as a PNG; "
        "titles and effects laid over a composite are not in it yet (C6)"
    )
    still_parser.add_argument("project", type=Path)
    still_parser.add_argument("scene")
    still_parser.add_argument("shot")
    still_parser.add_argument("--at", type=float, help="seconds into the shot (default: its middle)")
    still_parser.add_argument("--output", type=Path, help="default: stills/<scene>/<shot>.png in the production")
    still_parser.set_defaults(function=command_still)

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
