---
id: CT-0076
title: C5 -- the transition catalog as recipes of primitives
type: work
status: done
owner: unassigned
created_at: 2026-10-14
updated_at: 2026-10-14
tags:
  - compositing
  - transitions
---

# What

Step C5 of `development/compositing-roadmap.md`, chosen by the agent when the
user left the next step to its judgement (2026-10-14). Started inside C2
(CT-0071: recipes, `warp.surface`, three warp wipes). Done when: a warp wipe
runs the same in the reference, on GL and in the preview, and no transition
reimplements luma, a merge or a surface.

# Done

- **Nine reviewed shaders became recipes**, as Appendix B of SPEC-0012
  wrote them: `cross-dissolve`, `dip-to-black`, `blur-dissolve`,
  `iris-open`, `clock-wipe`, `diamond-wipe`, `luma`, `displacement`,
  `switcher-flip` (two `warp.transform` folds over black, shaded). Their
  FFmpeg stand-ins went with them (P4 of CT-0072, for these items); their
  local `.glsl` files are deleted. A recipe replacing an upstream shader
  keeps its name in `upstream` so the raw shader is not listed beside it,
  and reads none of it (`transitions._load_manifest`).
- **Primitives for them**: gradient kinds `circle`, `diamond`, `conic` (both
  renderers; the iris is round whatever the frame); `warp.displace` on GL.
  Every recipe in the catalog is now drawn by GL -- `displace-wipe` used to
  fall back to the reference.
- **Filed by family**: dissolve, wipe/geometric, wipe/luma, wipe/custom,
  warp, warp-wipe, move, stylised (the ADR's "category becomes a family").
- **Previews from the graphs** for every recipe, drawn by
  `transitions.render_preview` on sample pictures that now carry detail
  (lines, rings), so a blur or a warp can be seen; a recipe's own pictures
  (a luma, a map) are read.
- **Generated mattes** on a join: `matte: {gradient: {...}}` or `{noise:
  {...}}`, a node of the matte join's graph, read by its values; checked when
  the scene loads (`transition_matte_invalid`, under the practice
  `a-join-can-be-shaped-by-a-picture`).
- **A shader reads a moving texture** frame by frame: already true since
  CT-0072's B1 (a texture is a port of the graph); now tested.
- **Two shaders stay**, each saying why (`opaque_reason`): `pixelate` (no
  mosaic primitive) and `film-burn` (a procedural look of its own).
- On a real production: SC-020 Heat v6 assembled with its `luma` join as a
  recipe; no join fell back to a straight cut. (v6 was made while the recipe
  had a soft edge of 0.05; it was then set back to the shader's hard edge,
  which SPEC-0012's example and the luma conformance test hold.)

# Remaining (in the compositing roadmap)

- `filter.mosaic`, so `pixelate` becomes a recipe.
- A sheet for `film-burn`, or keeping it as a shader for good.
- Generated mattes from a VFX recipe (a Blender element), with C6.
- The 117 unreviewed gl-transitions shaders stay opaque until a sheet
  re-expresses one.

# Decisions

- **Recipes mix in linear light**, as ADR 0022's colour contract says; the
  old shaders mixed in the display encoding. A dissolve's middle is brighter
  than it was. No production of the user's (SINGULAR) uses these items; the
  demos do.
- **The DVE flip is two folds**, not a rotation in depth: the shader folded
  the picture to an edge and unfolded the next; kept, as a transform's scale.
- **A generated matte is read by its values** (`signal.luminance`); a file's
  grey is read as it is shown (`signal.luma`), so a mid-grey painted in a
  file is the middle of the order.

# Validation

- `tests/test_recipes.py`: no reviewed item reimplements the primitives (a
  shader only with a reason); a recipe needs no stand-in and has a preview;
  a replaced shader is not listed; every recipe runs on GL as the reference
  draws it; a dissolve mixes in linear light; a dip holds black; the iris is
  round; the clock sweeps clockwise from twelve; the diamond opens from the
  centre; the flip folds to its right edge; a generated matte is a node of
  the join and a bad one is a finding; a shader reads a moving texture.
- `tests/test_mattes.py`, `tests/test_transitions.py`, `tests/test_joins.py`
  and `tests/test_graph_transitions.py` updated: the luma join through its
  recipe; a remaining shader (or the test's own) as the example of a shader;
  `dip-to-black` resolved to a graph; `displace-wipe` filed as wipe/custom.
- Gradients identical on GL and the reference; `warp.displace` identical
  with `extend` and `mirror`, within 0.0035 on average with `transparent`.
- Full suite: 747 tests pass (2026-10-14).
