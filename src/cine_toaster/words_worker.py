"""Runs in the voice environment: word timings for takes that have none (CT-0054).

    python words_worker.py spec.json

`spec.json`: {"takes": [{"media": ..., "out": ...}], "model": "small", "language": "en"}. Each output is a
list of [start, end, word] -- the form SINGULAR writes and Cine Toaster reads.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main(spec_path: str) -> int:
    from faster_whisper import WhisperModel

    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    model = WhisperModel(spec.get("model") or "small", device="cpu", compute_type="int8")
    for take in spec["takes"]:
        segments, _ = model.transcribe(take["media"], word_timestamps=True, language=spec.get("language") or None)
        words = [[round(word.start, 3), round(word.end, 3), word.word] for segment in segments
                 for word in segment.words or []]
        Path(take["out"]).write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
        print(f"{Path(take['media']).name}: {len(words)} words", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
