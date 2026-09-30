"""Who speaks when in a take: the declared lines aligned to the spoken words (CT-0040).

No diarization model: the breakdown already says who says what, in order, and
word timings say when words were spoken. Aligning the two gives each line its
span, and so each speaker theirs. Standalone -- it imports nothing -- so the
voice worker, which runs in its own environment, can use it too.
"""

from __future__ import annotations

import difflib
import re
from typing import Any


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower().replace("’", "'"))


def align(lines: list[dict[str, Any]], words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each line's time span: [{who, text, start, end}] in order.

    `lines` are the declared lines ({who, text}); `words` are the spoken ones
    ({word, start, end}). Words the matcher cannot place take the line of the
    nearest placed word before them, else after them.
    """

    expected: list[int] = []
    tokens: list[str] = []
    for index, line in enumerate(lines):
        for token in _tokens(str(line.get("text") or "")):
            tokens.append(token)
            expected.append(index)
    spoken = [(_tokens(str(word.get("word") or "")) or [""])[0] for word in words]
    owner: list[int | None] = [None] * len(words)
    matcher = difflib.SequenceMatcher(a=tokens, b=spoken, autojunk=False)
    for tag, a1, a2, b1, b2 in matcher.get_opcodes():
        if tag == "equal":
            for offset in range(b2 - b1):
                owner[b1 + offset] = expected[a1 + offset]
        elif tag == "replace":
            # Misheard words stand where the declared ones were: they keep those lines, in proportion.
            for offset in range(b2 - b1):
                owner[b1 + offset] = expected[a1 + min(a2 - a1 - 1, offset * (a2 - a1) // (b2 - b1))]
        # "insert" (a filler, a word nobody wrote) is filled from its neighbours below.
    # Fill the gaps from the neighbours, keeping lines in order.
    last = None
    for position, value in enumerate(owner):
        if value is None:
            owner[position] = last
        else:
            last = value
    following = None
    for position in range(len(owner) - 1, -1, -1):
        if owner[position] is None:
            owner[position] = following
        else:
            following = owner[position]
    spans = []
    for index, line in enumerate(lines):
        mine = [words[position] for position, value in enumerate(owner) if value == index]
        if mine:
            spans.append({"who": line.get("who", ""), "text": line.get("text", ""),
                          "start": float(mine[0]["start"]), "end": float(mine[-1]["end"])})
    return spans


def segments(spans: list[dict[str, Any]], length: float, pad: float = 0.15) -> list[dict[str, Any]]:
    """Contiguous stretches of the take, one speaker each, covering it end to end.

    Consecutive lines of the same speaker join; between two speakers the cut
    falls halfway through the pause. The first stretch starts at 0 and the
    last ends at `length`, so nothing of the take is left unconverted or
    converted twice.
    """

    merged: list[dict[str, Any]] = []
    for span in spans:
        if merged and merged[-1]["who"] == span["who"]:
            merged[-1]["end"] = span["end"]
        else:
            merged.append({"who": span["who"], "start": span["start"], "end": span["end"]})
    if not merged:
        return []
    cuts = [0.0]
    for before, after in zip(merged, merged[1:]):
        cuts.append(max(before["end"], min(after["start"], (before["end"] + after["start"]) / 2)))
    cuts.append(max(length, merged[-1]["end"] + pad))
    return [{"who": part["who"], "start": round(cuts[index], 3), "end": round(cuts[index + 1], 3)}
            for index, part in enumerate(merged)]
