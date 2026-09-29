---
id: CT-0040
title: Voice direction — identity, state and delivery (intonation, accent, pace)
type: work
status: ready
owner: unassigned
created_at: 2026-09-29
updated_at: 2026-09-29
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

# Order

- **Now, at no cost:** voice identity on the cast sheet, state and delivery
  fields, the brief composing them, and the drift check (with SINGULAR's
  scene-level `vozes` read for comparison).
- **Later:** a TTS and voice-conversion spike, which needs a GPU and budget
  decision.
