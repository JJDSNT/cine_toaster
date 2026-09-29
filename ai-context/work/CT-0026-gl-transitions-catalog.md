---
id: CT-0026
title: gl-transitions as the transition catalog's shader bank, rendered by its own shaders
type: work
status: done
owner: development agent
created_at: 2026-09-29
updated_at: 2026-09-29
tags:
  - transitions
  - rendering
  - catalog
  - dependencies
---

# What

Add [gl-transitions](https://github.com/gl-transitions/gl-transitions) as a git
submodule and feed the transition catalog from it. Review a first set. Make
`toast build` run a GLSL transition's own shader instead of only its FFmpeg
stand-in.

# Why

The catalog had four built-in items. gl-transitions is the open bank of
transitions in exactly the GLSL contract the catalog already used. Requested by
the user before plan step 3.

# Done

- Submodule `vendor/gl-transitions`, pinned at `902218a` (2026-06-22).
  `make install` initialises it. The wheel force-includes the shaders and the
  LICENSE.
- `transitions.py`:
  - reads every upstream shader as an **unreviewed** item (`curated: false`,
    origin `gl-transitions`, no `[render]`), taking name, author, licence and
    parameters from its header;
  - lets a manifest with `upstream = "gl-transitions:<Name>"` review one,
    replacing the raw item;
  - parses parameters (`uniform <type> <name>; // = <default>`) for every GLSL
    item;
  - leaves out shaders that need a texture or lack a default.
- Six reviewed items: dip-to-black, iris-open, blur-dissolve, clock-wipe,
  pixelate and film-burn, each with guidance and a declared FFmpeg stand-in.
- `shader_render.py`: ModernGL wrapper for the GLSL contract. Each renderer
  claims its own context before drawing.
- `build.py`:
  - `--engine auto|gl|ffmpeg`;
  - with GL, the film is assembled from pieces: each shot's body and one clip
    per join. A shader join renders real frames; other joins use their xfade
    stand-in in the same film;
  - when no shader runs, the old single xfade graph is unchanged.
- `toast doctor`: ModernGL is now wired and checks for a context; a new
  gl-transitions capability; the catalog shows reviewed and unreviewed counts.
- Transitions room: the preview sets the shader's declared parameters and uses
  highp. The unreviewed bank is collapsed and plays on hover (browsers cap live
  WebGL contexts). The detail view shows author, source, parameters and how the
  film renders the item.

# To do

- Review more upstream shaders as productions need them.
- Per-shot parameter overrides (`transition.params`). The renderer already
  accepts and validates overrides; the schema, check and UI do not.
- The two texture shaders (`luma`, `displacement`) need a texture-input
  contract first.
- GL rendering on llvmpipe runs at about 3 fps at 720p for heavy shaders. That
  is acceptable for reels but should be measured on long films.

# Decisions

- The submodule is permitted by ADR 0011: every item is MIT or BSD.
- Unreviewed items are listed and renderable by GL, but never silently given a
  stand-in: the FFmpeg engine refuses them and tells the user to install the
  gpu extra.
- A reviewed manifest inherits licence and author from the shader, so
  attribution cannot drift from the source.
- Hard cuts in the GL path are real cuts; the xfade path keeps its 40 ms fade.

# Validation

- All 125 upstream shaders compiled under ModernGL (GLSL 330 wrapper). All 128
  catalog shaders, including the Amiga project's, compiled in headless
  Chromium WebGL.
- Every catalog shader rendered at progress 0 and 1, ending on the incoming
  frame.
- The Amiga reel was built on both engines: 25.7 s each. Mid-transition frames
  compared: GL shows the real switcher flip and copper bars.
- Headless screenshots of the Transitions room, the reviewed and unreviewed
  banks, and a simulated hover that played and released a preview.
- `tests/test_transitions.py`, `tests/test_shader_render.py`,
  `tests/test_build.py`, `tests/test_doctor.py`, and the full suite: 262 tests
  OK.
