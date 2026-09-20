from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from .index import ProjectIndex, build_index, index_path_for
from .model import ProjectItem
from .web import serve_project


SOURCE_EXAMPLES = Path(__file__).parents[2] / "examples"
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
    template = DEMO_TEMPLATES[args.template]
    source = demo_template_path(args.template)
    if not source.is_dir():
        print(f"Demo project template is unavailable: {source}", file=sys.stderr)
        return 2
    shutil.copytree(source, destination)
    print(f"Created {template['title']} demo production at {destination}")
    print(f"Open it with: toast serve {destination}")
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
    demo_parser.set_defaults(function=command_demo)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.function(args)
    except (FileNotFoundError, NotADirectoryError, PermissionError) as error:
        parser.error(str(error))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
