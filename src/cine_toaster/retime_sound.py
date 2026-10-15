"""The sound of a retimed shot (C7 step 3, CT-0080): a contract, then a policy.

**The contract.** A shot drawn by a graph shows, at each of its output frames,
one instant of its take's media (`compositing/clock.py`, from the output to the
take's source, plus the take's origin). That list -- one instant per frame, at
the frame's centre -- is the shot's `TimeMap`. From it:
- the shot's duration in the cut: its frames over the cut's rate;
- what of the take it uses: from the first instant shown to the last;
- its kind: **unchanged** (each frame shows its own instant), **shifted** (each
  frame shows its own instant moved by one constant amount, at speed 1 -- an
  offset), or **speed** (the instants advance at another speed, or turn back).
  A speed map is cut into pieces of near-constant speed (`pieces`), each with
  the exact media range its frames span, so sound placed piece by piece is in
  sync at every piece's boundary.

**The policies** (a shot's `retime_sound`), for a shot whose map is not
unchanged; an unchanged shot keeps its take's sound as it always has:
- `mute` (the default): the take's sound is not heard -- nothing drifts unseen;
- `preserve`: the take's sound at speed 1 from the cut point, for the shot's
  duration -- padded with silence where the take ends first; in sync only where
  the picture runs at speed 1;
- `stretch`: the sound follows the map, its pitch kept: a shift is the take's
  sound moved by the shift, no processing; a speed is stretched by a stretcher
  the shot may name (`stretch_with`) -- by default the anchored WSOLA here,
  every grain read where the map puts it and every attack laid whole on its
  instant (sample-exact in CT-0080's measurements), provisionally: the choice
  waits for the user's blind listening. FFmpeg's `rubberband` and `atempo`
  (pieces joined in phase) are there by name, never as a silent fallback. A
  map that runs backwards or holds still (a reverse, a freeze) cannot be
  stretched: refused, explicitly, and the shot muted;
- `resample` (speed and pitch together) is not built yet: refused by name.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np

from . import timebase
from .errors import ValidationError

POLICIES = ("mute", "preserve", "stretch")
LATER = ("resample",)
#: Consecutive frames whose speeds differ by less than this share a piece (an eased ramp is not cut per frame).
SPEED_GROUPING = 0.02
#: How far past its frames each piece is drawn, and so how long two pieces cross-fade, in seconds.
CROSSFADE = 0.010
#: How far a piece may move to meet the one before it in phase, in seconds -- half the period of 100 Hz, the
#: lowest voice: the most a sound is ever early or late, and only in a piece after a change of speed.
ALIGNMENT = 0.005
#: Instants closer than this (seconds) are the same: floats from approximate maps.
SAME = 1e-7


@dataclass(frozen=True)
class Piece:
    """Output frames [first, end) showing media from `start` to `stop` (seconds) at a near-constant speed."""

    first: int
    end: int
    start: Any
    stop: Any

    def speed(self, fps: Fraction) -> float:
        return float((self.stop - self.start) * fps / (self.end - self.first))


@dataclass(frozen=True)
class TimeMap:
    """The media instant a shot shows at each output frame's centre -- and, where it is given, at any instant
    (`at`, output seconds -> media seconds): the sound lives between frames, so a piece's edges are taken where
    the map really is; the frames are the points it is checked at."""

    fps: Fraction
    origin: Any  # the media instant of the shot's local zero (its cut point)
    instants: tuple[Any, ...]
    at: Any = None  # Callable[[Fraction], media seconds] | None

    @property
    def frames(self) -> int:
        return len(self.instants)

    @property
    def duration(self) -> Fraction:
        return Fraction(self.frames) / self.fps

    def _own(self, frame: int) -> Any:
        return self.origin + Fraction(2 * frame + 1, 2) / self.fps

    def shifts(self) -> list[float]:
        return [float(at - self._own(frame)) for frame, at in enumerate(self.instants)]

    @property
    def kind(self) -> str:
        shifts = self.shifts()
        if all(abs(shift) < SAME for shift in shifts):
            return "unchanged"
        if all(abs(shift - shifts[0]) < SAME for shift in shifts):
            return "shifted"
        return "speed"

    @property
    def shift(self) -> Any:
        """A shifted map's constant: how much later in the media every frame is shown (negative: earlier)."""

        return self.instants[0] - self._own(0)

    def edge(self, frame: int, side: int) -> Any:
        """The media instant at an output frame's start (side -1) or end (+1): half a frame from its centre, at
        the speed of the frame's neighbourhood."""

        if self.frames == 1:
            return self.instants[0] + Fraction(side, 2) / self.fps
        other = frame + 1 if frame + 1 < self.frames else frame - 1
        step = (self.instants[other] - self.instants[frame]) / (other - frame)
        return self.instants[frame] + step * Fraction(side, 2)

    def pieces(self) -> list[Piece]:
        """The map cut into runs of near-constant speed, each with the media range its frames span exactly."""

        if self.frames == 1:
            return [Piece(0, 1, self.edge(0, -1), self.edge(0, 1))]
        if self.at is not None:  # each frame's own speed, from the map at its two edges
            speeds = [float((self.boundary(f + 1) - self.boundary(f)) * self.fps) for f in range(self.frames)]
        else:  # between frame centres
            speeds = [float((self.instants[f + 1] - self.instants[f]) * self.fps) for f in range(self.frames - 1)]
        cuts, first = [0], speeds[0]
        for index, speed in enumerate(speeds[1:], 1):
            if abs(speed - first) > SPEED_GROUPING * max(1.0, abs(first)) or (speed > 0) != (first > 0):
                cuts.append(index)
                first = speed
        cuts.append(self.frames)
        pieces = []
        for a, b in zip(cuts, cuts[1:]):
            # Boundaries shared between pieces, at the frame boundary between them: the map itself there when it
            # is given (exact for exact maps), else halfway between the two frames' instants.
            pieces.append(Piece(a, b, self.boundary(a), self.boundary(b)))
        return pieces

    def boundary(self, frame: int) -> Any:
        """The media instant at the start of output frame `frame` (`frames` for the end of the last)."""

        if self.at is not None:
            return self.at(Fraction(frame) / self.fps)
        if frame == 0:
            return self.edge(0, -1)
        if frame == self.frames:
            return self.edge(self.frames - 1, 1)
        return (self.instants[frame - 1] + self.instants[frame]) / 2


