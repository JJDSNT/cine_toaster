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


#: Where Piper's voices are published (Piper's own download module reads the same place).
VOICE_URL = ("https://huggingface.co/rhasspy/piper-voices/resolve/main/{family}/{code}/{name}/{quality}/"
             "{code}-{name}-{quality}{extension}?download=true")
#: Seconds without a byte before a download is a stalled connection, not a slow one; and how many tries.
STALL_SECONDS = 30
ATTEMPTS = 3


def _voice_urls(voice: str) -> list[tuple[str, str]]:
    try:
        code, name, quality = voice.split("-", 2)
    except ValueError:
        raise PiperVoiceMissing(f"{voice!r} is not a Piper voice name (language-name-quality)") from None
    family = code.split("_")[0]
    return [(VOICE_URL.format(family=family, code=code, name=name, quality=quality, extension=extension), extension)
            for extension in (".onnx", ".onnx.json")]


def _download(url: str, target: Path, opener=None) -> None:
    """One file, written beside its place and moved there whole; a connection silent for `STALL_SECONDS` is given
    up and tried again, up to `ATTEMPTS` times -- a slow network still finishes, a stalled one no longer hangs
    the build (CT-0096: Piper's own download waited ten minutes on a stalled connection)."""

    import socket
    import urllib.request

    opener = opener or urllib.request.urlopen
    partial = target.with_name(target.name + ".part")
    last = None
    for _ in range(ATTEMPTS):
        try:
            with opener(url, timeout=STALL_SECONDS) as response, open(partial, "wb") as handle:
                shutil.copyfileobj(response, handle, 1 << 20)
            partial.replace(target)
            return
        except (OSError, socket.timeout) as error:  # URLError, a reset, a stall: try again
            last = error
            partial.unlink(missing_ok=True)
    raise ProviderError(f"Downloading {target.name} failed {ATTEMPTS} times ({last}); check the connection and run "
                        "again")


def ensure_voice(voices_directory: Path, voice: str = DEFAULT_VOICE, opener=None) -> Path:
    """Download the voice once, into the production, and return its file.

    A voice that lives only in a user's home directory makes a production
    unreproducible on another machine for no reason: the file is small and the
    film is the thing that must survive.
    """

    voices_directory.mkdir(parents=True, exist_ok=True)
    model = voice_path(voices_directory, voice)
    if model.is_file() and model.with_name(model.name + ".json").is_file():
        return model
    for url, extension in _voice_urls(voice):
        _download(url, voices_directory / f"{voice}{extension}", opener)
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
