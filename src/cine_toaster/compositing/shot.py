"""A shot drawn once: its picture, its effects and its title as one graph (CT-0078, the compositing roadmap).

A shot's picture -- a take, a still, a card, or a composite of layers -- its
effects and its title used to be three passes through the same engine, each
written to a file and read back: an encode between each, and the cut's own
re-encode after. Here they are one graph: each treatment is a fragment whose
port `picture` is the picture so far, chained after it, so the shot is drawn
once, by one renderer, and written once.
"""

from __future__ import annotations

import copy
from typing import Any

from .schema import OPAQUE_PORTS, OPS


def _inputs_of(node: dict[str, Any]) -> set[str]:
    """The keys of a node that name what it reads: its input ports (an opaque node's declared ones)."""

    op = str(node.get("op") or "")
    if op in OPAQUE_PORTS:
        return set(OPAQUE_PORTS[op])
    return set(OPS[op].inputs) if op in OPS else set()


def _renamed(value: Any, names: dict[str, str]) -> Any:
    if isinstance(value, str):
        head, dot, tail = value.partition(".")
        return names[head] + dot + tail if head in names else value
    return value


def chain(base: dict[str, Any] | None, fragment: dict[str, Any], prefix: str) -> dict[str, Any]:
    """`fragment` with its port `picture` fed by `base`'s output; its nodes renamed under `prefix` so none
    meets one of `base`'s. With no `base`, `fragment` itself: its `picture` stays a port of the shot."""

    if base is None:
        return copy.deepcopy(fragment)
    taken = set(base["nodes"]) | set(base.get("ports") or {})
    names: dict[str, str] = {}
    for name in fragment["nodes"]:
        candidate, number = f"{prefix}{name}", 1
        while candidate in taken:
            number += 1
            candidate = f"{prefix}{number}-{name}"
        names[name] = candidate
        taken.add(candidate)
    names["picture"] = base["output"]
    nodes = dict(copy.deepcopy(base["nodes"]))
    for name, node in fragment["nodes"].items():
        reads = _inputs_of(node)
        moved: dict[str, Any] = {}
        for key, value in copy.deepcopy(node).items():
            if key in reads:
                value = [_renamed(item, names) for item in value] if isinstance(value, list) else _renamed(value, names)
            elif isinstance(value, dict) and "curve" in value:  # a parameter following a curve
                value = {**value, "curve": _renamed(value["curve"], names)}
            moved[key] = value
        nodes[names[name]] = moved
    ports = {**(base.get("ports") or {}),
             **{name: kind for name, kind in (fragment.get("ports") or {}).items() if name != "picture"}}
    return {"ports": ports, "nodes": nodes, "output": _renamed(fragment["output"], names)}


def shot_graph(base: dict[str, Any] | None, fragments: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    """The shot's whole graph: `base` (a composite; None when the picture is the port `picture`), then each
    fragment in order, each over what came before."""

    graph = base
    for prefix, fragment in fragments:
        graph = chain(graph, fragment, prefix)
    if graph is None:
        raise ValueError("a shot's graph needs a picture or a treatment")
    return graph