def policy_problem(policy: Any) -> str | None:
    if policy in (None, "", *POLICIES):
        return None
    if policy in LATER:
        return f"retime_sound {policy!r} is not built yet ({', '.join(POLICIES)} are)"
    return f"retime_sound is one of {', '.join(POLICIES)}, not {policy!r}"


#: The stretchers (CT-0080, measured in `scripts/research/stretch_bench.py`): `anchored` -- WSOLA on the shot's
#: own map, attacks laid whole on their instants: length exact, tones level, clicks to the sample -- here, always;
#: FFmpeg's `rubberband` filter, pieces joined in phase: length exact, but dips steady tones and drifts with
#: the content; FFmpeg's `atempo`: its timing drifts and it drops transients above 2x. The default is
#: provisional until the user's blind listening decides.
STRETCHERS = ("anchored", "rubberband", "atempo")
DEFAULT_STRETCHER = "anchored"


def available() -> list[str]:
    """The stretchers here: the anchored one always (NumPy), FFmpeg's when this FFmpeg has them."""

    found = ["anchored"]
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        listed = subprocess.run([ffmpeg, "-hide_banner", "-filters"], capture_output=True, text=True).stdout
        found += [name for name in ("rubberband", "atempo") if f" {name} " in listed]
    return found


def stretcher(asked: str | None = None) -> str:
    """The stretcher a shot uses: the one it asks for, else the default. Never another in silence: what is asked
    and missing is refused, so the same production does not sound different on another machine."""

    wanted = asked or DEFAULT_STRETCHER
    if wanted not in STRETCHERS:
        raise ValidationError(f"stretch_with is one of {', '.join(STRETCHERS)}, not {wanted!r}")
    if wanted not in available():
        raise ValidationError(f"retime_sound stretch needs FFmpeg's {wanted} filter, which this FFmpeg lacks "
                              "(toast doctor says what to install)")
    return wanted


