---
id: CT-0040
title: Voice direction — identity, state and delivery (intonation, accent, pace)
type: work
status: done
owner: unassigned
created_at: 2026-09-29
updated_at: 2026-10-03
tags:
  - voice
  - cast
  - dialogue
  - generation
---

# What

Give a production control over how lines sound, as records rather than
prompt prose: accent, timbre, intonation, pace, emphasis. The user asked for
this on 2026-09-29.

# Evidence from SINGULAR

- Voices are described **per scene** (`vozes` in each breakdown) and sent to
  LTX as prompt text. A line's delivery is free text (`como: says weakly`).
- **KAEL drifts.** He has three different descriptions across six breakdowns,
  and only 3-01 gives him "a slight European accent". Part of the difference
  is intended: in 3-01 he is weak and hoarse after stasis. The accent is not:
  it is identity, and it appears and disappears.
- This is ADR 0012's placement problem, for voice: text re-authored per use
  has no canonical version, so nothing can compare against it.

# Proposal: three layers

1. **Identity: the cast member's voice.** It is declared once, on the cast
   entity (SPEC-0003):
   - timbre, age, gender presentation, and accent or dialect (free text,
     plus an optional language code such as `en-GB`);
   - reference recordings for engines that clone.

   It never changes from scene to scene.
2. **State: how the character is now.** Per scene, or per shot: tired,
   hoarse, weak, out of breath. It qualifies the identity and never replaces
   it.
3. **Delivery: one line.** The existing `delivery` stays as free text, with
   optional structured fields:
   - emotion and intensity;
   - pace;
   - volume, from whisper to shout;
   - intonation (rising, falling, flat, or a question);
   - emphasised words and pauses (marked in the text);
   - language, when a line is spoken in another one.

# Rendering, per engine (adapters)

- **Speech made inside the take** (LTX 2.5 generates voices from the prompt):
  the brief composes identity, state and delivery into the prompt, the way
  SINGULAR's `texto_das_falas` does.
- **Voice-over and replacement lines** (TTS):
  - Piper, already wired and offline, has no emotion control;
  - expressive, voice-cloning engines need a spike, with a licence check
    per ADR 0011 before any is adopted. Some popular ones are not
    permissive.
- **Voice consistency across clips.** A model's voice for one character
  drifts between generations. Speech-to-speech conversion to the cast's
  reference voice is a candidate fix, and needs a spike.

# Checks

- A scene that restates a cast member's identity differently from the cast
  sheet: `voice_identity_drift`, which would flag KAEL's accent.
- A line whose delivery asks for something the chosen engine cannot render:
  reported, not silently dropped.

# Done (2026-09-29)

The zero-cost part is implemented, as the SPEC-0003 amendment describes:

- cast sheets with `voice` (identity, accent, language, references),
  `variants` and `names`;
- scene `voice_state` and `cast`, and the `voice_identity_restated` check,
  with the practice "a voice has one identity";
- `[[VOICES]]` in the brief;
- `toast cast list` and `toast cast propose`.

The demo production declares Mara (face, wardrobe, voice), the speaker stack
and the announcer (voice only).

On SINGULAR, read-only, `toast cast propose` shows:

- Kael's three voices;
- a scar above his left eyebrow that only 1-02 and 3-01 describe;
- Claire's sheet changing from `claire_doente` to `claire` between Geneva
  and Boreal, which is an intended variant.

These decisions are left to the user, in `singular/docs/SINGULAR-CINE-TOASTER.md`.

Validation: `tests/test_cast.py` (11 tests) and the brief voice test. Full
suite: 398 OK.

**Cast room** (2026-09-29). The control room gained a **Cast** room, with
each member's:

- master picture ("Voice only" when the sheet does not decide a face);
- names, what the sheet decides, and description;
- voice, with language and playable reference recordings;
- variants, with their pictures;
- every scene they appear in, with shots, variant and the scene's voice
  state, linking to the scene.

The production payload carries `cast[*].appearances`, and voice recordings are
project-relative. Validated with a headless screenshot on a demo copy that has
a variant and a recording, and an appearances test. Full suite: 399 OK.

# Done: voice conversion, the spike and the feature (2026-09-29)

**Spike.** Local and on CPU, so it cost nothing. The candidates were
checked for licences first (ADR 0011):

| Tool | Role | Licence |
| --- | --- | --- |
| Chatterbox VC 0.1.7 | conversion | MIT, code and weights |
| Demucs 4.1 | separation | MIT |
| Resemblyzer | likeness | Apache-2.0 |
| faster-whisper | word checks | MIT |

XTTS and F5-TTS were excluded for their non-commercial weights.

The test used 12 takes where only Kael speaks (1-02, 1-02B, 1-03, 3-01),
against `elenco/voz_kael_genebra.wav`:

- Likeness to the reference rose from 0.672 to 0.816, and its spread fell
  from 0.094 to 0.051.
