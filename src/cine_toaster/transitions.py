from __future__ import annotations

import os
import re
import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Any


BUILTIN_TRANSITIONS = Path(__file__).with_name("transition_assets")

#: gl-transitions, a git submodule of the repository (MIT; a few items BSD).
#: A wheel carries its shaders inside the package; a checkout reads the
#: submodule where it lies.
UPSTREAM_NAME = "gl-transitions"
UPSTREAM_SOURCE = "https://github.com/gl-transitions/gl-transitions/blob/master/transitions"
_UPSTREAM_CANDIDATES = (
    Path(__file__).parent / "vendor" / "gl-transitions",
    Path(__file__).resolve().parents[2] / "vendor" / "gl-transitions",
)

_UNIFORM = re.compile(
    r"^\s*uniform\s+(\w+)\s+(\w+)\s*(?:/\*\s*=\s*(.+?)\s*\*/)?\s*;\s*(?://\s*=\s*([^;]+?)\s*(?:;.*)?)?$",
    re.MULTILINE,
)
_HEADER = re.compile(r"^//\s*(author|license)\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_COMPONENTS = {"float": 1, "int": 1, "bool": 1, "vec2": 2, "vec3": 3, "vec4": 4, "ivec2": 2, "ivec3": 3, "ivec4": 4}
#: Uniforms every shader receives from the renderer, never parameters.
_PROVIDED = {"progress", "ratio", "fromTexture", "toTexture"}


class TransitionFormatError(ValueError):
    """Raised when a transition manifest cannot be used safely."""


def upstream_root() -> Path | None:
    """Where the gl-transitions shaders are, or None when the submodule is absent."""

    for candidate in _UPSTREAM_CANDIDATES:
        if (candidate / "transitions").is_dir():
            return candidate
    return None


class UnsupportedShader(TransitionFormatError):
    """A shader needs an input the renderers do not provide, such as a texture."""


def _default(kind: str, raw: str, name: str) -> list[float] | float | bool | int:
    raw = raw.strip()
    count = _COMPONENTS[kind]
    if kind == "bool":
        return raw.lower() in {"true", "1"}
    match = re.fullmatch(r"\w+\s*\((.*)\)", raw)
    values = [float(part) for part in (match[1] if match else raw).split(",") if part.strip()]
    if len(values) == 1 and count > 1:
        values = values * count
    if len(values) != count:
        raise TransitionFormatError(f"Default for {name} has {len(values)} component(s), not {count}")
    if kind.startswith("i") or kind == "int":
        values = [int(value) for value in values]
    return values[0] if count == 1 else values


def shader_params(source: str) -> list[dict[str, Any]]:
    """The parameters a gl-transitions shader declares, with their defaults.

    The convention is `uniform float count; // = 10.0`. A uniform without a
    default cannot be rendered honestly, and a texture is an input neither the
    preview nor the build supplies, so both are refused.
    """

    params = []
    for match in _UNIFORM.finditer(source):
        kind, name = match[1], match[2]
        if name in _PROVIDED:
            continue
        if kind not in _COMPONENTS:
            raise UnsupportedShader(f"Uniform {name} is a {kind}, which no renderer supplies")
        raw = match[3] or match[4]
        if not raw:
            raise UnsupportedShader(f"Uniform {name} declares no default")
        params.append({"name": name, "type": kind, "default": _default(kind, raw, name)})
    return params


def _humanize(stem: str) -> str:
    words = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", stem).replace("_", " ").replace("-", " ").split()
    return " ".join(word if word.isupper() else word.capitalize() for word in words)


def _slug(stem: str) -> str:
    return "-".join(word.lower() for word in _humanize(stem).split())


@lru_cache(maxsize=4)
def _upstream_catalog(root: Path) -> tuple[dict[str, Any], ...]:
    """Every usable upstream shader, as an unreviewed catalog item.

    The shaders ship without guidance: nobody has said when to use one, and
    none declares an FFmpeg stand-in. They are listed so they can be previewed
    and chosen, and rendered by the GL engine; a curated manifest that names
    one as its `upstream` replaces it.
    """

    items = []
    for path in sorted((root / "transitions").glob("*.glsl")):
        source = path.read_text(encoding="utf-8")
        try:
            params = shader_params(source)
        except UnsupportedShader:
            continue
        header = {key.lower(): value for key, value in _HEADER.findall(source)}
        name = _humanize(path.stem)
        items.append(
            {
                "schema_version": 1,
                "id": _slug(path.stem),
                "name": name,
                "kind": "glsl",
                "category": UPSTREAM_NAME,
                "description": f"{name}, from gl-transitions. Not reviewed: nobody has said when it serves a film.",
                "guidance": "",
                "energy": "unknown",
                "motion": "unknown",
                "tags": [],
                "use_when": [],
                "avoid_when": [],
                "license": header.get("license", "MIT"),
                "author": header.get("author", ""),
                "source": f"{UPSTREAM_SOURCE}/{path.name}",
                "duration_ms": 1000,
                "webm_role": "preview",
                "render": {},
                "params": params,
                "curated": False,
                "upstream": f"{UPSTREAM_NAME}:{path.stem}",
                "origin": UPSTREAM_NAME,
                "asset": path.name,
                "preview": None,
                "asset_path": path,
                "preview_path": None,
            }
        )
    return tuple(items)


def _upstream_shader(reference: str) -> Path:
    prefix, _, stem = reference.partition(":")
    root = upstream_root()
    if prefix != UPSTREAM_NAME or not stem or "/" in stem or root is None:
        raise TransitionFormatError(
            f"Upstream shader {reference!r} is unavailable. Run: git submodule update --init"
        )
    path = root / "transitions" / f"{stem}.glsl"
    if not path.is_file():
        raise TransitionFormatError(f"gl-transitions has no shader named {stem!r}")
    return path


def _roots(project_root: Path | None = None) -> list[tuple[str, Path]]:
    roots: list[tuple[str, Path]] = [("built-in", BUILTIN_TRANSITIONS)]
    configured = os.environ.get("CINE_TOASTER_TRANSITIONS_PATH", "")
    for position, raw_path in enumerate(filter(None, configured.split(os.pathsep)), 1):
        roots.append((f"external-{position}", Path(raw_path).expanduser()))
    if project_root is not None:
        roots.append(("project", project_root.expanduser().resolve() / "transitions"))
    return roots


def _safe_asset(directory: Path, relative: str) -> Path:
    if not relative:
        raise TransitionFormatError(f"Empty asset path in {directory / 'transition.toml'}")
    try:
        candidate = (directory / relative).resolve()
        candidate.relative_to(directory.resolve())
    except (OSError, ValueError) as error:
        raise TransitionFormatError(f"Unsafe asset path {relative!r}") from error
    if not candidate.is_file():
        raise TransitionFormatError(f"Missing transition asset: {candidate}")
    return candidate


def _load_manifest(path: Path, origin: str) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            document = tomllib.load(handle)
    except tomllib.TOMLDecodeError as error:
        raise TransitionFormatError(f"Invalid TOML in {path}: {error}") from error

    upstream = str(document.get("upstream", ""))
    # A curated manifest over an upstream shader inherits its licence and author.
    required = ("id", "name", "kind", "description") + (() if upstream else ("license",))
    missing = [key for key in required if not document.get(key)]
    if missing:
        raise TransitionFormatError(f"Missing {', '.join(missing)} in {path}")

    transition_id = str(document["id"])
    kind = str(document["kind"])
    if kind not in {"glsl", "webm"}:
        raise TransitionFormatError(f"Unsupported transition kind {kind!r} in {path}")

    if upstream:
        asset_path = _upstream_shader(upstream)
        asset_name = asset_path.name
        header = {key.lower(): value for key, value in _HEADER.findall(asset_path.read_text(encoding="utf-8"))}
    else:
        asset_name = str(document.get("asset", ""))
        asset_path = _safe_asset(path.parent, asset_name)
        header = {}
    params = shader_params(asset_path.read_text(encoding="utf-8")) if kind == "glsl" else []
    preview_name = str(document.get("preview", ""))
    preview_path = _safe_asset(path.parent, preview_name) if preview_name else None

    return {
        "schema_version": int(document.get("schema_version", 1)),
        "id": transition_id,
        "name": str(document["name"]),
        "kind": kind,
        "category": str(document.get("category", "uncategorized")),
        "description": str(document["description"]),
        "guidance": str(document.get("guidance", "")),
        "energy": str(document.get("energy", "medium")),
        "motion": str(document.get("motion", "neutral")),
        "tags": list(document.get("tags", [])),
        "use_when": list(document.get("use_when", [])),
        "avoid_when": list(document.get("avoid_when", [])),
        "license": str(document.get("license") or header.get("license", "")),
        "author": str(document.get("author") or header.get("author", "")),
        "source": str(document.get("source") or (f"{UPSTREAM_SOURCE}/{asset_name}" if upstream else "")),
        "duration_ms": int(document.get("duration_ms", 1000)),
        "webm_role": str(document.get("webm_role", "preview")),
        # How this item renders on each engine that can execute it,
        # declared by the item rather than inferred by a renderer.
        "render": dict(document.get("render", {})),
        "params": params,
        "curated": True,
        "upstream": upstream or None,
        "origin": origin,
        "asset": asset_name,
        "preview": preview_name or None,
        "asset_path": asset_path,
        "preview_path": preview_path,
    }


def list_transitions(project_root: Path | None = None) -> list[dict[str, Any]]:
    """Load built-in, external, and project transition catalogs.

    Later roots override earlier ones by id, so a project may deliberately pin
    or customize a shared transition without modifying the application.
    """

    by_id: dict[str, dict[str, Any]] = {}
    upstream = upstream_root()
    if upstream is not None:
        for item in _upstream_catalog(upstream):
            by_id[item["id"]] = dict(item)
    for origin, root in _roots(project_root):
        if not root.is_dir():
            continue
        for manifest in sorted(root.glob("*/transition.toml")):
            transition = _load_manifest(manifest, origin)
            # A reviewed manifest over an upstream shader replaces the raw item.
            if transition["upstream"]:
                for key in [k for k, v in by_id.items() if v["upstream"] == transition["upstream"] and not v["curated"]]:
                    del by_id[key]
            by_id[transition["id"]] = transition
    return sorted(by_id.values(), key=lambda item: (item["category"], item["name"]))


def public_transition(transition: dict[str, Any]) -> dict[str, Any]:
    value = {key: item for key, item in transition.items() if not key.endswith("_path")}
    transition_id = transition["id"]
    value["asset_url"] = f"/transition-assets/{transition_id}/{transition['asset']}"
    if transition["preview"]:
        value["preview_url"] = f"/transition-assets/{transition_id}/{transition['preview']}"
    elif transition["kind"] == "webm":
        value["preview_url"] = value["asset_url"]
    else:
        value["preview_url"] = None
    return value


def transition_asset_path(
    transition_id: str,
    filename: str,
    project_root: Path | None = None,
) -> Path | None:
    for transition in list_transitions(project_root):
        if transition["id"] != transition_id:
            continue
        for key in ("asset_path", "preview_path"):
            path = transition.get(key)
            if path is not None and path.name == filename:
                return path
    return None
