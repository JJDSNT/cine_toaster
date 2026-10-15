"""Runs in the voice environment: a music track's tempo and beats (CT-0067).

    python beats_worker.py spec.json

`spec.json`: {"audio": ..., "out": ...}. The output is {"tempo": bpm, "beats": [seconds, ...],
"detector": "librosa <version>"}.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main(spec_path: str) -> int:
    import librosa
    import numpy

    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    signal, rate = librosa.load(spec["audio"], sr=22050, mono=True)
    tempo, beats = librosa.beat.beat_track(y=signal, sr=rate, units="time")
    result = {"tempo": round(float(numpy.atleast_1d(tempo)[0]), 3),
              "beats": [round(float(value), 3) for value in beats],
              "detector": f"librosa {librosa.__version__}"}
    Path(spec["out"]).write_text(json.dumps(result), encoding="utf-8")
    print(f"{Path(spec['audio']).name}: {result['tempo']} BPM, {len(result['beats'])} beats", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
