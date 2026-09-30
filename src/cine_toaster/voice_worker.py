"""Runs inside the voice environment: separate, convert each voice, mix the room back.

Standalone on purpose: it imports nothing from the Cine Toaster package, because
the voice engines pin their own numpy and torch (see voice.py). The only thing
it shares is `voice_align.py`, which imports nothing either.

    python voice_worker.py <take> <spec.json> <output.wav> <work-dir> <report.json>

The spec names the speakers (each with a reference recording), the lines in
the order they are spoken, and word timings when the production has them.
With one speaker the whole voice is converted; with several, each speaker's
stretch of the take is converted to their own recording (voice_align).
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import voice_align  # noqa: E402

RATE = 44100


def _sidecar(path: str) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    words = []
    for item in data if isinstance(data, list) else []:
        if isinstance(item, dict):
            words.append({"word": item.get("word") or item.get("palavra") or item.get("text") or "",
                          "start": float(item["start"]), "end": float(item["end"])})
        elif isinstance(item, (list, tuple)) and len(item) >= 3:
            words.append({"word": str(item[2]), "start": float(item[0]), "end": float(item[1])})
    return words


def _heard(vocals: Path) -> list[dict]:
    from faster_whisper import WhisperModel

    model = WhisperModel("small", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(str(vocals), word_timestamps=True)
    return [{"word": word.word, "start": word.start, "end": word.end} for segment in segments for word in segment.words]


def _spans(spec: dict, vocals: Path) -> tuple[list[dict], str]:
    """Each declared line's span, and where the word timings came from.

    The production's words are used only when every line finds its words in
    them: a sidecar written for subtitles may leave out a line, and trusting
    it would hand that line to the other speaker.
    """

    lines = [line for line in spec["lines"] if voice_align._tokens(str(line.get("text") or ""))]
    if spec.get("words"):
        spans = voice_align.align(spec["lines"], _sidecar(spec["words"]))
        if len(spans) == len(lines):
            return spans, Path(spec["words"]).name
    return voice_align.align(spec["lines"], _heard(vocals)), "heard (faster-whisper small)"


def main(take: str, spec_path: str, output: str, work: str, report: str) -> int:
    import librosa
    import numpy as np
    import soundfile as sf
    import torchaudio
    from chatterbox.vc import ChatterboxVC

    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    references = {speaker["who"]: speaker["reference"] for speaker in spec["speakers"]}
    work_dir = Path(work)
    work_dir.mkdir(parents=True, exist_ok=True)
    mix = work_dir / "mix.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", take, "-vn", "-ac", "2", "-ar", str(RATE), str(mix)], check=True)
    started = time.time()
    subprocess.run([sys.executable, "-m", "demucs", "--two-stems", "vocals", "-n", "htdemucs", "-d", "cpu",
                    "-o", str(work_dir), str(mix)], check=True, capture_output=True)
    separated = time.time()
    vocals_path, room_path = work_dir / "htdemucs" / "mix" / "vocals.wav", work_dir / "htdemucs" / "mix" / "no_vocals.wav"
    original, _ = librosa.load(vocals_path, sr=RATE, mono=True)
    ambience, _ = librosa.load(room_path, sr=RATE, mono=False)
    length = ambience.shape[1]
    engine = ChatterboxVC.from_pretrained("cpu")

    def convert(piece: np.ndarray, who: str, name: str) -> np.ndarray:
        """One stretch of voice in `who`'s recorded voice, the same length and level as it came."""

        source = work_dir / f"{name}.wav"
        sf.write(source, piece, RATE)
        converted = engine.generate(str(source), target_voice_path=references[who])
        target = work_dir / f"{name}.converted.wav"
        torchaudio.save(str(target), converted, engine.sr)
        voice, _ = librosa.load(target, sr=RATE, mono=True)
        voice = np.pad(voice, (0, max(0, len(piece) - len(voice))))[: len(piece)]
        return voice * ((np.sqrt(np.mean(piece ** 2)) + 1e-9) / (np.sqrt(np.mean(voice ** 2)) + 1e-9))

    parts = [{"who": spec["speakers"][0]["who"], "start": 0.0, "end": length / RATE}]
    words_source = ""
    if len(references) > 1:
        spans, words_source = _spans(spec, vocals_path)
        parts = voice_align.segments(spans, length / RATE) or parts
    voice = np.zeros(length)
    for index, part in enumerate(parts):
        begin, finish = int(part["start"] * RATE), min(length, int(part["end"] * RATE))
        if finish - begin > RATE // 10:
            voice[begin:finish] = convert(original[begin:finish], part["who"], f"part-{index}")
    sf.write(output, (ambience + voice).T, RATE)
    finished = time.time()
    sf.write(work_dir / "voice.wav", voice, RATE)

    result = {"engine": "chatterbox-vc", "separation": "htdemucs", "watermark": "perth (inaudible, applied by the engine)",
              "separate_seconds": round(separated - started, 1), "convert_seconds": round(finished - separated, 1),
              "segments": parts, "words_source": words_source,
              "unplaced": sorted(set(references) - {part["who"] for part in parts})}
    try:
        from resemblyzer import VoiceEncoder, preprocess_wav

        encoder = VoiceEncoder("cpu")
        likeness = {}
        for who, reference in references.items():
            target = encoder.embed_utterance(preprocess_wav(Path(reference)))
            mine = [part for part in parts if part["who"] == who]
            if not mine:
                likeness[who] = None  # never heard in this take: nothing to measure
                continue

            def similarity(signal: np.ndarray) -> float:
                pieces = [signal[int(p["start"] * RATE):int(p["end"] * RATE)] for p in mine]
                joined = np.concatenate(pieces)
                value = encoder.embed_utterance(preprocess_wav(joined, source_sr=RATE))
                return round(float(value @ target / (np.linalg.norm(value) * np.linalg.norm(target))), 3)

            likeness[who] = {"before": similarity(original), "after": similarity(voice)}
        result["similarity"] = likeness[spec["speakers"][0]["who"]] if len(likeness) == 1 else None
        result["similarity_by_speaker"] = likeness
    except ImportError:
        result["similarity"] = None
    Path(report).write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:6]))
