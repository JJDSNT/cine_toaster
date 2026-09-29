# Converting a take's voice

A video model gives a character a slightly different voice in every
generation. `toast revoice` converts a take's speech to the cast member's own
recording and keeps the room, the words and the timing. The result is a
**new take** of the shot, beside the others. Nothing is replaced.

```bash
make install-voice                                   # once: .venv-voice, about 2 GB, CPU only
toast revoice <project> 3-01 P13 --dry-run           # whose voice, which recording
toast revoice <project> 3-01 P13 [--take BLOCK-2]    # -> _takes/c13-voice.mp4, take VOICE
```

## What it needs

- The shot declares **one** speaker in the take (`lines`, not `mix: true`).
  A take with two speakers is refused: conversion would turn both into the
  same voice.
- The speaker has a **cast sheet** with a voice recording: a few clean
  seconds of the voice.

  ```yaml
  voice:
    identity: a low, controlled male voice
    references: [voice.wav]
  ```

## How it works

1. The take's sound is separated into voice and everything else (Demucs,
   `htdemucs`).
2. Only the voice is converted to the recording (Chatterbox).
3. The converted voice is set to the separated voice's level and mixed back
   with the room.
4. The result goes under the take's picture, which is copied untouched.

The new take's `.provenance.json` records:

- the source take, the cast member, and the recording with its digest;
- the engines;
- how long each step took;
- the likeness to the recording before and after (Resemblyzer).

## What was measured

On 12 of SINGULAR's takes of Kael, 2026-09-29:

- Likeness rose from 0.67 to 0.82 on average, and the spread across takes
  halved.
- The words were recognised as before.
- The timing moved 0 to 10 ms, so the mouths still match.

The claims are in the `chatterbox-vc` knowledge profile
(`toast knowledge --show chatterbox-vc`). A quiet, weak delivery comes back
at its level, but whether the weakness survives is for a listener to judge.

The engines are MIT (Chatterbox, Demucs) and Apache-2.0 (Resemblyzer).
Chatterbox puts an inaudible watermark (Perth) in what it makes. They pin
their own numpy and torch, so they live in `.venv-voice`, or in the
interpreter named by `CINE_TOASTER_VOICE_PYTHON`, and run as a process that a
job can cancel.
