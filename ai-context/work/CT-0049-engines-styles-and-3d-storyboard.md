---
id: CT-0049
title: Unreal/Unity support, a catalog of directors and styles, and 3D storyboards (later)
type: work
status: proposed
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
