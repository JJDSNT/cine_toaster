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


def shader_params(source: str, inputs: Any = ()) -> list[dict[str, Any]]:
    """The parameters a gl-transitions shader declares, with their defaults.

    The convention is `uniform float count; // = 10.0`. A uniform without a
    default cannot be rendered honestly, and is refused. A texture
    (`sampler2D`) is an input: allowed when the item names a picture for it in
    ``inputs`` (SPEC-0011), refused otherwise.
    """

    params = []
    for match in _UNIFORM.finditer(source):
        kind, name = match[1], match[2]
        if name in _PROVIDED or (kind == "sampler2D" and name in inputs):
            continue
        if kind == "sampler2D":
            raise UnsupportedShader(f"Uniform {name} is a texture, and the item names no picture for it")
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
                "inputs": {},
                "softness": 0.0,
                "graph": None,
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
    # A curated manifest over an upstream shader inherits its licence and author. A recipe that replaces one
    # (CT-0076) keeps the name, so the raw shader is not listed beside it, but is its own work: no shader is read.
    replaces = upstream if document.get("kind") == "graph" else ""
    upstream = "" if replaces else upstream
    required = ("id", "name", "kind", "description") + (() if upstream else ("license",))
    missing = [key for key in required if not document.get(key)]
    if missing:
        raise TransitionFormatError(f"Missing {', '.join(missing)} in {path}")

    transition_id = str(document["id"])
    kind = str(document["kind"])
    if kind not in {"glsl", "webm", "matte", "graph"}:
        raise TransitionFormatError(f"Unsupported transition kind {kind!r} in {path}")

    if upstream:
        asset_path = _upstream_shader(upstream)
        asset_name = asset_path.name
        header = {key.lower(): value for key, value in _HEADER.findall(asset_path.read_text(encoding="utf-8"))}
    elif kind in ("matte", "graph") and not document.get("asset"):
        # A matte item draws with the host's own matte renderer; it has no shader (SPEC-0011).
        asset_name, asset_path, header = "", None, {}
    else:
        asset_name = str(document.get("asset", ""))
        asset_path = _safe_asset(path.parent, asset_name)
        header = {}
    # Pictures the item gives its renderer: a matte, an overlay, a shader's textures (SPEC-0011).
    declared = document.get("inputs") or {}
    inputs = {name: _safe_asset(path.parent, str(value)) for name, value in declared.items() if isinstance(value, str)}
    softness = float(declared.get("softness", 0.0) or 0.0) if isinstance(declared, dict) else 0.0
    params = shader_params(asset_path.read_text(encoding="utf-8"), inputs) if kind == "glsl" else []
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
        "inputs": inputs,
        "softness": softness,
        # A recipe of SPEC-0012 primitives (ADR 0022), checked when the catalog loads.
        "graph": _recipe(document.get("graph"), path),
        # Why a reviewed shader stays a closed program and is not a recipe of primitives (CT-0076).
        "opaque_reason": str(document.get("opaque_reason", "")),
        "curated": True,
        "upstream": (upstream or replaces) or None,
        "origin": origin,
        "asset": asset_name,
        "preview": preview_name or None,
        "asset_path": asset_path,
        "preview_path": preview_path,
    }


def _recipe(graph: Any, path: Path) -> dict[str, Any] | None:
    if not graph:
        return None
    from .compositing.schema import validate

    problems = validate(graph)
    for name in ("from", "to", "progress"):
        if name not in (graph.get("ports") or {}):
            problems.append(("composite_input_missing", f"a join's recipe has a port {name!r}"))
    if problems:
        raise TransitionFormatError(f"The graph in {path} is not valid: " + "; ".join(text for _, text in problems))
    return graph


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
    value["inputs"] = {name: path.name for name, path in (transition.get("inputs") or {}).items()}
    value["asset_url"] = f"/transition-assets/{transition_id}/{transition['asset']}" if transition["asset"] else None
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
        for path in [transition.get("asset_path"), transition.get("preview_path"),
                     *(transition.get("inputs") or {}).values()]:
            if path is not None and path.name == filename:
                return path
    return None


