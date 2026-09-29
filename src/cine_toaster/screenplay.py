"""The screenplay, read into scenes and units a shot can point at (SPEC-0006).

The authored `.fountain` file is only read (ADR 0006). This module is the one
place that talks to screenplay-tools, so replacing or vendoring the parser later
changes one file.

A shot points at the screenplay by text, not by position: `covers.from` is the
start of a unit's text, and `CHARACTER: words` restricts it to that character's
speech. Rewriting another part of the screenplay does not break the link. A unit
is what a person would point at -- an action paragraph, or a whole speech with
its parentheticals -- not the parser's finer elements.
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from dataclasses import dataclass, field
from typing import Any

from .geometry import Finding

#: How alike an authored line must be to a screenplay line to count as the same
#: line, drifted, rather than a different one.
DRIFT_SIMILARITY = 0.6

#: Parser element types that open a new unit, mapped to the unit's kind.
_UNIT_KINDS = {"ACTION": "action", "TRANSITION": "transition", "LYRIC": "lyric"}


@dataclass(slots=True)
class Unit:
    """One addressable piece of a screenplay scene."""

    index: int
    kind: str  # heading | action | speech | transition | lyric
    text: str
    speaker: str = ""
    extension: str = ""
    dual: bool = False
    # A speech's ordered parts: ("parenthetical" | "dialogue" | "lyric", text).
    parts: list[tuple[str, str]] = field(default_factory=list)

    def anchor_text(self) -> str:
        return self.text

    def public_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"index": self.index, "kind": self.kind, "text": self.text}
        if self.kind == "speech":
            data.update(
                speaker=self.speaker,
                extension=self.extension,
                dual=self.dual,
                parts=[{"kind": kind, "text": text} for kind, text in self.parts],
            )
        return data


@dataclass(slots=True)
class ScriptScene:
    heading: str
    number: str
    occurrence: int
    units: list[Unit] = field(default_factory=list)

    def speeches(self) -> list[Unit]:
        return [unit for unit in self.units if unit.kind == "speech"]


@dataclass(slots=True)
class Screenplay:
    scenes: list[ScriptScene] = field(default_factory=list)
    title: str = ""

    def find_scene(self, heading: str, occurrence: int = 1) -> ScriptScene | None:
        wanted = normalize_heading(heading)
        matches = [scene for scene in self.scenes if normalize_heading(scene.heading) == wanted]
        if 1 <= occurrence <= len(matches):
            return matches[occurrence - 1]
        return None


def normalize(text: str) -> str:
    """Compare text the way a person reads it: case, spacing, quotes, dashes."""

    text = unicodedata.normalize("NFKC", text or "")
    text = (
        text.replace("‘", "'")
        .replace("’", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("–", "-")
        .replace("—", "-")
        .replace("…", "...")
    )
    # Emphasis is how a line looks, not what it says: an anchor quoted without
    # the asterisks still finds a line imported from Final Draft in bold.
    text = re.sub(r"(\*{1,3}|_)(?=\S)(.+?)(?<=\S)\1", r"\2", text)
    return re.sub(r"\s+", " ", text).strip().casefold()


def normalize_heading(text: str) -> str:
    """A heading without its scene number (`#12#`) or the forcing dot."""

    text = re.sub(r"#[^#]*#\s*$", "", text or "").strip()
    return normalize(text.lstrip("."))


def parse(text: str) -> Screenplay:
    """Parse Fountain into scenes of addressable units."""

    from screenplay_tools.fountain.parser import Parser

    parser = Parser()
    parser.add_text(text)
    parser.finalize()
    script = parser.script

    screenplay = Screenplay()
    for entry in getattr(script, "titleEntries", []) or []:
        if str(getattr(entry, "key", "")).lower() == "title":
            screenplay.title = entry.text.strip()

    occurrences: dict[str, int] = {}
    current: ScriptScene | None = None
    speech: Unit | None = None

    def scene() -> ScriptScene:
        nonlocal current
        if current is None:
            # Material before the first heading still belongs somewhere.
            current = ScriptScene(heading="", number="", occurrence=1)
            screenplay.scenes.append(current)
        return current

    def unit(kind: str, text: str, **extra: Any) -> Unit:
        target = scene()
        item = Unit(index=len(target.units), kind=kind, text=text, **extra)
        target.units.append(item)
        return item

    for element in script.elements:
        kind = element.type.name
        if kind == "HEADING":
            heading = element.text.strip()
            key = normalize_heading(heading)
            occurrences[key] = occurrences.get(key, 0) + 1
            current = ScriptScene(
                heading=heading,
                number=str(getattr(element, "scene_number", "") or ""),
                occurrence=occurrences[key],
            )
            screenplay.scenes.append(current)
            speech = None
            unit("heading", heading)
        elif kind == "CHARACTER":
            speech = unit(
                "speech",
                "",
                speaker=str(getattr(element, "name", "") or "").strip(),
                extension=str(getattr(element, "extension", "") or "").strip(),
                dual=bool(getattr(element, "is_dual_dialogue", False)),
            )
        elif kind in ("DIALOGUE", "PARENTHETICAL") or (kind == "LYRIC" and speech is not None):
            if speech is None:
                continue
            part = kind.lower()
            speech.parts.append((part, element.text.strip()))
            if part != "parenthetical":
                # Line breaks inside a speech are kept in its parts; the unit's
                # text reads as one line, for display and for anchors.
                flat = " ".join(element.text.split())
                speech.text = (speech.text + " " + flat).strip()
        elif kind == "ACTION":
            speech = None
            # The parser merges consecutive action paragraphs into one element.
            # A shot boundary usually falls between paragraphs, so each blank-line
            # separated paragraph is its own unit.
            for paragraph in re.split(r"\n\s*\n", element.text):
                if paragraph.strip():
                    unit("action", paragraph.strip())
        elif kind in _UNIT_KINDS:
            speech = None
            unit(_UNIT_KINDS[kind], element.text.strip())
        else:
            # Page breaks, sections, synopses: structure, not something a shot holds.
            speech = None
    return screenplay


# --- Anchors and coverage ----------------------------------------------------


def _split_anchor(anchor: str) -> tuple[str, str]:
    """`MARA: I never` -> (MARA, I never); plain text -> ('', text)."""

    head, sep, rest = anchor.partition(":")
    if sep and head.strip() and head.strip() == head.strip().upper() and any(c.isalpha() for c in head):
        return head.strip(), rest.strip()
    return "", anchor.strip()


def resolve_anchor(scene: ScriptScene, anchor: str) -> list[Unit]:
    """Every unit in the scene whose text starts with the anchor."""

    speaker, text = _split_anchor(str(anchor or ""))
    wanted = normalize(text)
    if not wanted:
        return []
    matches = []
    for unit in scene.units:
        if speaker and (unit.kind != "speech" or normalize(unit.speaker) != normalize(speaker)):
            continue
        if normalize(unit.anchor_text()).startswith(wanted):
            matches.append(unit)
    return matches


@dataclass(slots=True)
class Coverage:
    units: list[Unit]
    problems: list[Finding]


def _ranges(covers: Any) -> list[dict[str, Any]]:
    if isinstance(covers, dict):
        return [covers]
    if isinstance(covers, str):
        return [{"from": covers}]
    return [item if isinstance(item, dict) else {"from": item} for item in covers or []]


def shot_coverage(
    scene: ScriptScene,
    covers: Any,
    *,
    scene_id: str,
    shot_id: str,
) -> Coverage:
    """The units a shot covers, in screenplay order, and anything unresolved."""

    covered: dict[int, Unit] = {}
    problems: list[Finding] = []
    for entry in _ranges(covers):
        bounds: list[Unit] = []
        for key in ("from", "to"):
            anchor = entry.get(key) if key == "from" else entry.get(key, entry.get("from"))
            if anchor in (None, ""):
                problems.append(_anchor_problem("script_anchor_missing", scene_id, shot_id, anchor, []))
                break
            matches = resolve_anchor(scene, str(anchor))
            if not matches:
                problems.append(_anchor_problem("script_anchor_missing", scene_id, shot_id, anchor, []))
                break
            if len(matches) > 1:
                problems.append(
                    _anchor_problem("script_anchor_ambiguous", scene_id, shot_id, anchor, matches)
                )
                break
            bounds.append(matches[0])
        if len(bounds) != 2:
            continue
        start, end = sorted(bounds, key=lambda unit: unit.index)
        for unit in scene.units[start.index : end.index + 1]:
            covered[unit.index] = unit
    return Coverage([covered[index] for index in sorted(covered)], problems)


def _anchor_problem(
    code: str, scene_id: str, shot_id: str, anchor: Any, matches: list[Unit]
) -> Finding:
    if code == "script_anchor_ambiguous":
        candidates = "; ".join(
            f"{(unit.speaker + ': ') if unit.speaker else ''}{unit.text[:50]}" for unit in matches[:4]
        )
        message = (
            f"Shot {shot_id} covers from {anchor!r}, which matches {len(matches)} places in the "
            f"screenplay scene: {candidates}. Lengthen the anchor."
        )
    else:
        message = (
            f"Shot {shot_id} covers {anchor!r}, which is not in its screenplay scene. The "
            "screenplay may have been rewritten."
        )
    return Finding(
        code=code,
        severity="error",
        message=message,
        scene_id=scene_id,
        shots=(shot_id,),
    )


def compare_lines(
    authored: list[dict[str, Any]],
    speeches: list[Unit],
    *,
    scene_id: str,
    shot_id: str,
) -> tuple[list[dict[str, Any]], list[Finding]]:
    """Attach a shot's authored line metadata to the screenplay speeches it covers.

    The screenplay's words are canonical. An authored line that differs is
    reported, not preferred; one that matches nothing is advice, since it may be
    a deliberate ad-lib.
    """

    findings: list[Finding] = []
    remaining = list(speeches)
    matched: dict[int, dict[str, Any]] = {}
    for line in authored:
        who = normalize(str(line.get("who", "")))
        text = normalize(str(line.get("text", "")))
        candidates = [unit for unit in remaining if not who or normalize(unit.speaker) == who]
        exact = next((unit for unit in candidates if normalize(unit.text) == text), None)
        if exact is not None:
            matched[exact.index] = line
            remaining.remove(exact)
            continue
        scored = [
            (SequenceMatcher(None, text, normalize(unit.text)).ratio(), unit.index, unit)
            for unit in candidates
            if text
        ]
        best = max(scored, default=None, key=lambda item: (item[0], -item[1]))
        close = best[2] if best and best[0] >= DRIFT_SIMILARITY else None
        if close is not None:
            matched[close.index] = line
            remaining.remove(close)
            findings.append(
                Finding(
                    code="line_drift",
                    severity="warning",
                    message=(
                        f"Shot {shot_id}: {line.get('who') or 'a line'} reads "
                        f"{str(line.get('text', ''))[:60]!r} in the breakdown and "
                        f"{close.text[:60]!r} in the screenplay. One of them is out of date."
                    ),
                    scene_id=scene_id,
                    shots=(shot_id,),
                )
            )
            continue
        findings.append(
            Finding(
                code="line_unscripted",
                severity="advice",
                message=(
                    f"Shot {shot_id} has a line by {line.get('who') or 'someone'} that the "
                    f"screenplay does not contain here: {str(line.get('text', ''))[:60]!r}."
                ),
                scene_id=scene_id,
                shots=(shot_id,),
            )
        )

    dialogue = []
    for unit in speeches:
        entry = {
            "unit": unit.index,
            "who": unit.speaker,
            "extension": unit.extension,
            "dual": unit.dual,
            "text": unit.text,
            "parts": [{"kind": kind, "text": text} for kind, text in unit.parts],
        }
        meta = matched.get(unit.index)
        if meta:
            for key in ("delivery", "voice", "mix", "en"):
                if meta.get(key):
                    entry[key] = meta[key]
        dialogue.append(entry)
    return dialogue, findings


def uncovered_dialogue(
    scene: ScriptScene,
    covered: set[int],
    *,
    scene_id: str,
) -> list[Finding]:
    findings = []
    for unit in scene.speeches():
        if unit.index in covered:
            continue
        findings.append(
            Finding(
                code="dialogue_uncovered",
                severity="warning",
                message=(
                    f"{unit.speaker}: {unit.text[:70]!r} is in the screenplay but no shot "
                    "covers it. It is a line nobody films."
                ),
                scene_id=scene_id,
            )
        )
    return findings


def suggest_links(scene: ScriptScene, shots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Propose `covers` for shots that carry authored lines but no coverage."""

    suggestions = []
    for shot in shots:
        if shot.get("covers") or not shot.get("lines"):
            continue
        anchors = []
        for line in shot["lines"]:
            who = normalize(str(line.get("who", "")))
            text = normalize(str(line.get("text", "")))
            for unit in scene.speeches():
                if who and normalize(unit.speaker) != who:
                    continue
                if text and (normalize(unit.text) == text or normalize(unit.text).startswith(text[:30])):
                    words = " ".join(unit.text.split()[:6])
                    anchors.append((unit.index, f"{unit.speaker}: {words}", normalize(unit.text) == text))
                    break
        if anchors:
            anchors.sort()
            suggestions.append(
                {
                    "shot_id": shot["id"],
                    "from": anchors[0][1],
                    "to": anchors[-1][1],
                    "exact": all(exact for _, _, exact in anchors),
                    "matched": len(anchors),
                    "lines": len(shot["lines"]),
                }
            )
    return suggestions


def suggest_scene(screenplay: Screenplay, shots: list[dict[str, Any]]) -> tuple[ScriptScene, int] | None:
    """The screenplay scene sharing the most authored lines with these shots."""

    wanted = [
        (normalize(str(line.get("who", ""))), normalize(str(line.get("text", ""))))
        for shot in shots
        for line in shot.get("lines") or []
        if line.get("text")
    ]
    if not wanted:
        return None
    best: tuple[ScriptScene, int] | None = None
    for scene in screenplay.scenes:
        spoken = {(normalize(unit.speaker), normalize(unit.text)) for unit in scene.speeches()}
        texts = {text for _, text in spoken}
        hits = sum(1 for who, text in wanted if (who, text) in spoken or (not who and text in texts))
        if hits and (best is None or hits > best[1]):
            best = (scene, hits)
    return best

