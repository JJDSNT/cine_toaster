"""Generation blocks: several shots made in one generation, sliced back into takes (CT-0037).

A video model can render a run of consecutive shots in one generation, cutting
between them itself. That keeps light, voices and continuity across the cuts,
but the model cuts at its own rhythm: in SINGULAR 1-02A, cuts asked for at
frames 144 and 264 came out at 91, 190 and 283. Slicing the clip at the
requested times puts every cut in the wrong place.

So the cuts are *found*: the clip's real cuts are detected, and each stretch
between them is given to the shot whose reference picture it most resembles,
in shot order (a shot may return, as in shot/reverse-shot, so identity alone
cannot decide). When that reading does not add up, the requested cuts are used
and the take says so. Each slice becomes a take of its shot, with where it came
from recorded beside it.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .takes import MEDIA_SUFFIXES, read_provenance, shot_key

SIGNATURE = (32, 18)
SCENE_THRESHOLD = 0.25
#: Frames after a cut before the picture is compared: the change has settled.
SETTLE_FRAMES = 4
#: A generation opens on its still first frame and eases into motion; a
#: "cut" found in that opening is the model starting, not a shot change
#: (SINGULAR 1-03 b5: a false cut at frame 7).
OPENING_SECONDS = 0.35


@dataclass(slots=True)
class Block:
    id: str
    shots: list[str]
    durations: list[float]
    clip: str = ""
    contiguous: bool = True
    #: Every generation of the block: `b<id>.mp4`, then `b<id>-<n>.mp4` in order.
    versions: list[str] = field(default_factory=list)
    #: What each version was made from, as recorded beside it (by path).
    records: dict[str, dict[str, Any]] = field(default_factory=dict)

    def public_dict(self) -> dict[str, Any]:
        return {"id": self.id, "shots": self.shots, "durations": self.durations, "clip": self.clip,
                "duration": round(sum(self.durations), 3), "contiguous": self.contiguous,
                "versions": self.versions, "records": self.records}


def block_versions(work: Path, block_id: str) -> list[Path]:
    """The block's clips: the production's own `b<id>`, then each generation `b<id>-<n>`."""

    if not work.is_dir():
        return []
    pattern = re.compile(rf"b{re.escape(block_id)}(?:-(\d+))?")
    found = []
    for path in work.iterdir():
        match = pattern.fullmatch(path.stem)
        if match and path.suffix.lower() in MEDIA_SUFFIXES[:3] and path.is_file():
            found.append((int(match[1] or 0), path))
    return [path for _, path in sorted(found)]


def scene_blocks(scene: dict[str, Any], work: Path | None, root: Path) -> list[Block]:
    """The scene's blocks in shot order, each with its clip when one exists."""

    order = [shot for shot in scene["shots"] if not shot.get("out_of_cut")]
    blocks: dict[str, Block] = {}
    positions: dict[str, list[int]] = {}
    for index, shot in enumerate(order):
        block_id = str(shot.get("block") or "").strip()
        if not block_id:
            continue
        block = blocks.setdefault(block_id, Block(block_id, [], []))
        block.shots.append(shot["id"])
        # A block's cuts are asked for by generation length, not edit length.
        block.durations.append(float(shot.get("generated_seconds") or shot.get("duration_seconds") or 0.0))
        positions.setdefault(block_id, []).append(index)
    for block_id, block in blocks.items():
        where = positions[block_id]
        block.contiguous = where == list(range(where[0], where[0] + len(where)))
        if work is not None:
            found = block_versions(work, block_id)
            block.versions = [path.relative_to(root).as_posix() for path in found]
            block.records = {path.relative_to(root).as_posix(): read_provenance(path) for path in found}
            # The production's own clip stays the block's clip; a generation
            # made here is one more version, never a replacement.
            block.clip = block.versions[0] if block.versions else ""
    return list(blocks.values())


def _picture_stems(value: str) -> list[str]:
    """`p<n>` for a shot or master named n: `p08`/`p8` for 8, `pmA` for mA."""

    stems = [f"p{value}"]
    key = shot_key(value)
    match = re.fullmatch(r"(\d+)([a-z]*)", key)
    if match:
        stems += [f"p{int(match[1]):02d}{match[2]}", f"p{int(match[1])}{match[2]}"]
    return list(dict.fromkeys(stems))


def _approved(root: Path, scene: dict[str, Any], shot: dict[str, Any]) -> Path | None:
    candidates = [shot]
    for item in shot.get("from") or []:
        ref = str(item.get("ref") or "") if isinstance(item, dict) else ""
        candidates += [other for other in scene.get("shots", []) if shot_key(other.get("number")) == shot_key(ref)]
    for candidate in candidates:
        path = candidate.get("approved_picture")
        if path and (root / path).is_file():
            return root / path
    return None


