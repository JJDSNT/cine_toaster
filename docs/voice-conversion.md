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

In the comparison room, a take offers **Revoice as <speaker>** (or
**Revoice <A> and <B>** with several speakers), which starts the same job.

## What it needs

- The shot declares who speaks in the take (`lines`, in order).
- Every speaker has a **cast sheet** with a voice recording: a few clean
  seconds of the voice. A speaker without one stops the plan, by name.

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

## Several speakers

There is no diarization model. The breakdown already says who says what,
in order; word timings say when each word was spoken. `voice_align.py`
aligns the two (tolerating misheard and extra words), and each speaker's
stretch of the take is converted to their own recording. The stretches
cover the take end to end; between two speakers the cut falls in the pause.

Word timings come from the production's sidecar (`words_sidecar`, e.g.
`{stem}.palavras.json`) **only when every declared line is found in it**. A
sidecar written for subtitles may leave a line out, and trusting it would
hand that line to the other speaker. Otherwise the separated voice is
transcribed (faster-whisper `small`, CPU). The provenance records:

- `segments`: who was converted where;
- `words_source`: the sidecar, or `heard`;
- `similarity_by_speaker`: likeness before and after, per speaker, measured
  on their own stretches;
- `unplaced`: speakers declared but never heard in the take. Their likeness
  is not measured, and `toast revoice` warns.

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

On a two-speaker test take (2026-09-30: SINGULAR's Kael, "Who are you?",
then Lira, "No. My name is Lira."), the cut fell at 3.12 s against a real
joint at 3.04 s. Likeness: Kael 0.53 → 0.50, Lira 0.82 → 0.77 (Lira's
recording was a 12 s test cut from her own takes). A take that already
sounds like its speaker gains nothing from conversion; it is for takes
whose voice has drifted.

The claims are in the `chatterbox-vc` knowledge profile
(`toast knowledge --show chatterbox-vc`). A quiet, weak delivery comes back
at its level, but whether the weakness survives is for a listener to judge.

The engines are MIT (Chatterbox, Demucs) and Apache-2.0 (Resemblyzer).
Chatterbox puts an inaudible watermark (Perth) in what it makes. They pin
their own numpy and torch, so they live in `.venv-voice`, or in the
interpreter named by `CINE_TOASTER_VOICE_PYTHON`, and run as a process that a
job can cancel.