_CALIBRATION: dict[tuple[str, float], tuple[float, int]] = {}


def calibration(tempo: float, using: str, sample_rate: int) -> tuple[float, int]:
    """What to ask the stretcher for `tempo`, and how many samples late it puts what it is given: measured once
    per tempo with two pilot clicks a second and a half apart (CT-0080). `rubberband` lands transients at a
    constant delay but runs a few tenths of a percent off the tempo asked; corrected, a piece's end lands where
    its frames end. `atempo` is taken as it is."""

    key = (using, round(tempo, 9))
    if key in _CALIBRATION:
        return _CALIBRATION[key]
    if using != "rubberband":
        _CALIBRATION[key] = (tempo, 0)
        return _CALIBRATION[key]

    def clicks(asked: float) -> list[int]:
        pilot = np.zeros((2 * sample_rate, 2), np.float32)
        for at in (sample_rate // 4, sample_rate // 4 + 3 * sample_rate // 2):
            pilot[at:at + 48] = 0.8
        raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "f32le", "-ar", str(sample_rate), "-ac", "2",
                              "-i", "-", "-af", _tempo_filter(asked, using), "-f", "f32le", "-ar", str(sample_rate),
                              "-ac", "2", "-"], input=pilot.tobytes(), capture_output=True, check=True).stdout
        heard = np.abs(np.frombuffer(raw, np.float32).reshape(-1, 2).sum(axis=1))
        loud = np.nonzero(heard > 0.3)[0]
        return [int(v) for v in loud[np.insert(np.diff(loud) > sample_rate // 10, 0, True)]] if len(loud) else []

    asked = tempo
    for _ in range(3):  # the rate converges in two
        found = clicks(asked)
        if len(found) < 2:
            break
        spacing = (3 * sample_rate / 2) / tempo
        asked *= (found[1] - found[0]) / spacing
    found = clicks(asked)
    delay = int(found[0] - round((sample_rate // 4) / tempo)) if found else 0
    _CALIBRATION[key] = (asked, delay)
    return _CALIBRATION[key]


def _tempo_filter(tempo: float, using: str) -> str:
    if using == "rubberband":
        return f"rubberband=tempo={tempo:.9f}:transients=crisp:detector=compound:phase=laminar:pitchq=quality"
    # atempo takes 0.5 to 100 per filter: a slower tempo is a chain of halves.
    chain, left = [], tempo
    while left < 0.5:
        chain.append("atempo=0.5")
        left /= 0.5
    return ",".join(chain + [f"atempo={left:.9f}"])


def _read(path: Path, start: float, seconds: float, sample_rate: int) -> np.ndarray:
    """`seconds` of a file's sound from `start` (seconds, may be negative: silence before it), stereo floats."""

    lead = max(0, int(round(-start * sample_rate))) if start < 0 else 0
    begin = max(0.0, start)
    length = max(0.0, seconds - lead / sample_rate)
    raw = b""
    if length > 0:
        raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", timebase.seek(begin), "-t", f"{length + 0.05:.6f}",
                              "-i", str(path), "-map", "0:a:0", "-ac", "2", "-ar", str(sample_rate), "-f", "f32le", "-"],
                             capture_output=True, check=True).stdout
    data = np.frombuffer(raw, np.float32).reshape(-1, 2)
    wanted = int(round(seconds * sample_rate))
    out = np.zeros((wanted, 2), np.float32)
    body = data[: max(0, wanted - lead)]
    out[lead:lead + len(body)] = body
    return out


#: Media drawn before and after a piece, so the stretcher's start (a fade-in) and its end fall outside it.
PREROLL = 0.1


def _stretched(path: Path, start: float, stop: float, samples: int, using: str, sample_rate: int,
               work: Path) -> np.ndarray:
    """Media [start, stop) stretched to exactly `samples` samples, pitch kept: drawn with `PREROLL` of media
    either side, then cut where the media's `start` lands -- after the stretcher's calibrated delay."""

    seconds = stop - start
    tempo = seconds / (samples / sample_rate)
    if abs(tempo - 1.0) < 1e-9:
        return _read(path, start, seconds, sample_rate)[:samples]
    source = _read(path, start - PREROLL, seconds + 2 * PREROLL, sample_rate)
    given, made = work / "in.f32", work / "out.f32"
    given.write_bytes(source.astype("<f4").tobytes())
    asked, late = calibration(tempo, using, sample_rate)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "f32le", "-ar", str(sample_rate), "-ac", "2",
                    "-i", str(given), "-af", _tempo_filter(asked, using), "-f", "f32le", "-ar", str(sample_rate),
                    "-ac", "2", str(made)], check=True)
    out = np.frombuffer(made.read_bytes(), np.float32).reshape(-1, 2)
    first = int(round(PREROLL * sample_rate / tempo)) + late
    fitted = np.zeros((samples, 2), np.float32)
    body = out[first:first + samples]
    fitted[: len(body)] = body
    return fitted


def build(policy: str, timemap: TimeMap, heard: Path, destination: Path,
          sample_rate: int = timebase.SAMPLE_RATE, stretch_with: str | None = None) -> list[str]:
    """The shot's sound under `policy`, written to `destination` (a WAV of exactly the shot's samples).
    Returns the notes to give the plan; raises ValidationError when the policy cannot play this map."""

    problem = policy_problem(policy)
    if problem:
        raise ValidationError(problem)
    total = timebase.samples_of_frames(timemap.frames, timemap.fps, sample_rate)
    notes: list[str] = []
    if policy == "preserve":
        out = _read(heard, float(timemap.origin), total / sample_rate, sample_rate)
        notes.append("its take's sound at its own speed from the cut point (`preserve`): its speed is kept, not "
                     "its sync with the picture -- in sync only where the picture runs at speed 1")
    elif policy == "stretch":
        if timemap.kind == "shifted":
            begin = float(timemap.origin + timemap.shift)
            out = _read(heard, begin, total / sample_rate, sample_rate)
            notes.append(f"its take's sound moved by {float(timemap.shift):+.3f} s with the picture (`stretch` of a "
                         "shift: no processing)")
        else:
            pieces = timemap.pieces()
            backwards = [piece for piece in pieces if piece.speed(timemap.fps) <= 1e-6]
            if any(float(b) <= float(a) for a, b in zip(timemap.instants, timemap.instants[1:])):
                backwards = backwards or pieces
            if backwards:
                raise ValidationError("retime_sound stretch cannot play a reverse or a freeze (its map runs back or "
                                      "holds still); the shot is muted")
            using = stretcher(stretch_with)
            out = (anchored(heard, timemap, total, sample_rate) if using == "anchored"
                   else _joined(pieces, timemap, heard, total, sample_rate, using))
            speeds = sorted({round(piece.speed(timemap.fps), 2) for piece in pieces})
            notes.append(f"its take's sound stretched with the picture, pitch kept, in {len(pieces)} piece(s) at "
                         f"{', '.join(f'{speed:g}x' for speed in speeds)} (`stretch`, {using})"
                         + (" -- approximate: atempo's timing drifts and drops transients" if using == "atempo" else ""))
    else:  # mute
        out = np.zeros((total, 2), np.float32)
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "f32le", "-ar", str(sample_rate), "-ac", "2", "-i", "-",
                    "-c:a", "pcm_s16le", str(destination)], input=out.astype("<f4").tobytes(), check=True)
    return notes