def _declared_start(work: Path, root: Path, scene: dict[str, Any], shot: dict[str, Any]) -> Path | None:
    for item in shot.get("from") or []:
        if not isinstance(item, dict):
            continue
        relation, ref = str(item.get("relation") or ""), str(item.get("ref") or "")
        if relation in ("last_frame_of", "usa_ultimo_de"):
            return last_frame(work, root, scene, ref)
        if relation in ("file", "usa_arquivo"):
            path = (root / scene["file"]).parent / ref
            if path.is_file():
                return path.resolve()
        if relation in ("picture_of", "usa", "usa_de"):
            for stem in _picture_stems(ref):
                for suffix in (".png", ".jpg", ".jpeg", ".webp"):
                    if (work / f"{stem}{suffix}").is_file():
                        return work / f"{stem}{suffix}"
    return None


def last_frame(work: Path, root: Path, scene: dict[str, Any], ref: str) -> Path | None:
    """The last frame of a shot's clip: kept beside it when the production made it (`p01-ultimo.png`),
    else drawn into the operational cache (disposable) from its clip."""

    import shutil
    import subprocess

    from .takes import shot_key

    source = next((item for item in scene["shots"] if shot_key(item.get("number")) == shot_key(ref)), None)
    if source is None:
        return None
    takes = [take for take in source.get("takes") or [] if take.get("media")]
    take = next((t for t in takes if t.get("selected")), None) or next((t for t in takes if t["id"] == "CUT"), None)
    clip = root / take["media"] if take else None
    for stem in _picture_stems(ref):
        kept = work / f"{stem}-ultimo.png"
        if kept.is_file() and (clip is None or kept.stat().st_mtime >= clip.stat().st_mtime):
            return kept
    if clip is None or not clip.is_file() or not shutil.which("ffmpeg"):
        return None
    from .jobs import state_root

    frame = state_root() / "last-frames" / f"{scene['id']}-{shot_key(ref)}-{int(clip.stat().st_mtime)}.png"
    if not frame.is_file():
        frame.parent.mkdir(parents=True, exist_ok=True)
        # Decode the whole tail: a single-frame seek lands frames before the end (SINGULAR, 18/09).
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-sseof", "-1", "-i", str(clip), "-an",
                        "-fps_mode", "passthrough", "-update", "1", str(frame)], check=False, timeout=120)
    return frame if frame.is_file() else None


def reference_picture(work: Path, root: Path, scene: dict[str, Any], shot: dict[str, Any]) -> Path | None:
    """The picture a shot's slice should look like.

    The shot's still if it has one, then its master image in the work
    directory (`p08.png`, beside its clip `c08.mp4`), then the image of the
    shot or master it is made from (its `from` lineage, e.g. `pmA.png`).
    """

    # A picture a person approved (SPEC-0009) is the shot's picture, and the
    # picture of every shot made from it.
    approved = _approved(root, scene, shot)
    if approved is not None:
        return approved
    if shot.get("still"):
        path = root / shot["still"]
        if path.is_file():
            return path
    # A first frame the breakdown declares wins over any picture of the shot's own (SINGULAR's `origem`:
    # the last frame of another shot, a file, another shot's picture).
    declared = _declared_start(work, root, scene, shot)
    if declared is not None:
        return declared
    names = [str(shot.get("number") or "")]
    for item in shot.get("from") or []:
        if isinstance(item, dict) and item.get("ref"):
            names.append(str(item["ref"]))
    for name in filter(None, names):
        for stem in _picture_stems(name):
            for suffix in (".png", ".jpg", ".jpeg", ".webp"):
                if (work / f"{stem}{suffix}").is_file():
                    return work / f"{stem}{suffix}"
    return None


# --- reading the clip --------------------------------------------------------


def _ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise RuntimeError("FFmpeg is needed to slice a block")
    return path


def clip_info(path: Path) -> tuple[float, float]:
    """(duration in seconds, frames per second)."""

    ffprobe = shutil.which("ffprobe") or "ffprobe"
    out = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=r_frame_rate:format=duration", "-of", "default=nw=1", str(path)],
                         capture_output=True, text=True, timeout=60).stdout
    rate = re.search(r"r_frame_rate=(\d+)/(\d+)", out)
    duration = re.search(r"duration=([\d.]+)", out)
    fps = int(rate[1]) / int(rate[2]) if rate and int(rate[2]) else 24.0
    return (float(duration[1]) if duration else 0.0), fps


