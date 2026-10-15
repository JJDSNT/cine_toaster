"""A composed card -- words on the look's background -- as a SPEC-0012 graph (ADR 0022).

A card is data, not a generated image: the same shot draws the same card. It
is drawn by the renderers every composite uses; until CT-0072 it was drawn by
PIL in the quick build, a third way of making a picture.
"""

from __future__ import annotations

from typing import Any

#: Where each line sits, as the share of the frame's height to its centre, and its size in pixels at 720 lines.
_LINES = (("headline", 88), ("subhead", 30), ("body", 26))
_GAP = {"headline": 110, "subhead": 50}


def _linear(value: Any, fallback: str) -> list[float]:
    """A palette's sRGB hex as a linear colour, as the graph works (the display encoding is the writer's)."""

    text = str(value or "").strip()
    text = text if text.startswith("#") and len(text) == 7 else fallback
    encoded = [int(text[index:index + 2], 16) / 255.0 for index in (1, 3, 5)]
    return [round(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4, 6) for c in encoded] + [1.0]


def is_card(shot: dict[str, Any]) -> bool:
    """A composed shot with words to draw (a plain solid is held, not composited)."""

    return shot.get("source") == "composed" and shot.get("engine") != "solid" and bool(lines(shot))


def lines(shot: dict[str, Any]) -> dict[str, str]:
    text = shot.get("text") if isinstance(shot.get("text"), dict) else {}
    found = {"headline": str(text.get("headline") or "").upper(), "subhead": str(text.get("subhead") or ""),
             "body": str(text.get("body") or "")}
    return {key: value for key, value in found.items() if value}


def recipe(shot: dict[str, Any], look: dict[str, Any] | None) -> dict[str, Any]:
    """The card as a graph with no ports: the background, and each line laid over it, centred."""

    palette = (look or {}).get("palette") or {}
    ink = _linear(palette.get("ink"), "#f2ead9")
    colours = {"headline": ink, "subhead": _linear(palette.get("accent"), "#38b6a8"), "body": ink}
    nodes: dict[str, Any] = {"background": {"op": "generate.solid",
                                            "colour": _linear(palette.get("background"), "#0b0b16")}}
    below, top = "background", 270
    for key, size in _LINES:
        words = lines(shot).get(key)
        if not words:
            continue
        nodes[key] = {"op": "generate.text", "text": words, "size": size, "colour": colours[key],
                      "position": [0.5, round((top + size / 2) / 720, 4)]}
        nodes[f"{key}-over"] = {"op": "merge.over", "front": key, "back": below}
        below, top = f"{key}-over", top + _GAP.get(key, 0)
    return {"ports": {}, "nodes": nodes, "output": below}
