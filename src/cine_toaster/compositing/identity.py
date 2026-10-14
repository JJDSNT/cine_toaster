"""What a node's result is a function of (SPEC-0012 §5), as one hash.

A source is its file's content, its stretch, its colour space and alpha. Any
other node is a canonical JSON of its op, its parameters (a curve by its own
identity, a file it names by content), its inputs' identities in port order,
and the context everything is computed in: the working space, the OCIO
config's own identity, the precision, the frame rate, extent and size, and
the renderer with its version. Change any of these and the identity -- and
every identity downstream -- changes; change nothing and it does not.
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .schema import OPS, OPAQUE_PORTS

#: Bumped whenever the reference computes any op differently, so old results stop matching.
REFERENCE_VERSION = "reference/1"


@lru_cache(maxsize=512)
def _file_hash(path: str, size: int, modified: int) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_hash(path: Path) -> str:
    """A file by its content; read again only when its size or time changes."""

    stat = Path(path).stat()
    return _file_hash(str(Path(path).resolve()), stat.st_size, stat.st_mtime_ns)


def ocio_identity() -> str:
    """The OCIO config's own cache identity: its content, not its name."""

    try:
        from ..color import config

        return config().getCacheID()
    except Exception:  # no OCIO here: the default spaces are computed without it
        return "no-ocio"


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def identities(graph: dict[str, Any], inputs: dict[str, str], *, context: dict[str, Any],
               root: Path | None = None) -> dict[str, str]:
    """Every node's identity. ``inputs`` gives each of the graph's ports an identity already known."""

    nodes = graph["nodes"]
    known: dict[str, str] = dict(inputs)
    base = {"context": context, "ocio": context.get("ocio") or ocio_identity()}

    def resolve(path: str) -> Path:
        candidate = Path(path)
        return (root / candidate) if root and not candidate.is_absolute() else candidate

    def of(name: str) -> str:
        if name in known:
            return known[name]
        node, _, output = name.partition(".")
        if output:
            return _digest({"of": of(node), "output": output})
        spec = nodes[node]
        op = spec["op"]
        definition = OPS.get(op)
        ports = definition.inputs if definition else OPAQUE_PORTS.get(op, {})
        parts: dict[str, Any] = {"op": op, "inputs": {}, "params": {}}
        for key, value in sorted(spec.items()):
            if key == "op":
                continue
            if key in ports:
                values = value if isinstance(value, list) else [value]
                parts["inputs"][key] = [of(str(item)) for item in values]
            elif isinstance(value, dict) and "curve" in value:
                parts["params"][key] = {"curve": of(str(value["curve"]))}
            elif definition and definition.params.get(key) == "file" and isinstance(value, str):
                path = resolve(value)
                parts["params"][key] = {"file": file_hash(path) if path.is_file() else f"missing:{value}"}
            elif op == "generate.source" and key == "take" and isinstance(value, str) and resolve(value).is_file():
                parts["params"][key] = {"file": file_hash(resolve(value))}
            elif op.startswith("opaque.") and key == "textures" and isinstance(value, dict):
                # An opaque node's textures are ports of the graph: known by their identities.
                parts["params"][key] = {uniform: of(str(port)) for uniform, port in sorted(value.items())}
            elif op.startswith("opaque.") and isinstance(value, str) and resolve(value).is_file():
                parts["params"][key] = {"file": file_hash(resolve(value))}  # a shader known by its source
            else:
                parts["params"][key] = value
        known[node] = _digest({**base, **parts})
        return known[node]

    for name in nodes:
        of(name)
    return {name: known[name] for name in nodes}
