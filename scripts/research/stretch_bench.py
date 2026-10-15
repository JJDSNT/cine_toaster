"""CT-0080's time-stretch benchmark: candidate stretchers on one time map and one set of signals.

    PYTHONPATH=src:<candidates> python scripts/research/stretch_bench.py <folder> [<real recordings>...]

The map (output seconds -> media seconds) runs 1x for a second, 2x for a second, 0.5x for a second: two
changes of speed, a speed-up and a slow-down. Each backend is driven as faithfully as its interface allows:
Rubber Band's native offline engine with a key-frame map every 10 ms; Signalsmith Stretch and SoundTouch as
streams whose tempo follows the map block by block; AudioTSM's WSOLA with its speed following the map; our
anchored WSOLA on the map itself; FFmpeg's rubberband filter piece by piece (the earlier path).

Measured: exact length; every click's error against where the map puts it, and clicks lost or doubled; pitch
in each speed's stretch of a sine; the sine's level (min and max of its envelope -- dips at the changes); on
real recordings, onsets matched against the source's mapped through the map; time per second of sound.
"""

from __future__ import annotations

import ctypes
import json
import subprocess
import sys
import time
from fractions import Fraction
from pathlib import Path

import numpy as np

RATE = 48000
SECOND = Fraction(1)


def mapped(seconds: float) -> float:
    """Output seconds -> media seconds (from the media's 0): 1x, then 2x, then 0.5x."""

    if seconds < 1:
        return seconds
    if seconds < 2:
        return 1 + 2 * (seconds - 1)
    return 3 + 0.5 * (seconds - 2)


TOTAL_SECONDS = 3.0
TOTAL = int(TOTAL_SECONDS * RATE)
MEDIA_SECONDS = mapped(TOTAL_SECONDS)


def unmapped(media: np.ndarray) -> np.ndarray:
    grid = np.linspace(0, TOTAL_SECONDS, 30001)
    return np.interp(media, [mapped(t) for t in grid], grid)


# --- signals ---------------------------------------------------------------------------------------------------

