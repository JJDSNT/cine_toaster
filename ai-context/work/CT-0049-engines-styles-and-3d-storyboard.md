---
id: CT-0049
title: Unreal/Unity support, a catalog of directors and styles, and 3D storyboards (later)
type: work
status: doing
owner: unassigned
created_at: 2026-10-03
updated_at: 2026-10-03
tags:
  - unreal
  - unity
  - style
  - storyboard
  - 3d
  - future
---

# What

Noted at the user's request (2026-10-03), to take up later.

## 1. Unreal Engine and Unity support

Beyond the study in CT-0047, actual support: each engine as a **render
adapter**, like the generation providers.

- The bridge exists: `toast usd export` writes a scene's plan (room, set
  pieces, moving subjects, one camera per shot with lens and move) as a
  USD stage, checked in Blender.
- Unreal: import the stage (USD Stage), build a Level Sequence from the
  shot cameras, render through Movie Render Queue from the command line
  (Python executor), multi-pass EXR back as takes with lineage.
- Unity: import the stage (USD package), a Timeline with Cinemachine
  cameras per shot, render through the Recorder from the command line in
  the Editor.
- Both need a GPU machine (Windows or a Linux build); likely a remote one
  (RunPod) under the budget ceiling. First spike: Unreal on a RunPod Linux
  image rendering the demo's SC-030 from its USD.

## 2. A catalog of directors and styles

A catalog like the others (`style_assets/<id>/style.toml`, layered): a
director's or a movement's visual language described in our own words —
framing habits, lens and camera-move preferences, colour and light,
editing rhythm, performance register — with what each means for Cine
Toaster's own vocabularies: preferred camera moves (CT-0027), cut types
(SPEC-0007), looks (OCIO, CT-0047), titles, emotion intensity (CT-0048).
A scene or a production names a style; the brief, the generation prompt
and the checks (an advice when a shot departs from it) read it. Entries
describe styles, never imitate a person's work or claim endorsement;
references by link (films, stills, interviews).

## 3. 3D in the storyboard (reference: ScreenWeaver)

ScreenWeaver (screenweaver.ai) runs screenplay → shot breakdown →
storyboard → video in one workflow, with manual control of each shot
(frame, angle, movement, duration), one-click generative previs,
character and location continuity, and a "Storyboard to 3D" path where
"boards become a rendered 3D scene: same characters, same shots" (its
video features in beta, full availability announced for 2026-10-08; the
site does not detail the 3D mechanics).

What Cine Toaster already has toward this: the blocking frame (computed
from the plan, CT-0025), set pieces and objects, the USD export, camera
moves with previews, Blender renders. What a 3D storyboard would add:

- a **3D board** per shot rendered from the USD stage in Blender
  (Workbench or EEVEE) with simple character proxies posed by the plan,
  as a storyboard level between the blocking frame and the master picture;
- characters as rigged proxies (later, with the emotion catalog's FACS
  units for faces, CT-0048);
- the 3D board as a **guide for generation** (depth or pose conditioning),
  so the generated picture keeps the plan's geometry;
- editing the 3D board (moving a camera or a subject) writes back to the
  plan as a decision, like cuts and references (CT-0046).

The storyboard fidelity levels of CT-0025 (blocking frame → sketch →
master image) gain a level: blocking frame → **3D board** → master image.

# Done: the 3D storyboard (2026-10-03)

The user's rule: the 3D storyboard fixes composition, not animation;
animation in 3D may exist to validate the screenplay, but never to control
the AI model.

- `board.py` + `_blender/board.py` + `toast board frames|animatic`: the
  scene's USD stage rendered by Blender Workbench (studio light, shadows,
  cavity, outlines, smooth shading). Boards: stills per shot (start, and
  end with `--end`) + a 16-bit depth map from the multilayer EXR's
  `Depth.Z` (Blender 5 picks multilayer with `media_type`). Animatic: the
  scene through each shot's camera, every Nth frame, encoded with FFmpeg
  (SC-030: 26 s, 48 s to draw at 640×360, step 4).
- People are mannequins (body, shoulders, head at the eyes) in an Xform
  with several children, so Blender keeps its animation; no rig, no pose.
- `derive: {from: board}` / `board:end`: a master picture starts from the
  board; a sidecar fingerprint of the plan tells a stale board, said in the
  picture plan's notes.
- Tests: `tests/test_board.py` (boards and depth; derive from a board and
  the stale note; the animatic).
- Boards in the control room (2026-10-03): job kinds `boards` (boards,
  depth, sheet into staging, adopted into `renders/boards/<scene>/`) and
  `board_animatic`; `GET /api/boards?scene=` (`board.listing`: per shot,
  start/end, depth, stale, version); the scene room's blockout gains a 3D
  storyboard bar and shows a selected shot's board beside its blocking
  frames. Checked headless on a demo copy (draw → adopt → P3's board shown,
  "3 · MEDIUM CLOSE-UP · 3D board"); test: the job adopted and listed.

