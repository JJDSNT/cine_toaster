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

[[claims]]
id = "request-body-limit"
claim = "RunPod refuses a /run request body over 10 MiB (400, 'exceeded max body size'); three full-size PNG masters as base64 exceeded it."
status = "measured"
measured_on = "2026-10-18"
evidence = ["Demo 01 SC-040 P2, a bridge with a start, a frame-zero guide and an end guide"]
impact = "high"
workaround = "Pictures travel as JPEG at most 1920 px (providers/ltx.py PICTURE_EDGE); the workflow resizes to 1280x720 anyway."

[[claims]]
id = "zero-max-workers"
claim = "An endpoint scaled to 0..0 workers takes no job at all; scaling it to 0 to stop spending survives across productions."
status = "measured"
measured_on = "2026-10-18"
evidence = ["Demo 01: ltx25-i2v found at max 0 after SINGULAR"]
impact = "high"
workaround = "Read `toast recipes --health ltx-2-5` before a batch; set max workers to at least 1 (min 0 keeps it free when idle), and back after."

[[claims]]
id = "isolated-clips-slideshow"
claim = "Shots generated one by one from still masters read as a slideshow: each starts and ends still, and every cut jumps between unrelated motions."
status = "measured"
measured_on = "2026-10-18"
evidence = ["Demo 01 v1-v3 (23 clips)"]
impact = "high"
workaround = "Generate each scene as one block of up to 20 s, with written camera and action per shot."

[[claims]]
id = "fixed-setting-runs-in-place"
claim = "Told 'the setting stays exactly as in the first frame', a running figure runs in place like on a treadmill."
status = "measured"
measured_on = "2026-10-18"
evidence = ["Demo 01 SC-020 v1"]
impact = "high"
workaround = "For a shot that travels, say the camera moves with the action (holds: moving)."

[[claims]]
id = "guides-at-continuation-dissolve"
claim = "A master picture as a guide at a cut inside a continuous action makes the model dissolve from one pose to the next instead of animating between them."
status = "measured"
measured_on = "2026-10-18"
evidence = ["Demo 01 SC-010 blocks 2-4"]
impact = "high"
workaround = "A continuation cut has no guide (guide_at_cut: false); the first frame and the prompt carry the motion."

[[claims]]
id = "end-on-other-picture-exits"
claim = "Guiding a clip's last frame with a picture whose subject stands elsewhere makes the model take the subject out of the frame and bring it back."
status = "measured"
measured_on = "2026-10-18"
evidence = ["Demo 01 bridges SC-020/030/040, SC-010 block 1-2"]
impact = "high"
workaround = "Chain instead: start the next scene on this scene's last frame (clips.chain_entries)."

[[claims]]
id = "chain-across-scenes"
claim = "A scene started on the previous scene's last frame, guided to its own first picture two seconds in, continues the motion across the cut and changes style inside it."
status = "measured"
measured_on = "2026-10-18"
evidence = ["Demo 01 SC-010 to SC-030"]
impact = "high"
workaround = "clips.chain_entries; the frame is the last one the cut keeps, after its trim."

[[claims]]
id = "open-style-change-mush"
claim = "A change between distant drawing styles in the open reads as a double exposure, not a transformation."
status = "measured"
measured_on = "2026-10-18"
evidence = ["Demo 01 bridges"]
impact = "medium"
workaround = "Hide it: end the scene behind an occluder or a white-out (trunk, leaves, spray, mist, sun glare) and start the next from that frame."

[[claims]]
id = "whiteout-overrun"
claim = "After a white-out peaks, the model keeps inventing: a crystal tunnel, a sketch; and a long block's last seconds can drift to a pencil sketch."
status = "measured"
measured_on = "2026-10-18"
evidence = ["Demo 01 SC-040, SC-050, SC-070 (blocks 1)"]
impact = "medium"
workaround = "Measure brightness and saturation per frame and trim at the peak (trim: {tail}); the chain then starts from the kept frame."

[[claims]]
id = "drawn-iris-not-continuous"
claim = "An iris drawn into each master is interpolated between their sizes: it opens, closes and reopens."
status = "measured"
measured_on = "2026-10-18"
evidence = ["Demo 01 SC-010 block 1"]
impact = "medium"
workaround = "Masters full-frame; the iris is a montage reveal over the whole scene (reveal: {kind: iris})."
+++

LTX 2.5 makes picture, speech and sound together from a starting image and a
prompt. What it does well -- mouths, voices, a room that holds across cuts in
one generation -- makes it the production engine of SINGULAR. What it does
not obey is listed above with the date it was measured, so each claim can be
re-tested when the model changes instead of turning into folklore.

Cost, measured on 2026-09-17 on an L40S at US$ 1.75/h: a 10 s clip at
1280×704 took about 64 s, roughly US$ 0.03. The first call of a session paid a
cold start of about 20 minutes (US$ 0.60).