- Likeness between takes rose from 0.604 to 0.769.
- The word error rate stayed the same (0.051 before and after).
- The speech envelope moved 0–10 ms in 11 takes and 50 ms in one.
- Converting alone removes the room (noise floor −inf). Separating with
  Demucs, converting only the voice and remixing keeps it, with likeness
  0.85 on 1-02 P12 and 0.72 on 3-01 P13.
- Cost: about 5 s of CPU per second of speech.

The comparison video for the author is
`singular/cenas/1-02/ltx/teste-conversao-voz/comparacao-voz-kael.mp4`, with
the numbers in `medicoes.json` beside it. The claims are in knowledge
profile `chatterbox-vc` (7 claims).

**Feature.**

- `voice.py` works out:
  - the take (the selected one, or the first);
  - the single in-take speaker, and the cast sheet it resolves to;
  - the first existing voice recording on that sheet.

  It refuses no speaker, two speakers, no sheet, and no recording.
- `voice_worker.py` is standalone, importing nothing from Cine Toaster.
  It separates, converts, remixes at the separated voice's level, and
  measures likeness.
- Job kind `convert_voice` runs the worker in `.venv-voice` (or
  `CINE_TOASTER_VOICE_PYTHON`) as a cancellable process. It muxes the new
  sound under the untouched picture into `_takes/<stem>-voice.mp4`, and
  writes provenance: source take, member, recording and digest, engines,
  timings, likeness.
- CLI `toast revoice <project> <scene> <shot> [--take] [--dry-run]`. The
  name `toast voice` was already Piper narration.
- `make install-voice` and `requirements-voice.txt` (pinned). A separate
  environment is needed because Chatterbox pins `numpy<2`, `torch==2.6`
  and `transformers`.
- `toast doctor` reports "Voice conversion".
- Docs are in `docs/voice-conversion.md`.

**Validation.**

- `tests/test_voice.py` (4 tests, with a fake voice interpreter) covers
  the plan, refusals, and the new take with lineage and untouched picture.
- A real run on the SINGULAR scratch copy, with a Kael sheet written only
  in the copy: 3-01 P13 became take `VOICE`, likeness 0.474 → 0.727, in
  64 s.

Remaining:

- the author listening, deferred at the author's request (2026-09-29).
  They will judge whether Kael's converted voice in 3-01 still sounds ill
  or has become healthy. Until then, conversion is not applied where the
  state of the voice matters. Noted in `singular/docs/SINGULAR-CINE-TOASTER.md`;
- ~~converting per speaker in two-speaker takes~~ done 2026-09-30 without
  diarization: `voice_align.py` aligns the declared lines to word timings
  (the production sidecar only when it contains every line, else
  faster-whisper on the separated voice); the worker converts each
  speaker's stretch to their own recording. Provenance gains `segments`,
  `words_source`, `similarity_by_speaker` and `unplaced`; the CLI and the
  comparison room offer it for any number of speakers.
  Validated: on SINGULAR's only two-speaker shot (3-01 P2) the take holds
  no "Claire?!" at all (the voice track is silent until 6.5 s), and the
  sidecar lacks it too; the run reported KAEL `unplaced` rather than
  inventing a likeness. On a test take joined from 3-01 c15 (Kael) and c02
  (Lira), the cut fell at 3.12 s against the real joint at 3.04 s; likeness
  Kael 0.527 → 0.498, Lira 0.817 → 0.765. Comparison video sent to the
  author. `tests/test_voice.py`: 8 tests (alignment, three speakers,
  two-speaker job, an incomplete sidecar not trusted).
- ~~a control-room action~~ done 2026-09-30: "Revoice as <speaker>" on a
  take card in the comparison room, when the shot has one speaker in the
  take. It starts `convert_voice`, and the new take appears once adopted.
  Checked headless with a fake voice interpreter.
- ~~applying conversion inside `assemble` rather than as a take~~ done
  2026-09-30. A decision on the shot, `voices` in `state.json` (schema 5),
  command `set_voice` (`toast revoice --in-cut|--take-sound`, a switch in the
  comparison room). The assemble job converts each marked shot's chosen take
  and caches the audio in the operational state, keyed by the take, the
  recordings, the lines and the worker. Decision: a decision, not a take,
  so choosing another take keeps the voice, and the alternatives are not
  cluttered by converted copies. Validated: `tests/test_voice.py` (9 tests,
  the cache hit included); on the SINGULAR scratch copy, 3-01 P13 marked and
  3-01 assembled as v1 (85.5 s, 85 s of CPU), P13 likeness 0.475 → 0.741, no
  new take. Comparison sent to the author.

# Order

- **Now, at no cost:** voice identity on the cast sheet, state and delivery
  fields, the brief composing them, and the drift check (with SINGULAR's
  scene-level `vozes` read for comparison).
- **Later:** ~~a voice-conversion spike~~ done on CPU at no cost; expressive TTS
  for voice-over lines is still open.

# Closed (2026-10-03, close-out pass)

Voice identity, state and delivery, the drift check, voice conversion with the cache and the voice in the cut are delivered.

What remains moved to the backlog (`development/roadmap.md` § Backlog): The author re-checks Kael's converted voice; expressive TTS for voice-over lines.
