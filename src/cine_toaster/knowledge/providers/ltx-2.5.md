+++
id = "ltx-2.5"
title = "LTX 2.5 — image to video, with speech"
kind = "image-to-video"
version = "2.5 (distilled, int8)"
measured_with = "SINGULAR, endpoint ltx25-i2v on an L40S, 17–21 Sep 2026 (singular/docs/SINGULAR-PROXIMOS-PASSOS.md and ferramentas/cena_ltx.py)"

[[claims]]
id = "speech-and-lips"
claim = "Speech and lip sync are very good; automatic transcription matches the scripted lines."
status = "measured"
measured_on = "2026-09-17"
evidence = ["SINGULAR 3-01 (v12)"]
impact = "low"

[[claims]]
id = "reads-direction-aloud"
claim = "When the acting direction also describes the speech, the model reads the direction aloud (9 of 57 clips of 1-02)."
status = "measured"
measured_on = "2026-09-18"
evidence = ["SINGULAR 1-02, 9/57 clips"]
impact = "high"
workaround = "Name the speech verb once ('says'); a line's delivery carries only the manner, never another speech verb."

[[claims]]
id = "offscreen-line-goes-to-visible-mouth"
claim = "A line asked for off screen comes out of the mouth of whoever is in frame."
status = "measured"
measured_on = "2026-09-17"
evidence = ["SINGULAR 3-01 tests"]
impact = "high"
workaround = "Off-screen and voice-over lines are added in the mix (`mix: true`), not asked of the model."

[[claims]]
id = "several-speakers-in-one-clip"
claim = "Two or three speakers in frame keep the right mouths and order when each line names its speaker and later lines start with 'Then'."
status = "measured"
measured_on = "2026-09-18"
evidence = ["SINGULAR 1-02A opening, 1-02C promise: six lines, right voices and mouths"]
impact = "medium"
workaround = "Dialogue can be covered like a shoot: a two-shot master plus closes."

[[claims]]
id = "prompt-must-match-first-frame"
claim = "The text may describe only what is in the starting image, plus movement; if it contradicts the image, the model changes the scene to obey the text."
status = "measured"
measured_on = "2026-09-17"
evidence = ["SINGULAR 3-01 tests"]
impact = "high"

[[claims]]
id = "no-point-of-view"
claim = "The model does not hold a point of view: it puts the viewing character into the frame."
status = "measured"
measured_on = "2026-09-17"
evidence = ["SINGULAR 3-01 tests"]
impact = "medium"
workaround = "Describe only what is seen; subjective views are built in the montage."

[[claims]]
id = "defocus-reinvents"
claim = "A requested defocus or refocus reinvents the face and the setting when focus returns."
status = "measured"
measured_on = "2026-09-17"
evidence = ["SINGULAR 3-01 tests"]
impact = "medium"
workaround = "Focus effects are done in the montage."

[[claims]]
id = "action-order"
claim = "The order of actions in the prompt is not always obeyed (a line meant for the start came at the end)."
status = "measured"
measured_on = "2026-09-17"
evidence = ["SINGULAR 3-01 plan 8"]
impact = "medium"
workaround = "Cut around the speech that was actually spoken; mute the wrong stretch in the montage."

[[claims]]
id = "still-opening"
claim = "A clip opens on its still first image for about 0.35 s before moving."
status = "measured"
measured_on = "2026-09-17"
evidence = ["SINGULAR montage rule (cena_ltx.py INICIO_MIN)"]
impact = "low"
workaround = "The assembly skips the opening, except in continuations (CT-0039)."

[[claims]]
id = "multishot-own-rhythm"
claim = "In a multi-shot generation the model cuts at its own rhythm, sometimes with an extra cut: asked for 144 and 264, it cut at 91, 190 and 283."
status = "measured"
measured_on = "2026-09-20"
evidence = ["SINGULAR 1-02A block 1 (shots 8, 9, 10)"]
impact = "high"
workaround = "Slice a block by content against each shot's reference picture, never by the requested times (CT-0037)."

[[claims]]
id = "frame-zero-guide"
claim = "In a long block the first-frame image alone gives way: the first frame drifted to another person unless the first image is also a guide at frame 0."
status = "measured"
measured_on = "2026-09-20"
evidence = ["SINGULAR 1-03, a 17 s block"]
impact = "high"
workaround = "Always guide frame 0 with the first shot's image, and each later shot's master image at its cut."

[[claims]]
id = "keyframe-guides"
claim = "Keyframe guides work, including a final-frame guide (-1); guide frames must be -1 or multiples of 8 (the VAE packs eight frames per latent)."
status = "measured"
measured_on = "2026-09-18"
evidence = ["SINGULAR 1-04 v4, one-take test ending on shot 2's master image"]
impact = "medium"

[[claims]]
id = "last-frame-chaining"
claim = "A second stretch generated from the last frame of the first joins invisibly, but the face drifts a little in each stretch."
status = "measured"
measured_on = "2026-09-18"
evidence = ["singular/cenas/1-04/ltx/teste-plano-sequencia/"]
impact = "medium"
workaround = "Declare the join as a continuation with chain: frame; guide the end of a stretch with the next master image."

[[claims]]
id = "duration-limits"
claim = "A generation is 1 to 20 seconds, in whole seconds."
status = "measured"
measured_on = "2026-09-20"
evidence = ["SINGULAR cena_ltx.py produzir_bloco"]
impact = "medium"

[[claims]]
id = "identity-lora-voice"
claim = "The LTX 2.3 identity LoRA with reference audio runs on 2.5 distilled, keeps the face, but gives no clear voice gain: similarity 0.52→0.59 and 0.67→0.45, within normal clip-to-clip variation (0.45–0.78)."
status = "measured"
measured_on = "2026-09-18"
evidence = ["singular/cenas/1-03/ltx/teste-id-lora/comparacao-id-lora.mp4"]
impact = "medium"
workaround = "For a consistent voice across clips, convert the take's speech to the cast member's reference voice in the montage (CT-0040)."

[[claims]]
id = "no-smile-instruction"
claim = "'Not smiling' is only partly obeyed."
status = "measured"
measured_on = "2026-09-17"
evidence = ["SINGULAR 1-04"]
impact = "low"
workaround = "Guide with a master image of the face not smiling."
+++

LTX 2.5 makes picture, speech and sound together from a starting image and a
prompt. What it does well -- mouths, voices, a room that holds across cuts in
one generation -- makes it the production engine of SINGULAR. What it does
not obey is listed above with the date it was measured, so each claim can be
re-tested when the model changes instead of turning into folklore.

Cost, measured on 2026-09-17 on an L40S at US$ 1.75/h: a 10 s clip at
1280×704 took about 64 s, roughly US$ 0.03. The first call of a session paid a
cold start of about 20 minutes (US$ 0.60).