def sine() -> np.ndarray:
    t = np.arange(int((MEDIA_SECONDS + 0.5) * RATE)) / RATE
    tone = (0.25 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    return np.stack([tone, tone], axis=1)


def clicks() -> tuple[np.ndarray, np.ndarray]:
    n = int((MEDIA_SECONDS + 0.5) * RATE)
    out = np.zeros((n, 2), np.float32)
    at = np.arange(int(0.13 * RATE), int(MEDIA_SECONDS * RATE) - 2400, int(0.17 * RATE))  # off any grid
    for start in at:
        out[start:start + 96] = 0.8
    return out, at / RATE


def recording(path: Path) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(path), "-t", f"{MEDIA_SECONDS + 0.5}", "-ac", "2",
                          "-ar", str(RATE), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()


# --- backends: (source stereo, map) -> TOTAL samples ----------------------------------------------------------

def ours(source: np.ndarray, work: Path) -> np.ndarray:
    from cine_toaster import retime_sound as rs

    wav = work / "source.wav"
    _write(wav, source)
    fps = Fraction(24)
    frames = int(TOTAL_SECONDS * 24)
    timemap = rs.TimeMap(fps, Fraction(0), tuple(Fraction(mapped((f + 0.5) / 24)) for f in range(frames)),
                         at=lambda t: Fraction(mapped(float(t))))
    return rs.anchored(wav, timemap, TOTAL, RATE)


def ffmpeg_pieces(source: np.ndarray, work: Path) -> np.ndarray:
    from cine_toaster import retime_sound as rs

    wav = work / "source.wav"
    _write(wav, source)
    fps = Fraction(24)
    frames = int(TOTAL_SECONDS * 24)
    timemap = rs.TimeMap(fps, Fraction(0), tuple(Fraction(mapped((f + 0.5) / 24)) for f in range(frames)),
                         at=lambda t: Fraction(mapped(float(t))))
    return rs._joined(timemap.pieces(), timemap, wav, TOTAL, RATE, "rubberband")


def rubberband_native(source: np.ndarray, work: Path) -> np.ndarray:
    """Rubber Band's own C API (the system's librubberband, through ctypes -- pylibrb's key-frame binding does not
    accept a map): offline, the R3 engine, the whole input studied, a key-frame map every 10 ms."""

    lib = ctypes.CDLL("librubberband.so.2")
    lib.rubberband_new.restype = ctypes.c_void_p
    lib.rubberband_new.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_int, ctypes.c_double, ctypes.c_double]
    for name in ("rubberband_set_expected_input_duration", "rubberband_set_max_process_size"):
        getattr(lib, name).argtypes = [ctypes.c_void_p, ctypes.c_uint]
    lib.rubberband_set_key_frame_map.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.POINTER(ctypes.c_uint),
                                                 ctypes.POINTER(ctypes.c_uint)]
    channel = ctypes.POINTER(ctypes.c_float) * 2
    for name in ("rubberband_study", "rubberband_process"):
        getattr(lib, name).argtypes = [ctypes.c_void_p, channel, ctypes.c_uint, ctypes.c_int]
    lib.rubberband_available.argtypes = [ctypes.c_void_p]
    lib.rubberband_available.restype = ctypes.c_int
    lib.rubberband_retrieve.argtypes = [ctypes.c_void_p, channel, ctypes.c_uint]
    lib.rubberband_retrieve.restype = ctypes.c_uint
    offline_finer = 0x00000000 | 0x20000000  # ProcessOffline | EngineFiner
    length = int(MEDIA_SECONDS * RATE)
    state = ctypes.c_void_p(lib.rubberband_new(RATE, 2, offline_finer, TOTAL / length, 1.0))
    lib.rubberband_set_expected_input_duration(state, length)
    lib.rubberband_set_max_process_size(state, length)
    hop = RATE // 100
    before = [int(round(mapped(o / RATE) * RATE)) for o in range(hop, TOTAL, hop)]
    after = list(range(hop, TOTAL, hop))
    lib.rubberband_set_key_frame_map(state, len(before), (ctypes.c_uint * len(before))(*before),
                                     (ctypes.c_uint * len(after))(*after))
    planes = [np.ascontiguousarray(source[:length, c], np.float32) for c in range(2)]
    pointers = channel(*[plane.ctypes.data_as(ctypes.POINTER(ctypes.c_float)) for plane in planes])
    lib.rubberband_study(state, pointers, length, 1)
    lib.rubberband_process(state, pointers, length, 1)
    chunks = []
    while True:
        ready = lib.rubberband_available(state)
        if ready <= 0:
            break
        out = [np.zeros(ready, np.float32) for _ in range(2)]
        got = lib.rubberband_retrieve(state, channel(*[o.ctypes.data_as(ctypes.POINTER(ctypes.c_float)) for o in out]),
                                      ready)
        chunks.append(np.stack([o[:got] for o in out], axis=1))
    return _fit(np.concatenate(chunks) if chunks else np.zeros((0, 2), np.float32))


def signalsmith(source: np.ndarray, work: Path) -> np.ndarray:
    from python_stretch.Signalsmith import Stretch

    stretch = Stretch()
    stretch.preset(2, RATE)
    return _streamed(source, lambda block, factor: (stretch.setTimeFactor(factor), stretch.process(block.T).T)[1],
                     pilot=lambda: _fresh_signalsmith())


def _fresh_signalsmith():
    from python_stretch.Signalsmith import Stretch

    stretch = Stretch()
    stretch.preset(2, RATE)
    return lambda block, factor: (stretch.setTimeFactor(factor), stretch.process(block.T).T)[1]


def soundtouch(source: np.ndarray, work: Path) -> np.ndarray:
    return _streamed(source, _fresh_soundtouch(), pilot=_fresh_soundtouch)


