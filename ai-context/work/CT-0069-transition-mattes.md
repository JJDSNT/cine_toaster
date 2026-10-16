---
id: CT-0069
title: Joins shaped by a picture -- mattes and overlays in the transition contract
type: work
status: done
owner: unassigned
created_at: 2026-10-14
updated_at: 2026-10-15
tags:
  - transitions
  - compositing
  - demos
---

# What

Point D3 of the demos line: `SPEC-0011`. A join between two playing pictures
shaped by a third (the matte), and carrying a fourth (an overlay with alpha).

# Why

The Toaster's organic wipes were joins shaped by a picture; every shape a
Cine Toaster transition could draw was a formula in a shader. The user, on
the organic trial: what matters is matte support and layers (2026-10-14).

# Done

- `SPEC-0011` written (accepted on the user's go-ahead for D3).
- **Catalog**: an item may name pictures in `[inputs]`; each `sampler2D` a
  shader declares must have one, else it is refused as before. A new kind,
  `matte`, has no shader. Three items: `matte-wipe` (the join gives the
  matte), `luma` and `displacement` (gl-transitions shaders, until now left
  out) with textures of our own, generated, CC0.
- **On the join**: `matte`, `overlay`, `blend`, `softness`, on a shot's
  `transition` and on a scene's `enter`.
- **Rendering** (`mattes.py`, the assembly): a still matte is an order with a
  soft edge; a moving matte is retimed to the join and completed to white
  over its last tenth; both pictures keep playing. An overlay with alpha is
  laid over the join (`normal`, `screen`, `add`); one without alpha is not
  laid, and said. GL binds a shader's textures after the two pictures; without
  GL, `luma` is drawn by the matte renderer from the same texture.
- **Checks**: `transition_input_missing`, `transition_input_outside` (errors),
  under the practice `a-join-can-be-shaped-by-a-picture`. A matte that does
  not start black or end white, or is retimed, is said in the version's notes.
- **The preview** in the Transitions room binds an item's textures (stills,
  and clips updated every frame) and previews a `matte` item with a sample
  matte of soft blobs; checked in headless Chromium: the three items draw, no
  shader error. (Since CT-0072 a `matte` item's preview is a clip drawn by
  the matte join's graph; the browser no longer holds the rule.)
- **ADR 0022**, from the user's direction, amended twice and accepted
  (2026-10-14), consolidated into one text: luma, matte, warp and
  wipe are compositing primitives shared by every renderer, not effects; the
  catalogs are to be built on them. `luma` and `matte-wipe` are filed as
  wipes and `displacement` as a warp accordingly (it had been filed beside
  `luma` as "organic", which mixed a reveal with a deformation).
- `toast build` refused a matte join with a reason (it drew cards only) and
  passed textures to its shaders. (Removed in CT-0072.)

# To do (solvable; also in the roadmap)

- **A moving texture for a shader** (a `glsl` item reading a clip, not a
  still): the GL renderer binds stills only; moving mattes go through the
  matte renderer.
- **Generated mattes** (`matte: {effect: ...}` from the VFX catalog) are in
  the specification but not built; the splash in the trial was rendered by
  hand and cropped into a production file.
- `transition_overlay_without_alpha` and `transition_matte_incomplete` are
  notes at assembly, not checks at load: they need ffprobe, which loading
  does not run. The specification says checks; amend it or add a cached probe.
- A per-join `softness` for a glsl item (the shader has its own edge).

# Where the plan went (2026-10-14)

The remaining work of this line is ordered in
`development/compositing-roadmap.md` (C1-C10), built on ADR 0022's
primitives: signal, matte, merge, warp, colour, filter, time, generate,
fed by track and animate.

# Decisions

- **Two places for a picture**: the item (a shader with its texture) and the
  join (a production's own matte over a generic wipe). Both happen.
- **A moving matte is completed, not refused**: a matte that stops short
  would leave both pictures on screen at the cut; it is finished to white and
  said, since the editor may have meant its shape and not its ending.
- **The FFmpeg path is the reference**: it runs everywhere; GL is checked
  against it (`luma` by both, within 24 levels at four points).

# Validation

- `tests/test_mattes.py` (9): the three items and their pictures; a still
  matte as an order (left before right); a moving bar matte that stops at
  half, completed and said; an overlay seen only during the join, and one
  without alpha refused; `luma` reads its texture on GL; without GL it is drawn
  by the matte renderer; both give the same join; the input checks.
- `tests/test_transitions.py`, `tests/test_build.py` updated.
- For real: the organic trial's join into the engine vapour now goes through
  a splash (a Blender fluid simulation rendered from the VFX catalog, cropped
  into `mattes/splash.mp4` in the production) and the join into the Sun through
  `luma`, assembled by the tool as `SC-020 v2` (42.3 s). The version's notes
  said the splash was retimed, did not start black, and was completed.
- Full suite: 642 tests pass (2026-10-14); after it, only the three items' categories changed, and their tests pass.

**Closed (2026-10-15).** SPEC-0011's first part is done; what it left is in the compositing roadmap (C10 and its paths of evolution), as the list above says.