def detected_cuts(path: Path, fps: float, threshold: float = SCENE_THRESHOLD) -> list[int]:
    """Frames where the clip's picture actually changes shot."""

    completed = subprocess.run(
        [_ffmpeg(), "-hide_banner", "-i", str(path), "-vf", f"select='gt(scene,{threshold})',showinfo",
         "-f", "null", "-"], capture_output=True, text=True, timeout=300)
    return [round(float(value) * fps) for value in re.findall(r"pts_time:([0-9.]+)", completed.stderr)]


def _raw_signature(command: list[str]) -> list[int]:
    completed = subprocess.run(command + ["-vf", f"scale={SIGNATURE[0]}:{SIGNATURE[1]},format=rgb24",
                                          "-frames:v", "1", "-f", "rawvideo", "-"],
                               capture_output=True, timeout=60)
    return list(completed.stdout)


def picture_signature(path: Path) -> list[int]:
    return _raw_signature([_ffmpeg(), "-v", "error", "-i", str(path)])


def frame_signature(clip: Path, frame: int, fps: float) -> list[int]:
    return _raw_signature([_ffmpeg(), "-v", "error", "-ss", f"{frame / fps:.4f}", "-i", str(clip)])


def distance(a: list[int], b: list[int]) -> float:
    if not a or not b or len(a) != len(b):
        return float("inf")
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


# --- deciding the cuts ---------------------------------------------------------


def requested_cuts(durations: list[float], fps: float) -> list[int]:
    """Where each shot was asked to start, in frames (multiples of 8, as LTX needs)."""

    starts, clock = [], 0.0
    for seconds in durations:
        starts.append(int(round(clock * fps / 8)) * 8)
        clock += seconds
    return starts


def assign(costs: list[list[float]], shots: int) -> list[int] | None:
    """Give each stretch a shot, in order, every shot at least one stretch.

    ``costs[i][j]`` is how unlike stretch *i* is to shot *j*'s picture. The
    assignment is monotonic -- stretches follow the shot order -- and the
    cheapest such assignment is returned, or None when none exists.
    """

    stretches = len(costs)
    if stretches < shots:
        return None
    infinity = float("inf")
    best = [[infinity] * shots for _ in range(stretches)]
    came = [[-1] * shots for _ in range(stretches)]
    best[0][0] = costs[0][0]
    for i in range(1, stretches):
        for j in range(shots):
            options = [(best[i - 1][j], j)] + ([(best[i - 1][j - 1], j - 1)] if j else [])
            value, origin = min(options)
            if value < infinity:
                best[i][j], came[i][j] = value + costs[i][j], origin
    if best[-1][-1] == infinity:
        return None
    owners, j = [0] * stretches, shots - 1
    for i in range(stretches - 1, 0, -1):
        owners[i], j = j, came[i][j]
    owners[0] = j
    return owners


@dataclass(slots=True)
class Slicing:
    starts: list[int]
    method: str
    detected: list[int] = field(default_factory=list)
    requested: list[int] = field(default_factory=list)
    note: str = ""


def decide(clip: Path, durations: list[float], references: list[Path | None], fps: float) -> Slicing:
    """Where each shot of the block starts in the clip, and how that was decided."""

    requested = requested_cuts(durations, fps)
    found = [frame for frame in detected_cuts(clip, fps) if frame > max(SETTLE_FRAMES, OPENING_SECONDS * fps)]
    shots = len(durations)
    if shots == 1:
        return Slicing([0], "single", found, requested)
    bounds = [0] + found
    if len(bounds) < shots:
        return Slicing(requested, "requested", found, requested,
                       f"{len(bounds)} stretch(es) found for {shots} shots; cut where they were asked for")
    if all(references):
        pictures = [picture_signature(path) for path in references]  # type: ignore[arg-type]
        costs = [[distance(frame_signature(clip, start + SETTLE_FRAMES, fps), picture) for picture in pictures]
                 for start in bounds]
        owners = assign(costs, shots)
        if owners is not None:
            starts = [start for index, (start, owner) in enumerate(zip(bounds, owners))
                      if index == 0 or owner != owners[index - 1]]
            return Slicing(starts, "content", found, requested)
        return Slicing(requested, "requested", found, requested, "no ordered match with the reference pictures")
    if len(bounds) == shots:
        return Slicing(bounds, "detected", found, requested,
                       "no reference pictures; the model's own cuts were used, one per shot")
    return Slicing(requested, "requested", found, requested,
                   f"{len(bounds)} stretches for {shots} shots and no reference pictures to tell them apart")
