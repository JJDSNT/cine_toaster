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
    serve_project(args.project, host=args.host, port=args.port)
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