Correction (2026-10-03): a ScreenWeaver post the user shared (Instagram,
2026-10-01) shows what its site did not: a grid of nine grey clay 3D
boards, each labelled with its number and shot size (wide, close-up, POV
wide, insert, medium, low angle), then "the film" generated by Wan 3 from
them -- "the wolf does not appear until shot seven; that decision was made
on" the board. So it goes 3D boards → video, the same direction as here,
not boards → 3D as first written. The gap is the 3D's richness: detailed
characters, creatures and sets (likely a library or image-to-3D), where
Cine Toaster has mannequins and boxes. Next steps from it: a clay look and
labelled contact sheets (cheap); detailed proxies from image-to-3D models
(TRELLIS, Hunyuan3D) on a GPU, per cast member and set piece (later).

# Noted for later: drawn storyboards (manga and other styles) (2026-10-03)

The user's reference: ScreenWeaver "draws a manga storyboard, not just a 3D
blockout" (YouTube, "Screenweaver for Screenwriters", 2026-08-31): from a
scene's text and a shot (SHOT 04 · STATIC), a pencil manga panel of the
character -- line art, speed lines, expression -- beside the final anime
frame. A second post (LinkedIn, 2026-09-02) shows a clay 3D board (SHOT 01 ·
PUSH IN) and the final image keeping exactly its framing.

What it means for Cine Toaster, as the user put it: handling the storyboard
well seems good for the final result.

- A **drawn board** level: a style applied to
  the 3D board -- the board fixes composition, the drawing gives
  expression and gesture the mannequins cannot -- through an image model
  conditioned on the board's depth or edges, or a line-art pass over the
  render. Styles would come from the style catalog (section 2). The user
  named manga because the reference was an anime; the variations worth
  testing, to compare the results each gives the final film: manga/anime
  line art, cel-shaded anime, classic pencil storyboard (live action), ink,
  comic, watercolour, charcoal.
- The **framing kept from board to film**: the master picture's edit
  already asks to keep the source's geometry and the edge score measures
  it; that measure should also compare the final frame with the board.

# Done: clay look, labelled sheets, one scale of framing (2026-10-03)

- Boards default to grey clay (`--look colour` keeps the plan's colours).
- `toast board sheet`: the scene's boards on one labelled grid.
- The user asked for consistent framing: one scale (extreme close-up …
  extreme wide) measured the same way for every shot (the followed
  subject's share of the frame's height on its blocking frame); kinds two
  shot and over shoulder measured, insert and pov declared (`framing:`);
  a declared `size` (aliases cu, mcu, ws...) checked: `shot_size_unknown`
  (warning), `shot_size_mismatch` (advice, more than a step away). `size`
  and `framing` became core shot fields -- and `title` and `effects`, which
  had been reported as undeclared fields when used.
- Tests: `SizeTests` (measured sizes, label, aliases, both findings) and a
  sheet test.

# Done: the style catalog (2026-10-03)

The user's reminder: a style is not only direction -- animation
techniques, viral videos, adverts too. Ghibli was named as a well-known
example of a possible style, not as a conversion feature. Guide:
`docs/styles.md`.

- `styles.py`, `style_assets/<id>/style.toml` (layered: built in,
  `CINE_TOASTER_STYLES_PATH`, the production's `styles/`); 28 entries in six
  kinds: movement, approach, genre, manner, animation (stop-motion,
  hand-drawn 2D, 3D feature, cut-out, rotoscope, pixel art, painterly,
  pastoral anime), format (viral vertical, commercial spot, music video,
  trailer, explainer, interview documentary).
- An entry: framing, lens, moves preferred/avoided, shot lengths, cuts and
  transitions preferred/avoided, performance register and ceiling, colour,
  sound, titles, `prompt` (words of craft), `format` (aspect, total length,
  hook, captions, end card, frame rate), `inspired_by` (for people only).
- `style:` in `project.yaml`, overridden per scene (`scene["style"]` with
  its level). It reaches the video prompt ("Style: …"), the derived
  picture ("Render the whole image as …", `derive.style: false` to keep
  the source's look), the brief (`STYLE`), the emotions' default intensity;
  `style_unknown` (error), `style_departure` (advice: move, cut,
  transition, shot length, emotion ceiling, the format's hook and length).
- `toast style list|show`, `/api/styles`, the Styles room (the
  production's own marked), MCP `list_styles`.

Validation: `tests/test_styles.py` (all kinds; every id an entry names
exists; no filmmaker or studio name in a prompt; formats' rules; the
nearest style wins; departures as advice; the emotion register and
ceiling; prompt and brief); the room checked headless (28 cards, the
production's style marked, no page errors).

Names people recognise (the user, 2026-10-03: the name is what makes a
style recognisable): entries carry `aka` ("Ghibli", "Wes Anderson",
"Kubrick", "TikTok", "advert"...), shown in the catalog and accepted by
`style:` (`styles.lookup`); several names read "(Ghibli-like)". The prompt
still describes the traits rather than a name.

Reference only, not implemented (the user): Midlibrary's guide to
animation styles in Midjourney,
https://midlibrary.io/midguide/animation-in-midjourney-ai -- a survey of
animation styles and how to word them for an image model.

Remains: applying a format's aspect and frame rate to generation and the
assembly; captions and end cards from the format; a sequence-level style;
Unreal/Unity adapters (section 1).
