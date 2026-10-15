"""A retime as a filmmaker writes it, compiled into the graph's `time.remap` (C7 step 4, CT-0080; ADR 0022).

    retime:
      speed: 2                       # constant; or keys of speed over the shot's time:
      speed: [{t: 0, speed: 1}, {beat: 2, speed: 1}, {beat: 3, speed: 3, ease: hold}]
      reverse: true                  # played backwards (from where it would end)
      freeze: 0.8                    # held on the source's 0.8 s for the whole shot
      interpolation: blend           # how a source instant is pictured: nearest (default) or blend

A speed key's time is seconds of the shot (`t`) or one of the music's beats in
the shot (`beat: n`, the n-th from its start) -- so a ramp lands on a beat. The
speed between keys follows the left key's ease: `linear` (the default) or
`hold`; a speed of 0 is a freeze for that stretch. What the picture shows is
the integral of the speed: exact (linear keys of the map) where the speed is
held, sampled finely (every `SAMPLE` seconds, exact at each sample) where it
ramps. Nothing here draws: it only writes a `time.remap` and its map, which the
renderers, the sound (`retime_sound`) and the tracks (`clock`) already follow.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

RETIME_KEYS = ("speed", "reverse", "freeze", "interpolation")
#: Where the speed ramps, the map is sampled this often (seconds): its keys are exact at each sample.
SAMPLE = Fraction(1, 240)
#: How far a map runs when the length it is for is not known (a layer compiled before its shot is cut).
HORIZON = Fraction(3600)


def _number(value: Any) -> Fraction | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        return Fraction(str(value))
    except (ValueError, ZeroDivisionError):
        return None


def speed_keys(spec: Any, beats: list[float] | None, where: str) -> tuple[list[tuple[Fraction, Fraction, str]], list[str]]:
    """The speed keys, as (time, speed, ease), times in seconds -- a beat's time from `beats`."""

    problems: list[str] = []
    if _number(spec) is not None:
        return [(Fraction(0), _number(spec), "hold")], problems
    if not isinstance(spec, list) or not spec:
        return [], [f"{where}'s speed is a number or keys [{{t | beat, speed, ease}}, ...]"]
    keys = []
    for key in spec:
        if not isinstance(key, dict) or _number(key.get("speed")) is None:
            problems.append(f"{where}'s speed key {key!r} has no number `speed`")
            continue
        if key.get("beat") is not None:
            index = key["beat"]
            if not isinstance(index, int) or index < 1:
                problems.append(f"{where}'s key `beat: {index!r}` is the n-th beat of the shot, from 1")
                continue
            if not beats or index > len(beats):
                problems.append(f"{where}'s key falls on beat {index}, which the shot does not have "
                                f"({len(beats or [])} beats in it)")
                continue
            at = Fraction(str(beats[index - 1]))
        elif _number(key.get("t")) is not None:
            at = _number(key["t"])
        else:
            problems.append(f"{where}'s speed key {key!r} has no `t` (seconds) or `beat`")
            continue
        ease = str(key.get("ease", "linear"))
        if ease not in ("linear", "hold"):
            problems.append(f"{where}'s speed key ease is linear or hold, not {ease!r}")
            ease = "linear"
        keys.append((at, _number(key["speed"]), ease))
    keys.sort(key=lambda key: key[0])
    return keys, problems


def map_keys(keys: list[tuple[Fraction, Fraction, str]], horizon: Fraction) -> list[list[Any]]:
    """The map (output seconds -> source seconds) that integrates the speed keys, as linear keys: exact where
    the speed holds, sampled every `SAMPLE` where it ramps, run on at the last speed to `horizon`."""

    if not keys:
        return [[0, 0], [float(horizon), float(horizon)]]
    points: list[tuple[Fraction, Fraction]] = [(Fraction(0), Fraction(0))]
    position = Fraction(0)
    first_speed = keys[0][1]
    if keys[0][0] > 0:  # before the first key, its speed
        position += first_speed * keys[0][0]
        points.append((keys[0][0], position))
    for (t0, v0, ease), (t1, v1, _) in zip(keys, keys[1:]):
        if t1 <= t0:
            continue
        if ease == "hold" or v0 == v1:
            position += v0 * (t1 - t0)
            points.append((t1, position))
            continue
        steps = max(1, int((t1 - t0) / SAMPLE))
        for step in range(1, steps + 1):
            t = t0 + (t1 - t0) * step / steps
            u = t - t0
            # The integral of a speed rising linearly from v0 to v1 over [t0, t1].
            points.append((t, position + v0 * u + (v1 - v0) * u * u / (2 * (t1 - t0))))
        position += (v0 + v1) * (t1 - t0) / 2
    last_time, last_speed = keys[-1][0], keys[-1][1]
    if horizon > last_time:
        points.append((horizon, position + last_speed * (horizon - last_time)))
    return [[_plain(t), _plain(v)] for t, v in points]


def _plain(value: Fraction) -> Any:
    """A key's number: an int when whole, else a float exact enough to read back as the same fraction."""

    return int(value) if value.denominator == 1 else float(value)


def compile_retime(spec: Any, *, length: float | None = None, beats: list[float] | None = None,
                   where: str = "the retime", prefix: str = "retime") -> tuple[dict[str, Any] | None, list[str]]:
    """(a graph with one port, `picture`, and its retimed output; the problems)."""

    if not isinstance(spec, dict):
        return None, [f"{where} is a mapping of {', '.join(RETIME_KEYS)}"]
    unknown = [key for key in spec if key not in RETIME_KEYS]
    problems = [f"{where} has no {', '.join(unknown)} ({', '.join(RETIME_KEYS)})"] if unknown else []
    interpolation = str(spec.get("interpolation") or "nearest")
    if interpolation not in ("nearest", "blend"):
        problems.append(f"{where}'s interpolation is nearest or blend, not {interpolation!r}")
        interpolation = "nearest"
    horizon = Fraction(str(length)) if length else HORIZON
    if spec.get("freeze") is not None:
        held = _number(spec["freeze"])
        if held is None:
            return None, problems + [f"{where}'s freeze is the source's second to hold, a number"]
        keys = [[0, _plain(held)], [_plain(horizon), _plain(held)]]
    else:
        speeds, more = speed_keys(spec.get("speed", 1), beats, where)
        problems += more
        keys = map_keys(speeds, horizon)
        if spec.get("reverse"):
            if not length:
                return None, problems + [f"{where} plays backwards from where it would end: it needs the shot's "
                                         "length (a shot's retime, not a layer's)"]
            end = Fraction(str(keys[-1][1]))
            keys = [[t, _plain(end - Fraction(str(v)))] for t, v in keys]
    if problems:
        return None, problems
    return {"ports": {"picture": "picture"}, "output": f"{prefix}-out",
            "nodes": {f"{prefix}-map": {"op": "curve.keys", "keys": keys},
                      f"{prefix}-out": {"op": "time.remap", "in": "picture", "map": {"curve": f"{prefix}-map"},
                                        "interpolation": interpolation}}}, []
