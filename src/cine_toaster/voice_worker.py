"""Runs inside the voice environment: separate, convert the voice, mix the room back.

Standalone on purpose: it imports nothing from Cine Toaster, because the voice
engines pin their own numpy and torch (see voice.py).

    python voice_worker.py <take> <reference.wav> <output.wav> <work-dir> <report.json>
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path


def main(take: str, reference: str, output: str, work: str, report: str) -> int:
    import librosa
    import numpy as np
    import soundfile as sf
    import torchaudio
    from chatterbox.vc import ChatterboxVC

    work_dir = Path(work)
    work_dir.mkdir(parents=True, exist_ok=True)
    mix = work_dir / "mix.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", take, "-vn", "-ac", "2", "-ar", "44100", str(mix)], check=True)
    started = time.time()
    subprocess.run([sys.executable, "-m", "demucs", "--two-stems", "vocals", "-n", "htdemucs", "-d", "cpu",
                    "-o", str(work_dir), str(mix)], check=True, capture_output=True)
    separated = time.time()
    vocals, room = work_dir / "htdemucs" / "mix" / "vocals.wav", work_dir / "htdemucs" / "mix" / "no_vocals.wav"
    engine = ChatterboxVC.from_pretrained("cpu")
    converted = engine.generate(str(vocals), target_voice_path=reference)
    finished = time.time()
    voice_file = work_dir / "voice.wav"
    torchaudio.save(str(voice_file), converted, engine.sr)

    voice, _ = librosa.load(voice_file, sr=44100, mono=True)
    ambience, _ = librosa.load(room, sr=44100, mono=False)
    original, _ = librosa.load(vocals, sr=44100, mono=True)
    length = ambience.shape[1]
    voice = np.pad(voice, (0, max(0, length - len(voice))))[:length]
    # The converted voice sits at the separated voice's level, so the balance with the room holds.
    voice *= (np.sqrt(np.mean(original ** 2)) + 1e-9) / (np.sqrt(np.mean(voice ** 2)) + 1e-9)
    sf.write(output, (ambience + voice).T, 44100)

    result = {"engine": "chatterbox-vc", "separation": "htdemucs", "watermark": "perth (inaudible, applied by the engine)",
              "separate_seconds": round(separated - started, 1), "convert_seconds": round(finished - separated, 1)}
    try:
        from resemblyzer import VoiceEncoder, preprocess_wav

        encoder = VoiceEncoder("cpu")
        target = encoder.embed_utterance(preprocess_wav(Path(reference)))

        def similarity(path: Path) -> float:
            value = encoder.embed_utterance(preprocess_wav(path))
            return round(float(value @ target / (np.linalg.norm(value) * np.linalg.norm(target))), 3)

        result["similarity"] = {"before": similarity(vocals), "after": similarity(voice_file)}
    except ImportError:
        result["similarity"] = None
    Path(report).write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:6]))
