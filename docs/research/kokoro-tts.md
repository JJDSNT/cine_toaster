# Kokoro — Local text-to-speech candidate

Status: **Reference / evaluation candidate** (not an implemented integration)

Upstream: https://github.com/hexgrad/kokoro

## Purpose

Evaluate Kokoro as a local, open-weight text-to-speech (TTS) backend for Cine Toaster's voice-production pipeline. Kokoro-82M is a compact speech synthesis model distributed under Apache-2.0; verify the licensing and provenance of individual voice assets before production use.

## Potential use cases

- Dialogue scratch tracks and animatics, with reproducible timing and voice selection.
- Narration and commercial voice-over.
- Multilingual dialogue and dubbing prototypes, subject to per-language quality checks.
- Automated audio previews for editorial review.

## Proposed integration direction

Treat Kokoro as an **optional provider**, not a hard-coded dependency. A provider-neutral voice synthesis contract should accept script/dialogue identifiers, text, language, voice profile, speaking rate, desired output format and generation metadata, and return an audio artifact with provenance, timestamps and reproducibility metadata.

Keep character voice identity in production data: character ID, language/accent, selected provider and voice, pronunciation preferences, approved reference outputs, and versioned parameters. Changing providers must not silently change an approved character voice.

Voice generation should integrate with shot/scene dialogue, asset tracking, editorial timeline, storage budgets, and the existing toolbelt/orchestration conventions. Avoid treating TTS as a substitute for acting direction or audio post-production.

## Evaluation checklist

1. Verify upstream setup, runtime requirements, CPU/GPU performance, offline operation, model and voice licenses.
2. Test Brazilian Portuguese pronunciation, names, punctuation, long-form stability and multiple voice profiles; compare other target languages.
3. Measure latency, throughput, peak memory, artifact size, output sample rate and quality under Cine Toaster deployment environments.
4. Check whether expressive/emotional control, consistent character delivery and fine-grained timing are available; do not assume they are.
5. Assess downstream alignment, phoneme/word timing, lip-sync, dialogue editing and dubbing; these likely require separate tools.
6. Prototype a provider-neutral adapter with provenance and repeatability tests before promoting Kokoro to supported status.

## Acceptance criteria for a future implementation

- An end-to-end sample generates and registers a dialogue artifact from a scene/character specification.
- Model/voice versions, language, settings and license information are traceable.
- Character voice settings persist across scenes; regeneration does not overwrite approved takes.
- Timing and pronunciation limitations are documented, and provider substitution is possible.
- No claim of production-ready acting, voice cloning or lip-sync without dedicated validation.

## Architectural note

Voice production is a broader capability than TTS: speech synthesis, voice casting/identity, performance direction, localization, alignment/lip-sync and audio finishing should remain separable responsibilities.

This document records a research direction, **not** a decision to adopt Kokoro or a claim that Cine Toaster already supports it.