def _aligned(tail: np.ndarray, head: np.ndarray, search: int) -> int:
    """The shift, within +/-`search` samples, that lines `head` up with `tail` best (normalised correlation of
    their mono sums over the overlap): where the two waveforms are in phase."""

    left, right = tail.sum(axis=1), head.sum(axis=1)
    span = len(left)
    best, chosen = -np.inf, 0
    for shift in range(-search, search + 1):
        piece = right[search + shift: search + shift + span]
        if len(piece) < span:
            continue
        norm = float(np.linalg.norm(left) * np.linalg.norm(piece))
        score = float(np.dot(left, piece)) / norm if norm > 1e-12 else 0.0
        if score > best:
            best, chosen = score, shift
    return chosen


def _joined(pieces: list[Piece], timemap: TimeMap, heard: Path, total: int, sample_rate: int,
            using: str) -> np.ndarray:
    """Each piece stretched exactly over its own frames, drawn past both ends; at each change of speed the
    incoming piece is moved by a few samples (at most `ALIGNMENT`) to where its waveform is in phase with the
    outgoing one, and the two are joined by an equal-gain crossfade centred on the boundary (WSOLA's splice).

    Measured (CT-0080): pieces joined at their exact instants come out of phase, and a crossfade there drops
    the level by half; one continuous stretch with changing tempo is smooth but lands 12-19 ms early and
    drifts. Aligned pieces are smooth, and in sync to within the alignment, which never accumulates: each
    piece is placed by its own exact start."""

    margin = int(round(CROSSFADE * sample_rate))
    search = int(round(ALIGNMENT * sample_rate))
    out = np.zeros((total, 2), np.float32)
    previous: np.ndarray | None = None  # the outgoing piece's overlap, as placed
    with tempfile.TemporaryDirectory(prefix="retime-sound-") as folder:
        for index, piece in enumerate(pieces):
            a = timebase.samples_of_frames(piece.first, timemap.fps, sample_rate)
            b = timebase.samples_of_frames(piece.end, timemap.fps, sample_rate)
            speed = float(piece.stop - piece.start) / ((b - a) / sample_rate)
            lead = margin + search if index > 0 else 0
            tail = margin if index < len(pieces) - 1 else 0
            start = float(piece.start) - lead / sample_rate * speed
            stop = float(piece.stop) + tail / sample_rate * speed
            drawn = _stretched(heard, start, stop, (b - a) + lead + tail, using, sample_rate, Path(folder))
            shift = 0
            if index > 0 and previous is not None:
                # The incoming overlap starts `margin` before the boundary; candidates move it by +/-search.
                shift = _aligned(previous, drawn[: 2 * margin + 2 * search], search)
            body = drawn[search + shift:] if index > 0 else drawn
            weights = np.ones(len(body), np.float32)
            if index > 0:
                weights[: 2 * margin] = np.linspace(0, 1, 2 * margin, dtype=np.float32)
            if tail:
                weights[-2 * tail:] = np.linspace(1, 0, 2 * tail, dtype=np.float32)
            begin = a - (margin if index > 0 else 0)
            placed = body * weights[:, None]
            lo, hi = max(0, begin), min(total, begin + len(placed))
            out[lo:hi] += placed[lo - begin:hi - begin]
            previous = drawn[-2 * tail:] if tail else None
    return out


