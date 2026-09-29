+++
id = "chatterbox-vc"
title = "Chatterbox voice conversion, with Demucs separation"
kind = "voice-conversion"
version = "chatterbox-tts 0.1.7, demucs 4.1.0 (htdemucs), CPU"
measured_with = "12 of Kael's takes from SINGULAR (1-02, 1-02B, 1-03, 3-01), against elenco/voz_kael_genebra.wav; likeness by Resemblyzer, words by faster-whisper small.en (CT-0040)"

[[claims]]
id = "converges-the-voice"
claim = "Converting a take's speech to the reference raises likeness from 0.67 to 0.82 on average and halves its spread across takes (0.094→0.051); takes resemble each other more too (0.60→0.77)."
status = "measured"
measured_on = "2026-09-29"
evidence = ["singular/cenas/1-02/ltx/teste-conversao-voz/medicoes.json"]
impact = "high"

[[claims]]
id = "keeps-words-and-timing"
claim = "The words survive (recognition error unchanged, 0.051 before and after) and so does the timing: the speech envelope moves 0–10 ms in 11 takes and 50 ms in one, under a frame, so the mouths still match."
status = "measured"
measured_on = "2026-09-29"
evidence = ["singular/cenas/1-02/ltx/teste-conversao-voz/medicoes.json"]
impact = "high"

[[claims]]
id = "drops-the-room"
claim = "Converted directly, the take's room is lost: the output's noise floor is silent. Separating the voice first (htdemucs, two stems), converting only the voice and mixing the rest back keeps the room; likeness after the remix is 0.85 and 0.72 on 1-02 P12 and 3-01 P13."
status = "measured"
measured_on = "2026-09-29"
evidence = ["singular/cenas/1-02/ltx/teste-conversao-voz/comparacao-voz-kael.mp4"]
impact = "high"
workaround = "voice_worker.py always separates first."

[[claims]]
id = "cpu-is-enough"
claim = "About 5 s of CPU per second of speech for the conversion, plus about 13–37 s to separate a take; 3-01 P13 took 64 s end to end on 8 cores. No GPU and no paid service."
status = "measured"
measured_on = "2026-09-29"
evidence = ["CT-0040 spike"]
impact = "medium"

[[claims]]
id = "weak-voice-gains-level"
claim = "A weak, quiet delivery (3-01 P13, −26 LUFS) comes back at ordinary level (−16 LUFS) when converted alone; the remix restores the separated voice's level, but whether the weakness itself survives is for a listener to judge."
status = "measured"
measured_on = "2026-09-29"
evidence = ["singular/cenas/1-02/ltx/teste-conversao-voz/comparacao-voz-kael.mp4"]
impact = "medium"

[[claims]]
id = "watermarked"
claim = "Every output carries Resemble's Perth watermark, inaudible, applied by the engine."
status = "unmeasured"
measured_on = "2026-09-29"
evidence = ["chatterbox/vc.py: PerthImplicitWatermarker"]
impact = "low"

[[claims]]
id = "one-voice-per-take"
claim = "Conversion turns every voice in the audio into the reference; a take with two speakers cannot be converted as a whole."
status = "unmeasured"
measured_on = "2026-09-29"
evidence = ["how speech-to-speech conversion works"]
impact = "medium"
workaround = "toast revoice refuses a take with more than one speaker; converting per speaker needs diarization."
+++

A take's speech converted to the cast member's own recording, the room kept.
It answers `ltx-2.5`'s `identity-lora-voice`: the model's voice drifts from
clip to clip, and conversion in the montage holds it. Engines are permissive
(MIT and Apache-2.0) and run in `.venv-voice`, apart from the main
environment, because they pin their own numpy and torch.
