"""A 5.1 mix beside the stereo one, in the same version (CT-0052, phase 1).

The research (CT-0052) chose the "master once, deliver several" model: the
player picks the track its output can carry. Phase 1 adds, when the
production or a scene asks for it (`surround: "5.1"`), a second audio track
to every version: **5.1 (side) as AC-3 at 640 kb/s**, which every 5.1
receiver decodes over HDMI/ARC or S/PDIF. The stereo AAC track stays
first and default, so a browser or a phone plays as before.

The 5.1 is mixed from the same pieces as the stereo, routed by what they
are, by the conventions of a film mix:

- a take's sound while someone speaks in it: the **centre** (dialogue);
- a take's sound otherwise: front left and right;
- ambience: front and surrounds, a bed around the room;
- music: front, a little in the surrounds;
- effects and Foley: front, their low end also to the **LFE**, which
  carries only what is under 120 Hz.

Placing a sound where its subject stands in the plan is phase 2.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

LAYOUT = "5.1(side)"
LFE_CUTOFF = 120
#: How a stereo piece is spread over the six channels, by what it is.
ROUTES = {
    "dialogue": "FC=0.5*c0+0.5*c1",
    "room": "FL=c0|FR=c1",
    "ambience": "FL=0.71*c0|FR=0.71*c1|SL=0.71*c0|SR=0.71*c1",
    "music": "FL=c0|FR=c1|SL=0.35*c0|SR=0.35*c1",
    "effect": "FL=c0|FR=c1|LFE=0.5*c0+0.5*c1",
}
ROUTE_OF_CUE = {"ambience": "ambience", "music": "music", "shot": "effect"}


def _ffmpeg() -> str:
    return shutil.which("ffmpeg") or "ffmpeg"


def mix(takes: list[tuple[Path, float, bool]], cues: list[tuple[Path, dict[str, Any], float]],
        speech: list[tuple[float, float]], seconds: float, output: Path, run_process) -> Path:
    """The 5.1 mix as a six-channel WAV.

    `takes` are the takes' levelled clips: (file, where it starts, whether someone speaks in it);
    `cues` the catalog's prepared sounds: (file, its placement, its gain in dB).
    """

    from .sounds import duck_expression

    inputs, chains = [], []
    for index, (clip, at, speaks) in enumerate(takes):
        inputs += ["-i", str(clip)]
        chains.append(f"[{index}:a]pan={LAYOUT}|{ROUTES['dialogue' if speaks else 'room']},"
                      f"adelay={int(round(at * 1000))}:all=1[t{index}]")
    offset = len(takes)
    for index, (prepared, cue, gain) in enumerate(cues):
        inputs += ["-i", str(prepared)]
        chain = f"[{offset + index}:a]volume={gain}dB"
        if cue.get("duck", 0) > 0 and speech:
            # Ducked before the delay would shift the expression's time: delay first, as the stereo mix does.
            chain += f",adelay={int(round(cue['start'] * 1000))}:all=1"
            chain += f",volume='{duck_expression(speech, cue['duck'])}':eval=frame"
        else:
            chain += f",adelay={int(round(cue['start'] * 1000))}:all=1"
        route = ROUTES[ROUTE_OF_CUE.get(cue.get("kind", "shot"), "effect")]
        chains.append(f"{chain},pan={LAYOUT}|{route}[c{index}]")
    labels = "".join(f"[t{index}]" for index in range(len(takes))) + "".join(f"[c{index}]" for index in range(len(cues)))
    count = len(takes) + len(cues)
    graph = ";".join(chains) + (
        f";{labels}amix=inputs={count}:normalize=0:duration=longest,apad=whole_dur={seconds:.3f},"
        f"atrim=0:{seconds:.3f},channelsplit=channel_layout={LAYOUT}[FL][FR][FC][LFE][SL][SR];"
        f"[LFE]lowpass=f={LFE_CUTOFF}[LFEf];"
        f"[FL][FR][FC][LFEf][SL][SR]join=inputs=6:channel_layout={LAYOUT}:"
        "map=0.0-FL|1.0-FR|2.0-FC|3.0-LFE|4.0-SL|5.0-SR,alimiter=limit=0.95:level=disabled[a]")
    output.parent.mkdir(parents=True, exist_ok=True)
    run_process([_ffmpeg(), "-y", "-loglevel", "error", *inputs, "-filter_complex", graph, "-map", "[a]",
                 "-ar", "48000", str(output)], expected_seconds=seconds, message="Mixing the 5.1")
    return output


def attach(video: Path, surround: Path, output: Path, run_process) -> Path:
    """The version with its 5.1 as a second audio track: stereo AAC first and default, then AC-3 5.1."""

    run_process([_ffmpeg(), "-y", "-loglevel", "error", "-i", str(video), "-i", str(surround),
                 "-map", "0:v:0", "-map", "0:a:0", "-map", "1:a:0", "-c:v", "copy", "-c:a:0", "copy",
                 "-c:a:1", "ac3", "-b:a:1", "640k", "-disposition:a:0", "default", "-disposition:a:1", "0",
                 # MP4 shows a track's name as its handler; other containers as its title.
                 "-metadata:s:a:0", "title=Stereo", "-metadata:s:a:1", "title=5.1",
                 "-metadata:s:a:0", "handler_name=Stereo", "-metadata:s:a:1", "handler_name=5.1",
                 "-metadata:s:a:0", "language=und", "-metadata:s:a:1", "language=und",
                 "-movflags", "+faststart", str(output)], message="Adding the 5.1 track")
    return output


def loudness(path: Path, stream: int = 0) -> float | None:
    """Integrated loudness of one audio track (EBU R128; for 5.1 the LFE is not counted)."""

    completed = subprocess.run([_ffmpeg(), "-hide_banner", "-i", str(path), "-map", f"0:a:{stream}",
                                "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True, timeout=300)
    measured = re.findall(r"I:\s+(-?[\d.]+) LUFS", completed.stderr)
    return float(measured[-1]) if measured else None
