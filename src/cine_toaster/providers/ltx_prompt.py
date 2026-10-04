"""How a block of shots is told to LTX 2.5 -- the model's own grammar.

This is provider-specific on purpose: the brief is neutral, this is what LTX
2.5 obeys. Each rule answers a measured claim in `knowledge/providers/ltx-2.5.md`,
and is reimplemented from SINGULAR's practice (`cena_ltx.py`), not copied.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

#: Speech verbs a delivery must not repeat: the model reads a second one aloud
#: (claim `reads-direction-aloud`).
SPEECH_VERBS = re.compile(r"^(says|asks|answers|replies|calls out|repeats|whispers)\b[,\s]*", re.IGNORECASE)


@dataclass(slots=True)
class Line:
    speaker: str      # how the model should refer to them: "The man beside the bed"
    text: str         # the words, in the language spoken in the take
    manner: str = ""  # delivery: "quietly, almost warmly"
    voice: str = ""   # identity and state: "a low controlled male voice; here, hoarse"


@dataclass(slots=True)
class ShotPrompt:
    picture: str
    camera: str
    action: str = ""
    lines: list[Line] = field(default_factory=list)
    sound: str = ""
    #: How the people in it feel, as behaviour to act (the emotion catalog, CT-0048).
    acting: list[str] = field(default_factory=list)
    #: What holds still in a single shot (`holds`): the setting, all but the light, or the setting with
    #: people free to enter or leave (SINGULAR's `so_a_luz` and `entra_sai`).
    holds: str = "setting"


#: A single shot's sentence on what stays as in the first frame, by `holds` (SINGULAR's rules of 17/09).
HOLDS = {
    "setting": "The setting stays exactly as in the first frame and nobody else enters the frame.",
    "light": "The camera, the framing and every object stay exactly as in the first frame, only the light "
             "changes, and nobody else enters the frame.",
    "open": "The setting stays exactly as in the first frame.",
}


def _sentence(text: str) -> str:
    text = " ".join(text.split()).rstrip(".")
    return (text[0].upper() + text[1:] + ".") if text else ""


def _lower_first(text: str) -> str:
    text = " ".join(text.split()).rstrip(".")
    return text[0].lower() + text[1:] if text else text


def _speech(lines: list[Line], already_spoken: bool) -> list[str]:
    """Each line names its speaker; later ones start with "Then" so the order holds
    (claims `several-speakers-in-one-clip`, `action-order`)."""

    parts = []
    for index, line in enumerate(lines):
        manner = SPEECH_VERBS.sub("", line.manner.strip())
        speaker = line.speaker if index == 0 and not already_spoken else "Then " + _lower_first(line.speaker)
        how = ", ".join(part for part in (manner, f"in {line.voice}" if line.voice else "") if part)
        text = " ".join(line.text.split())
        if text and text[-1] not in ".!?…\"'":
            text += "."
        parts.append(f'{speaker} says{" " + how if how else ""}: "{text}"')
    return parts


def block_prompt_sections(shots: list[ShotPrompt], style: str = "") -> list[str]:
    """The prompt in pieces: one per shot, then what holds across the block.

    Joined, they are the prompt the model receives (`block_prompt`); apart,
    a person can read which words belong to which shot.
    """

    sections: list[str] = []
    spoken = False
    for index, shot in enumerate(shots):
        parts: list[str] = []
        camera = shot.camera.rstrip(".")
        if index == 0:
            parts += [_sentence(shot.picture), _sentence(f"Camera: {camera}") if camera else ""]
            if len(shots) == 1:
                # A single shot says what holds right after the camera, before the action (SINGULAR's order).
                parts.append(HOLDS.get(shot.holds, HOLDS["setting"]))
        else:
            opening = "A hard cut transitions to a new shot" + (f", {camera}" if camera else "")
            parts.append(f"{opening}: {_lower_first(shot.picture)}." if shot.picture else f"{opening}.")
        if shot.action:
            parts.append(_sentence(shot.action))
        parts += [_sentence(text) for text in shot.acting]
        parts += _speech(shot.lines, spoken)
        spoken = spoken or bool(shot.lines)
        sections.append(" ".join(" ".join(part for part in parts if part).split()))
    constant = "The setting, the light and the voices stay the same across the cuts, and nobody else enters the frame."
    if len(shots) == 1:
        constant = ""  # said after the camera
    # One sound for the block: it is one continuous room.
    sound = next((shot.sound for shot in shots if shot.sound), "quiet room")
    closing = [(constant + ("" if spoken else " Nobody speaks.")).strip(),
               *([f"Style: {style.rstrip('.')}."] if style else []),
               f"Sound: {sound}{', continuing across the cuts' if len(shots) > 1 else ''}. No music."]
    sections.append(" ".join(" ".join(closing).split()))
    return sections


def block_prompt(shots: list[ShotPrompt], style: str = "") -> str:
    """One generation holding several shots, cut by the model itself.

    The first shot describes only what its starting picture shows (claim
    `prompt-must-match-first-frame`); each later one is introduced as a hard
    cut to a new shot. Setting, light and voices are held across the cuts.
    """

    return " ".join(section for section in block_prompt_sections(shots, style) if section)
