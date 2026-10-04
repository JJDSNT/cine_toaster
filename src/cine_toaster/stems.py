"""Stems: the cut's sound in its parts, for a final mix in a DAW (CT-0063).

Cine Toaster lays the sound; a sound editor finishes it in a DAW such as
Ardour, and Cine Toaster does not become one (`docs/production-agents.md`).
So the assembly can hand over its parts, each the whole length of the cut and
starting at zero, by the conventions of a film mix:

- **dialogue**: the takes' sound while someone speaks, and the voice-overs;
- **room**: the takes' own sound when no one speaks (production effects);
- **effects**: the catalog's effects and Foley placed on shots;
- **ambience**: the catalog's beds;
- **music**: the catalog's music.

Each is a stereo 48 kHz 24-bit WAV, with the same gains, fades and ducking as
the version's mix: laid together at unity they make it, without the final
limiter. Beside them, `stems.json` says what each holds.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

STEMS = ("dialogue", "room", "effects", "ambience", "music")
STEM_OF_CUE = {"ambience": "ambience", "music": "music", "shot": "effects"}
IMPORT_HINT = ("Ardour: Session > Import, select the WAVs, 'Add files: as new tracks', 'Insert at: session start', "
               "'Mapping: one track per file'. Video: Session > Open Video, the version's .mp4.")


def _ffmpeg() -> str:
    return shutil.which("ffmpeg") or "ffmpeg"


def write(takes: list[tuple[Path, float, bool]], cues: list[tuple[Path, dict[str, Any], float]],
          speech: list[tuple[float, float]], seconds: float, folder: Path, run_process) -> dict[str, Any]:
    """Write one WAV per stem that holds anything, and `stems.json`; return the manifest.

    `takes`: (levelled clip, where it starts, whether someone speaks in it), voice-overs included;
    `cues`: (prepared catalog sound, its placement, its gain in dB) -- the pieces the mix used.
    """

    from .sounds import duck_expression

    parts: dict[str, list[tuple[Path, str]]] = {name: [] for name in STEMS}
    for clip, at, speaks in takes:
        parts["dialogue" if speaks else "room"].append((clip, f"adelay={int(round(at * 1000))}:all=1"))
    for prepared, cue, gain in cues:
        chain = f"volume={gain}dB,adelay={int(round(cue['start'] * 1000))}:all=1"
        if cue.get("duck", 0) > 0 and speech:
            chain += f",volume='{duck_expression(speech, cue['duck'])}':eval=frame"
        parts[STEM_OF_CUE.get(cue.get("kind", "shot"), "effects")].append((prepared, chain))
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    for name in STEMS:
        if not parts[name]:
            continue
        inputs = [item for path, _ in parts[name] for item in ("-i", str(path))]
        chains = ";".join(f"[{index}:a]{chain}[p{index}]" for index, (_, chain) in enumerate(parts[name]))
        labels = "".join(f"[p{index}]" for index in range(len(parts[name])))
        output = folder / f"{name}.wav"
        run_process([_ffmpeg(), "-y", "-loglevel", "error", *inputs, "-filter_complex",
                     f"{chains};{labels}amix=inputs={len(parts[name])}:normalize=0:duration=longest,"
                     f"apad=whole_dur={seconds:.3f},atrim=0:{seconds:.3f}[a]",
                     "-map", "[a]", "-ar", "48000", "-ac", "2", "-c:a", "pcm_s24le", str(output)],
                    expected_seconds=seconds, message=f"Stem: {name}")
        written.append({"stem": name, "file": output.name, "pieces": len(parts[name])})
    manifest = {"seconds": round(seconds, 3), "sample_rate": 48000, "bit_depth": 24, "channels": 2,
                "starts_at": 0.0, "stems": written,
                "summed": "at unity, the stems make the version's stereo mix before its final limiter",
                "import": IMPORT_HINT}
    (folder / "stems.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