def _sample_pictures(size: tuple[int, int]) -> dict[str, Any]:
    """Two shots and a matte to show a recipe with: a warm and a cool gradient, and soft dark blobs."""

    import numpy as np

    width, height = size
    y, x = np.mgrid[0:height, 0:width].astype(np.float32)
    u, v = x / max(width - 1, 1), y / max(height - 1, 1)
    warm = np.dstack([0.9 - 0.4 * v, 0.35 + 0.3 * u, 0.12 + 0.1 * v, np.ones_like(u)])
    cool = np.dstack([0.08 + 0.1 * u, 0.25 + 0.3 * v, 0.75 - 0.3 * u, np.ones_like(u)])
    # Detail a blur or a warp can be seen on: thin lines on one, rings on the other.
    lines = (np.abs(np.mod(x, 40) - 20) < 2) | (np.abs(np.mod(y, 40) - 20) < 2)
    rings = np.abs(np.mod(np.hypot(x - width / 2, y - height / 2), 36) - 18) < 3
    warm[lines, :3] *= 0.35
    cool[rings, :3] = cool[rings, :3] * 0.4 + 0.5
    matte = np.ones_like(u)
    for cx, cy, r, shade in ((0.31, 0.47, 0.55, 0.0), (0.73, 0.33, 0.4, 0.27), (0.66, 0.83, 0.45, 0.47),
                             (0.14, 0.17, 0.32, 0.67)):
        reach = np.clip(np.hypot((u - cx) * width / height, v - cy) / r, 0, 1)
        matte = np.minimum(matte, shade + (1 - shade) * reach)
    from .compositing.reference import decode_srgb

    matte = decode_srgb(matte)  # as a matte drawn in an image file arrives: decoded to linear light
    return {"from": warm.astype(np.float32), "to": cool.astype(np.float32),
            "matte_clip": np.dstack([matte, matte, matte, np.ones_like(matte)]).astype(np.float32)}


def render_preview(transition: dict[str, Any], destination: Path, *, seconds: float = 2.0, fps: int = 24,
                   size: tuple[int, int] = (640, 360)) -> Path:
    """A recipe's preview clip, drawn from its graph by the renderers every join uses (ADR 0022, CT-0072).

    A `matte` item is previewed through the matte join's own graph with a sample matte, so the browser
    holds no copy of the rule. The clip is VP9 WebM, which every browser plays.
    """

    import shutil
    import subprocess
    import tempfile

    from .compositing import reference
    from .compositing.gl import renderer_for
    from .mattes import recipe as matte_recipe

    graph = matte_recipe(False) if transition["kind"] == "matte" else transition.get("graph")
    if not graph:
        raise TransitionFormatError(f"{transition['id']} has no graph to preview")
    frames = max(1, round(seconds * fps))
    inputs = {name: value for name, value in _sample_pictures(size).items() if name in graph["ports"]}
    for name, path in (transition.get("inputs") or {}).items():  # the recipe's own pictures: a luma, a map
        if name in graph["ports"]:
            inputs[name] = reference.read(Path(path), frames, size, fps)
    pictures, _, _ = reference.render(graph, inputs, frames=frames, size=size, fps=fps, cache=False,
                                      renderer=renderer_for(graph))
    with tempfile.TemporaryDirectory() as work:
        drawn = reference.write(pictures, Path(work) / "preview.mp4", fps)
        subprocess.run([shutil.which("ffmpeg") or "ffmpeg", "-y", "-loglevel", "error", "-i", str(drawn), "-c:v",
                        "libvpx-vp9", "-b:v", "0", "-crf", "36", "-pix_fmt", "yuv420p", "-an", str(destination)],
                       check=True)
    return Path(destination)