def _fresh_soundtouch():
    lib = ctypes.CDLL("libSoundTouchDll.so.1")
    lib.soundtouch_createInstance.restype = ctypes.c_void_p
    handle = ctypes.c_void_p(lib.soundtouch_createInstance())
    lib.soundtouch_setSampleRate(handle, ctypes.c_uint(RATE))
    lib.soundtouch_setChannels(handle, ctypes.c_uint(2))
    lib.soundtouch_setTempo.argtypes = [ctypes.c_void_p, ctypes.c_float]
    lib.soundtouch_putSamples.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_float), ctypes.c_uint]
    lib.soundtouch_receiveSamples.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_float), ctypes.c_uint]
    lib.soundtouch_receiveSamples.restype = ctypes.c_uint

    def step(block: np.ndarray, factor: float) -> np.ndarray:
        lib.soundtouch_setTempo(handle, ctypes.c_float(factor))
        data = np.ascontiguousarray(block, np.float32)
        lib.soundtouch_putSamples(handle, data.ctypes.data_as(ctypes.POINTER(ctypes.c_float)), ctypes.c_uint(len(data)))
        out = np.zeros((len(data) * 4 + 8192, 2), np.float32)
        got = lib.soundtouch_receiveSamples(handle, out.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                                            ctypes.c_uint(len(out)))
        return out[:got]

    return step


def audiotsm_wsola(source: np.ndarray, work: Path) -> np.ndarray:
    return _streamed(source, _fresh_audiotsm(), pilot=_fresh_audiotsm)


def _fresh_audiotsm():
    from audiotsm import wsola
    from audiotsm.io.array import ArrayReader, ArrayWriter

    tsm = wsola(2)

    def step(block: np.ndarray, factor: float) -> np.ndarray:
        tsm.set_speed(factor)
        reader, writer = ArrayReader(np.ascontiguousarray(block.T)), ArrayWriter(2)
        while not reader.empty:
            tsm.read_from(reader)
            tsm.write_to(writer)
        return writer.data.T.astype(np.float32)

    return step


def _streamed(source: np.ndarray, step, pilot) -> np.ndarray:
    """A streaming stretcher fed block by block, each block the media its 10 ms of output shows, its tempo the
    block's speed; its latency measured with a pilot click through a fresh instance, and removed."""

    hop = RATE // 100
    pieces = []
    for start in range(0, TOTAL + 4 * hop, hop):
        a, b = int(round(mapped(start / RATE) * RATE)), int(round(mapped((start + hop) / RATE) * RATE))
        block = source[a:b] if b > a else np.zeros((1, 2), np.float32)
        pieces.append(step(block, max(1e-3, (b - a) / hop)))
    out = np.concatenate([piece for piece in pieces if len(piece)]) if pieces else np.zeros((0, 2), np.float32)
    late = _latency(pilot())
    return _fit(out[late:])


def _latency(step) -> int:
    hop = RATE // 100
    pilot = np.zeros((RATE, 2), np.float32)
    pilot[RATE // 4:RATE // 4 + 96] = 0.8
    out = np.concatenate([step(pilot[i:i + hop], 1.0) for i in range(0, len(pilot), hop)] +
                         [step(np.zeros((hop, 2), np.float32), 1.0) for _ in range(40)])
    loud = np.nonzero(np.abs(out.sum(axis=1)) > 0.3)[0]
    return int(loud[0] - RATE // 4) if len(loud) else 0


def _fit(out: np.ndarray) -> np.ndarray:
    fitted = np.zeros((TOTAL, 2), np.float32)
    fitted[: min(TOTAL, len(out))] = out[:TOTAL]
    return fitted


def _write(path: Path, data: np.ndarray) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "f32le", "-ar", str(RATE), "-ac", "2", "-i", "-",
                    "-c:a", "pcm_f32le", str(path)], input=np.ascontiguousarray(data, np.float32).tobytes(), check=True)


# --- measures --------------------------------------------------------------------------------------------------