# --- An anchored stretcher: WSOLA on the shot's own time map ---------------------------------------------------

#: Grains of 40 ms, laid every 10 ms (four overlap, Hann windows sum flat), each read where the map says that
#: output instant shows, moved by at most `ALIGNMENT` to continue the previous grain in phase.
GRAIN = 0.040
HOP = 0.010


def anchored(heard: Path, timemap: TimeMap, total: int, sample_rate: int, grain_seconds: float | None = None,
             hop_seconds: float | None = None) -> np.ndarray:
    """The shot's sound following its map, pitch kept, by WSOLA anchored on the map (CT-0080).

    Every grain of output is read from the media instant the map gives for its centre -- so no error ever
    accumulates, a ramp is continuous (there are no pieces to join), and a transient lands within `ALIGNMENT`
    of its instant -- and is moved by at most `ALIGNMENT` to where its waveform continues the sound already laid
    (the WSOLA search), so a steady tone keeps its level. Measured against FFmpeg's stretchers in CT-0080:
    `rubberband` either dips steady tones (crisp) or misplaces transients (mixed), and drifts with the content;
    `atempo` drifts and drops transients."""

    grain = int(round((grain_seconds or GRAIN) * sample_rate))
    hop = int(round((hop_seconds or HOP) * sample_rate))
    search = int(round(ALIGNMENT * sample_rate))
    window = np.hanning(grain + 1)[:-1].astype(np.float32)
    # Where each output grain starts, and the media sample its centre shows.
    starts = list(range(-grain // 2, total, hop))
    centres = [(start + grain / 2) / sample_rate for start in starts]
    media = [float(_media_at(timemap, Fraction(round(c * sample_rate), sample_rate))) for c in centres]
    lowest = min(media) - (grain / 2 + 2 * search + hop) / sample_rate
    highest = max(media) + (grain / 2 + 2 * search + hop) / sample_rate
    source = _read(heard, lowest, highest - lowest, sample_rate).sum(axis=1) / 2.0
    stereo = _read(heard, lowest, highest - lowest, sample_rate)
    out = np.zeros((total + 2 * grain, 2), np.float32)
    norm = np.zeros(total + 2 * grain, np.float32)
    # The attacks, and the output sample the map puts each at: kept out of the grains (where they would repeat
    # or land early) and laid whole, at speed 1, on their instant afterwards.
    kept = _attack_places(stereo, lowest, media, starts, grain, sample_rate, total)
    natural = None  # where the previous grain would have continued, in the source
    for start, at in zip(starts, media):
        anchor = int(round((at - lowest) * sample_rate)) - grain // 2
        offset = 0
        if natural is not None:
            # Of the candidates within +/-search of the anchor, the one most like the natural continuation.
            reference = source[natural:natural + grain] * window
            # From the anchor outwards, so a tie -- silence, where every candidate scores nothing -- keeps the grain
            # where the map puts it.
            best = -np.inf
            for shift in sorted(range(-search, search + 1, 4), key=abs):
                candidate = source[anchor + shift:anchor + shift + grain]
                if len(candidate) < grain or len(reference) < grain:
                    continue
                score = float(np.dot(reference, candidate * window))
                if score > best + 1e-9 * (1.0 + abs(best) if best > -np.inf else 1.0):
                    best, offset = score, shift
        read = anchor + offset
        piece = stereo[read:read + grain]
        if len(piece) < grain:
            piece = np.pad(piece, ((0, grain - len(piece)), (0, 0)))
        for at, _place, room, _edge in kept:  # an attack inside this grain is the copy's, not the grain's
            lo, hi = max(at - read, 0), min(at + room - read, grain)
            if lo < hi:
                piece = piece.copy()
                piece[lo:hi] = 0.0
        lo = start + grain  # `out` is padded by a grain at the front
        out[lo:lo + grain] += piece * window[:, None]
        norm[lo:lo + grain] += window
        natural = read + hop
    body = out[grain:grain + total]
    weights = norm[grain:grain + total]
    laid = body / np.maximum(weights, 1e-6)[:, None]
    # Attacks laid as they are, at speed 1, where the map puts them: WSOLA halves them at 2x (they fall in some
    # of the overlapping grains) and repeats them early at 0.5x; a copy keeps them whole and on their instant.
    return _lay_attacks(laid, stereo, kept, sample_rate)


#: An attack: a 2 ms frame this many times louder (in energy) than the loudest of the 8 ms before it, above
#: -50 dBFS, at least `ATTACK_SPACING` after the last one. Laid at speed 1 for `ATTACK_LENGTH` after its start,
#: or until the next attack -- each keeps its own instant.
ATTACK_RISE = 8.0
ATTACK_FLOOR = 10 ** (-50 / 10)
ATTACK_LENGTH = 0.025
ATTACK_FADE = 0.003
ATTACK_SPACING = 0.008


def attacks(mono: np.ndarray, sample_rate: int) -> list[int]:
    """Where attacks start in a sound, in samples: a sharp rise of energy over what came just before."""

    frame = int(round(0.002 * sample_rate))
    count = len(mono) // frame
    if count < 12:
        return []
    energy = (mono[: count * frame].reshape(count, frame) ** 2).mean(axis=1)
    found: list[int] = []
    back = max(1, int(round(ATTACK_SPACING / 0.002)))  # the energy just before: as far back as attacks may be apart
    for index in range(back, count):
        before = energy[index - back:index].max()
        if energy[index] > ATTACK_FLOOR and energy[index] > ATTACK_RISE * max(before, 1e-12):
            # To the sample: where, in this frame and the one before, the sound first reaches a quarter of the
            # attack's peak -- the frame only says where to look.
            lo = (index - 1) * frame
            window = np.abs(mono[lo:(index + 1) * frame])
            start = lo + int(np.argmax(window > 0.25 * float(window.max())))
            if not found or start - found[-1] > ATTACK_SPACING * sample_rate:
                found.append(start)
    return found


def _attack_places(stereo: np.ndarray, lowest: float, media: list[float], starts: list[int], grain: int,
                   sample_rate: int, total: int) -> list[tuple[int, int, int, int]]:
    """Each attack of the source (its sample in `stereo`) and the output sample the map puts it at -- only where
    the map runs forward, and only those that land inside the output."""

    centres = np.array([start + grain / 2 for start in starts], dtype=np.float64)
    shown = np.array(media, dtype=np.float64)
    if len(shown) < 2 or np.any(np.diff(shown) <= 0):
        return []
    longest, fade = int(round(ATTACK_LENGTH * sample_rate)), int(round(ATTACK_FADE * sample_rate))
    found = attacks(stereo.sum(axis=1) / 2, sample_rate)
    places = []
    for index, at in enumerate(found):
        instant = lowest + at / sample_rate
        if not shown[0] <= instant <= shown[-1]:
            continue
        place = int(round(np.interp(instant, shown, centres)))
        # Until the next attack, in the source and in the output, so the next one keeps its own instant; attacks
        # this close cross-fade faster (a quarter of the gap), rather than one being left to the grains.
        room, edge = longest, fade
        if index + 1 < len(found):
            following = found[index + 1]
            next_place = int(round(np.interp(lowest + following / sample_rate, shown, centres)))
            gap = min(following - at, next_place - place)
            edge = max(1, min(fade, gap // 4))
            room = min(room, gap - 2 * edge)
        if room <= 0:
            continue
        if place - edge >= 0 and place + room + edge <= total and at - edge >= 0 and at + room + edge <= len(stereo):
            places.append((at, place, room, edge))
    return places


def _lay_attacks(laid: np.ndarray, stereo: np.ndarray, kept: list[tuple[int, int, int, int]],
                 sample_rate: int) -> np.ndarray:
    out = laid.copy()
    for at, place, room, fade in kept:
        lo, hi = place - fade, place + room + fade
        copy = stereo[at - fade:at + room + fade]
        weight = np.ones(hi - lo, np.float32)
        weight[:fade] = np.linspace(0, 1, fade, dtype=np.float32)
        weight[-fade:] = np.linspace(1, 0, fade, dtype=np.float32)
        out[lo:hi] = out[lo:hi] * (1 - weight[:, None]) + copy * weight[:, None]
    return out


def _media_at(timemap: TimeMap, seconds: Fraction) -> Any:
    """The media instant at output instant `seconds`: the map itself when given, else between frame centres."""

    if timemap.at is not None:
        return timemap.at(seconds)
    position = float(seconds * timemap.fps) - 0.5
    first = min(max(int(np.floor(position)), 0), timemap.frames - 1)
    second = min(first + 1, timemap.frames - 1)
    weight = min(max(position - first, 0.0), 1.0)
    return float(timemap.instants[first]) * (1 - weight) + float(timemap.instants[second]) * weight
