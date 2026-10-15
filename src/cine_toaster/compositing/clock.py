"""Timeline time and source time in a graph (C7 step 2, CT-0080; ADR 0023).

Every node of a graph is evaluated at a *local* time: the shot's own time at
the output, and below a `time.remap` or a `time.offset`, the time those make.
A source -- a take given as a port, or a `generate.source` -- turns its local
time into an instant of its *media* by its origin: where its local zero falls
in the file (the cut point of a take, a source's `start`). So the instant of
a source shown by any node is found by walking from that node to the source,
composing each time operation on the way, then adding the source's origin.

That one walk serves three uses: how far (and how far back -- a pre-roll) a
source is read; whether a shot is retimed at all (its sound is then muted
until a policy says otherwise); and where a track is read. A track is data
of its source: it carries its own clock -- a rate and the media instant of its
first entry -- and is looked up at the media instant the source is showing, so
it is right whether the track was measured on the cut, on the whole take, or
elsewhere, and whatever remaps stand between.

A source reached by several paths at different times is legitimate for
pictures (a plate shown straight and retimed); for a track lookup it is
ambiguous, and refused rather than guessed.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any, Callable

from ..errors import ValidationError
from .schema import OPAQUE_PORTS, OPS

Instant = Any  # a Fraction when exact, else a float (seconds)


def reads(node: dict[str, Any]) -> list[str]:
    """The nodes and ports a node reads through its input ports -- not the curves its parameters follow."""

    op = str(node.get("op") or "")
    ports = set(OPAQUE_PORTS.get(op) or (OPS[op].inputs if op in OPS else {}))
    found = []
    for key in ports:
        value = node.get(key)
        for item in value if isinstance(value, list) else [value]:
            if isinstance(item, str):
                found.append(item.split(".", 1)[0])
    return found


def exact_keys(keys: list[Any]) -> Callable[[Fraction], Fraction] | None:
    """Keys a time map can follow exactly: numbers, linear or held between them (a Bezier is not rational).
    None otherwise."""

    points = []
    for key in keys:
        t, value, ease = (key["t"], key["value"], key.get("ease", "linear")) if isinstance(key, dict) else (
            key[0], key[1], "linear")
        if ease not in ("linear", "hold") or isinstance(value, (list, tuple)):
            return None
        points.append((Fraction(str(t)), Fraction(str(value)), ease))
    points.sort(key=lambda point: point[0])

    def at(seconds: Fraction) -> Fraction:
        if seconds <= points[0][0]:
            return points[0][1]
        for (t0, v0, ease), (t1, v1, _) in zip(points, points[1:]):
            if seconds < t1:
                return v0 if ease == "hold" else v0 + (v1 - v0) * (seconds - t0) / (t1 - t0)
        return points[-1][1]

    return at


def remap_at(node: dict[str, Any], nodes: dict[str, Any], curve: Callable[[str], Callable],
             seconds: Instant) -> Instant:
    """The source instant a `time.remap` reads when it is evaluated at `seconds`: exact (a Fraction) when its
    map is a number or linear or held keys and `seconds` is exact; otherwise the map curve's float."""

    import numpy as np

    given = node.get("map")
    if given is None:
        return seconds
    if isinstance(given, (int, float)):
        return Fraction(str(given))
    keyed = nodes.get(given["curve"], {}) if isinstance(given, dict) else {}
    if isinstance(seconds, Fraction) and keyed.get("op") == "curve.keys" and not keyed.get("in"):
        exact = exact_keys(keyed["keys"])
        if exact is not None:
            return exact(seconds)
    return float(np.asarray(curve(given["curve"])(float(seconds))).reshape(-1)[0])


def step(node: dict[str, Any], nodes: dict[str, Any], curve: Callable[[str], Callable], seconds: Instant,
         fps: Any) -> Instant:
    """The local time of a node's input when the node is evaluated at `seconds`."""

    from ..timebase import rate

    op = node.get("op")
    if op == "time.remap":
        return remap_at(node, nodes, curve, seconds)
    if op == "time.offset":
        shift = Fraction(int(node.get("frames", 0) or 0)) / rate(fps)
        return seconds - shift if isinstance(seconds, Fraction) else seconds - float(shift)
    return seconds  # every other op reads its input at its own time (an echo's present, a blend's centre)


def instants(nodes: dict[str, Any], curve: Callable[[str], Callable], fps: Any, start: str, target: str,
             seconds: Instant) -> list[Instant]:
    """Every local time at which `target` is evaluated when `start` is evaluated at `seconds` -- one per
    distinct path, each composing the time operations on it. Empty when `target` is not upstream of `start`."""

    found: list[Instant] = []

    def walk(name: str, at: Instant, trail: frozenset[str]) -> None:
        if name == target:
            if not any(at == seen for seen in found):
                found.append(at)
            return
        node = nodes.get(name)
        if node is None or name in trail:
            return
        inner = step(node, nodes, curve, at, fps)
        for upstream in reads(node):
            walk(upstream, inner, trail | {name})

    walk(start, seconds, frozenset())
    return found


def instant(nodes: dict[str, Any], curve: Callable[[str], Callable], fps: Any, start: str, target: str,
            seconds: Instant) -> Instant | None:
    """The one local time of `target` when `start` is evaluated at `seconds`; refused when paths disagree."""

    found = instants(nodes, curve, fps, start, target, seconds)
    if len(found) > 1:
        values = ", ".join(f"{float(item):.4f} s" for item in found)
        raise ValidationError(f"{start} shows {target} at several instants ({values}): which one a track "
                              f"describes is ambiguous -- read the track below the time operations that split it")
    return found[0] if found else None


def centre(frame: int, fps: Any) -> Fraction:
    """A frame's centre, exactly: where a frame samples its curves (SPEC-0012 §6)."""

    from ..timebase import rate

    return Fraction(2 * frame + 1, 2) / rate(fps)


def sources(graph: dict[str, Any]) -> list[str]:
    """The graph's sources: its picture ports and its `generate.source` nodes."""

    ports = [name for name, kind in (graph.get("ports") or {}).items() if kind in ("picture", "matte", "signal")]
    return ports + [name for name, node in (graph.get("nodes") or {}).items() if node.get("op") == "generate.source"]


def extents(graph: dict[str, Any], frames: int, fps: Any, curve: Callable[[str], Callable]) -> dict[str, tuple[int, int]]:
    """For each source, the first and the last of its local frames the graph's output reads (first < 0 is a
    pre-roll: frames of the source before its local zero), over every output frame and every path. A blend on
    the way takes one frame more."""

    from ..timebase import rate
    from .semantics import remap_samples

    nodes = graph.get("nodes") or {}
    output = str(graph.get("output") or "").split(".")[0]
    blends = any(node.get("op") == "time.remap" and node.get("interpolation") == "blend" for node in nodes.values())
    exact = rate(fps)
    result: dict[str, tuple[int, int]] = {}
    for source in sources(graph):
        low, high = 0, frames - 1
        for frame in range(frames):
            for at in instants(nodes, curve, fps, output, source, centre(frame, fps)):
                picked = [index for index, _ in remap_samples(at, exact, "blend" if blends else "nearest",
                                                              clamp=False)]
                low, high = min(low, min(picked)), max(high, max(picked))
        result[source] = (low, high)
    return result


def media(local: Instant, origin: Instant) -> Instant:
    """A source's local time as an instant of its media."""

    return local + origin if isinstance(local, Fraction) and isinstance(origin, Fraction) else float(local) + float(origin)