def click_errors(out: np.ndarray, media_at: np.ndarray) -> dict:
    mono = np.abs(out.sum(axis=1)) / 2
    loud = np.nonzero(mono > 0.2)[0]
    onsets = loud[np.insert(np.diff(loud) > RATE // 50, 0, True)] if len(loud) else np.array([], int)
    expected = (unmapped(media_at) * RATE).astype(int)
    expected = expected[(expected > RATE // 50) & (expected < TOTAL - RATE // 50)]
    errors, used = [], set()
    for e in expected:
        if not len(onsets):
            break
        near = int(np.argmin(np.abs(onsets - e)))
        if abs(onsets[near] - e) < RATE // 40:
            errors.append(int(onsets[near] - e))
            used.add(near)
    extra = len(onsets) - len(used)
    errors = np.array(errors) if errors else np.array([0])
    return {"found": f"{len(used)}/{len(expected)}", "extra": int(extra), "mean_ms": round(float(errors.mean()) / 48, 2),
            "worst_ms": round(float(np.abs(errors).max()) / 48, 2)}


def tone(out: np.ndarray) -> dict:
    mono = out.sum(axis=1) / 2
    level = np.abs(mono[RATE // 20: TOTAL - RATE // 20]).reshape(-1, 240)
    envelope = level.max(axis=1)
    pitches = []
    for lo, hi in ((0.1, 0.9), (1.1, 1.9), (2.1, 2.9)):
        part = mono[int(lo * RATE):int(hi * RATE)]
        part = part * np.hanning(len(part))
        spectrum = np.abs(np.fft.rfft(part, 8 * len(part)))
        pitches.append(round(float(np.argmax(spectrum) * RATE / (8 * len(part))), 1))
    return {"level_min_db": round(float(20 * np.log10(envelope.min() / 0.25 + 1e-9)), 2),
            "level_max_db": round(float(20 * np.log10(envelope.max() / 0.25 + 1e-9)), 2), "pitch": pitches}


def onsets(mono: np.ndarray) -> np.ndarray:
    frame = 512
    energy = np.array([float(np.sum(mono[i:i + frame] ** 2)) for i in range(0, len(mono) - frame, frame // 2)])
    flux = np.maximum(0, np.diff(np.log(energy + 1e-9)))
    threshold = np.median(flux) + 3 * np.std(flux)
    peaks = [i for i in range(1, len(flux) - 1) if flux[i] > threshold and flux[i] >= flux[i - 1] and flux[i] > flux[i + 1]]
    return np.array(peaks, int) * (frame // 2)


def real(out: np.ndarray, source: np.ndarray) -> dict:
    found = onsets(out.sum(axis=1) / 2)
    media = onsets(source[: int(MEDIA_SECONDS * RATE)].sum(axis=1) / 2) / RATE
    expected = unmapped(media) * RATE
    errors = [float(found[np.argmin(np.abs(found - e))] - e) for e in expected if len(found) and
              np.min(np.abs(found - e)) < RATE * 0.03]
    return {"onsets_matched": f"{len(errors)}/{len(expected)}",
            "median_ms": round(float(np.median(np.abs(errors))) / 48, 2) if errors else None}


BACKENDS = {"anchored-wsola (ours)": ours, "ffmpeg-rubberband pieces": ffmpeg_pieces,
            "rubberband native R3 + keyframes": rubberband_native, "signalsmith stretch": signalsmith,
            "soundtouch": soundtouch, "audiotsm wsola": audiotsm_wsola}


def main() -> None:
    folder = Path(sys.argv[1])
    folder.mkdir(parents=True, exist_ok=True)
    recordings = [Path(arg) for arg in sys.argv[2:]]
    tone_source, (click_source, click_at) = sine(), clicks()
    reals = {path.stem: recording(path) for path in recordings}
    results = {}
    for name, backend in BACKENDS.items():
        row = {}
        try:
            began = time.time()
            out = backend(tone_source, folder)
            row["seconds_per_second"] = round((time.time() - began) / TOTAL_SECONDS, 3)
            row["length_exact"] = len(out) == TOTAL
            row.update(tone(out))
            row["clicks"] = click_errors(backend(click_source, folder), click_at)
            for stem, source in reals.items():
                row[stem] = real(backend(source, folder), source)
        except Exception as error:  # a backend that cannot run here is reported, not hidden
            row["error"] = f"{type(error).__name__}: {error}"[:200]
        results[name] = row
        print(name, json.dumps(row), flush=True)
    (folder / "results.json").write_text(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
