"""Narration, offline and free, from a voice the machine downloads once.

The reel declares its narration -- who speaks, in what voice, where it sits in
the mix -- and declaring it was never the hard part. Making it was, and making
it needed the tool to own a generator rather than borrow one.

Piper is chosen for the first audio provider because it costs nothing, needs no
account, and runs on the machine that is already there. A demo that needs a
credential is a demo most people never see run, and the reel's end card claims
it cost nothing.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from . import GenerationResult, ProviderError, ProviderNotConfigured


#: The voice used when a line names none. Chosen for being unremarkable: a
#: narrator the listener stops noticing is doing its job.
DEFAULT_VOICE = "en_US-lessac-medium"

#: Where a downloaded voice is kept. Beside the production, so a film carries
#: the voice it was narrated with rather than depending on a machine.
VOICES_DIRECTORY = "voices"


class PiperNotInstalled(ProviderNotConfigured):
    """Piper is not importable, so nothing can be spoken."""

    code = "piper_not_installed"


class PiperVoiceMissing(ProviderNotConfigured):
    """The voice model has not been downloaded yet."""

    code = "piper_voice_missing"


def _executable() -> str:
    """Piper's CLI, preferring the one in this interpreter's environment."""

    beside = Path(sys.executable).with_name("piper")
    if beside.is_file():
        return str(beside)
    found = shutil.which("piper")
    if found:
        return found
    raise PiperNotInstalled(
        "Piper is not installed. Install it with: uv sync --extra audio "
        "(or: pip install -e '.[audio]')"
    )


def voice_path(voices_directory: Path, voice: str) -> Path:
    return voices_directory / f"{voice}.onnx"


def ensure_voice(voices_directory: Path, voice: str = DEFAULT_VOICE) -> Path:
    """Download the voice once, into the production, and return its file.

    A voice that lives only in a user's home directory makes a production
    unreproducible on another machine for no reason: the file is small and the
    film is the thing that must survive.
    """

    voices_directory.mkdir(parents=True, exist_ok=True)
    model = voice_path(voices_directory, voice)
    if model.is_file():
        return model

    try:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "piper.download_voices",
                voice,
                "--download-dir",
                str(voices_directory),
            ],
            capture_output=True,
            text=True,
            timeout=600,
        )
    except FileNotFoundError as error:  # pragma: no cover - interpreter is always there
        raise PiperNotInstalled(str(error)) from error
    except subprocess.TimeoutExpired as error:
        raise ProviderError(f"Downloading the voice {voice!r} timed out.") from error

    if completed.returncode != 0 or not model.is_file():
        raise PiperVoiceMissing(
            f"Could not download the voice {voice!r}. "
            f"{(completed.stderr or completed.stdout or '').strip()[:300]}"
        )
    return model


class PiperNarration:
    """Text to a spoken WAV file, with nothing sent anywhere."""

    id = "piper"

    def __init__(self, voices_directory: Path, voice: str = DEFAULT_VOICE) -> None:
        self.voices_directory = Path(voices_directory)
        self.voice = voice

    def speak(
        self,
        *,
        text: str,
        output: Path,
        rate: float = 1.0,
        sentence_silence: float = 0.3,
    ) -> GenerationResult:
        """Say `text` into `output`.

        `rate` is the everyday sense of the word: above 1.0 is faster. Piper
        wants the inverse as a length scale, and translating it here keeps the
        inversion out of every caller.
        """

        if not text.strip():
            raise ProviderError("Nothing to speak: the line is empty.")
        if rate <= 0:
            raise ProviderError(f"Speaking rate must be positive, not {rate}.")

        executable = _executable()
        model = ensure_voice(self.voices_directory, self.voice)
        output.parent.mkdir(parents=True, exist_ok=True)

        completed = subprocess.run(
            [
                executable,
                "--model",
                str(model),
                "--length-scale",
                f"{1.0 / rate:.4f}",
                "--sentence-silence",
                str(sentence_silence),
                "--output_file",
                str(output),
            ],
            input=text,
            capture_output=True,
            text=True,
            timeout=600,
        )
        if completed.returncode != 0:
            raise ProviderError(
                f"Piper failed ({completed.returncode}): {completed.stderr.strip()[:300]}"
            )
        if not output.is_file():
            raise ProviderError(f"Piper reported success but wrote no file at {output}.")

        return GenerationResult(
            media=output,
            provider=self.id,
            model=self.voice,
            seed=0,
            duration_seconds=_wav_seconds(output),
            cost_usd=0.0,
            provenance={
                "piper": {
                    "voice": self.voice,
                    "voice_file": model.name,
                    "rate": rate,
                    "sentence_silence": sentence_silence,
                    "offline": True,
                }
            },
        )


def _wav_seconds(path: Path) -> float:
    """Length from the file itself, never from what was asked for."""

    import wave

    try:
        with wave.open(str(path), "rb") as handle:
            frames = handle.getnframes()
            rate = handle.getframerate()
        return round(frames / rate, 3) if rate else 0.0
    except Exception:
        return 0.0
