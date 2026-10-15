"""CT-0079's measurement: does each shot's sound land on its picture in a cut, and does the gap grow?

    PYTHONPATH=src python scripts/research/time_drift.py <folder> <shots> <rate> [<take seconds> [<every>]]

A film of `shots` shots whose takes flash white at their frame 20 -- and every `every` frames after, for long
takes -- with a click at the same instant (exact in the take), cut by the assembly. Measured twice, in samples at 48 kHz:
- the engine: the frames' numbers in the joined picture against the clicks in the PCM mix (`work/sound.wav`),
  before any lossy codec;
- the delivery: the cut's own frames' times against its AAC sound, which adds the codec's priming and blocks.
A take's first 0.35 s is dropped by the assembly (a generated take's still opening), off the frame grid at
most rates: the case that put the sound half a frame early before the fix.
"""

from __future__ import annotations

import json
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np

from cine_toaster.assembly import plan_scene, render
from cine_toaster.project import load_production

SAMPLE_RATE = 48000
FLASH_FRAME = 20


def make_film(root: Path, shots: int, rate: str, take_seconds: float = 2.0, every: int = 0) -> None:
    exact = Fraction(rate)
    root.mkdir(parents=True, exist_ok=True)
    (root / "project.yaml").write_text("id: t\ntitle: T\npaths:\n  scenes: scenes\n")
    work = root / "scenes" / "010" / "work"
    work.mkdir(parents=True, exist_ok=True)
    (root / "scenes" / "010" / "scene.yaml").write_text("scene: S1\nshots:\n" + "".join(
        f"  - n: {i}\n    duration: {take_seconds:g}\n    label: Shot {i}.\n" for i in range(1, shots + 1)))
    # The clicks by whole sample index (`n`), not by time in floating point: the instrument must be more exact
    # than what it measures. Frame 20, and every `every` frames after, fall on whole samples at every rate
    # measured here (32,032 + 480,480 k at 30000/1001); a rate where they do not is refused.
    first, period = Fraction(FLASH_FRAME * SAMPLE_RATE) / exact, Fraction(every * SAMPLE_RATE) / exact
    if first.denominator != 1 or period.denominator != 1:
        raise SystemExit(f"At {rate} the flashes do not fall on whole samples: choose another `every`")
    burst = SAMPLE_RATE // 500  # 2 ms
    lit = f"gte(N,{FLASH_FRAME})*eq(mod(N-{FLASH_FRAME},{every}),0)" if every else f"eq(N,{FLASH_FRAME})"
    heard = (f"gte(n,{first})*lt(mod(n-{first},{period}),{burst})" if every
             else f"gte(n,{first})*lt(n,{first + burst})")
    for i in range(1, shots + 1):
        take = work / f"c{i:02d}.mp4"
        if take.exists():
            continue
        partial = take.with_suffix(".mov")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                        f"color=c=black:s=160x90:r={rate}:d={take_seconds},"
                        f"geq=lum='if({lit},255,16)':cb=128:cr=128",
                        "-f", "lavfi", "-i",
                        f"aevalsrc='if({heard},0.9,0)':s={SAMPLE_RATE}:d={take_seconds}",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le", "-shortest", str(partial)],
                       check=True)
        partial.rename(take)


def _flashes(video: Path) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(video), "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         capture_output=True, check=True).stdout
    probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                       "stream=width,height", "-of", "json", str(video)],
                                      capture_output=True, text=True).stdout)["streams"][0]
    lum = np.frombuffer(raw, np.uint8).reshape(-1, probe["width"] * probe["height"]).mean(axis=1)
    return np.nonzero(lum > 128)[0]


def _clicks(sound: Path) -> np.ndarray:
    pcm = np.frombuffer(subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(sound), "-ac", "1", "-ar",
                                        str(SAMPLE_RATE), "-f", "f32le", "-"], capture_output=True, check=True).stdout,
                        np.float32)
    loud = np.nonzero(np.abs(pcm) > 0.3)[0]
    return loud[np.insert(np.diff(loud) > SAMPLE_RATE // 10, 0, True)]


def _summary(gap: np.ndarray, at: np.ndarray) -> dict:
    slope, offset = np.polyfit(at, gap, 1) if len(gap) > 1 else (0.0, float(gap[0]))
    return {"count": int(len(gap)), "mean": float(gap.mean()), "min": float(gap.min()), "max": float(gap.max()),
            "scatter": float(np.std(gap - (slope * at + offset))), "per_hour": float(slope * 3600)}


def measure(root: Path, rate: str) -> dict:
    """Cut the film and measure it: {rate written, engine and delivery gaps in samples (click minus flash)}."""

    exact = Fraction(rate)
    plan = plan_scene(root, load_production(root)["scenes"][0])
    out, work = root / "cut.mp4", root / "work"
    render(root, plan, out, work, lambda command, **_: subprocess.run(command, check=True, capture_output=True))
    stream = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                        "stream=r_frame_rate", "-of", "json", str(out)],
                                       capture_output=True, text=True).stdout)["streams"][0]
    result = {"rate_written": stream["r_frame_rate"]}
    for name, video, sound in (("engine", work / "picture.mp4", work / "sound.wav"), ("delivery", out, out)):
        frames, clicks = _flashes(video), _clicks(sound)
        count = min(len(frames), len(clicks))
        at = np.array([float(Fraction(int(f)) / exact) for f in frames[:count]])
        gap = clicks[:count] - np.array([float(Fraction(int(f)) * SAMPLE_RATE / exact) for f in frames[:count]])
        result[name] = {**_summary(gap, at), "flashes": int(len(frames)), "clicks": int(len(clicks))}
    return result


if __name__ == "__main__":
    folder, shots, rate = Path(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
    make_film(folder, shots, rate, float(sys.argv[4]) if len(sys.argv) > 4 else 2.0,
              int(sys.argv[5]) if len(sys.argv) > 5 else 0)
    print(json.dumps(measure(folder, rate), indent=1))
