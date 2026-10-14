---
id: CTX-COMPOSITING-ROADMAP
title: Compositing roadmap
type: roadmap
status: active
owner: project
created_at: 2026-10-14
updated_at: 2026-10-14
tags:
  - compositing
  - transitions
  - vfx
  - demos
---

# Compositing roadmap

The plan that turns Cine Toaster's transitions, effects and titles into one
compositing engine built on primitives (ADR 0022). It replaces points D3b-D7
of the demos line in `roadmap.md`, which now points here. The demos (D8 the
music piece, D9 the reel) are its validation.

The user's rules for this line (2026-10-14): every gap found is attacked;
every solvable limitation is written down here; nothing of the old reel is
kept; the Video Toaster and the ADO are models of what to reach, never limits
to copy.

## The architecture in one page

```text
            signals          track           animate
         (luma, alpha,   (point, plane,   (keyframes, easing,
          depth, hue..)      camera)       beats, tracks)
                \               |               /
                 v              v              v
  generate --> [ matte ]  [ warp ]  [ colour ]  [ filter ]  [ time ] --> merge
                  \___________ primitives, defined once ___________/
                                       |
        implemented by each renderer: FFmpeg (reference), GL (preview,
        real time), Blender (3D, its compositor), ComfyUI/models (depth,
        segmentation, inpainting), Natron (OFX) -- each says which it has
                                       |
           recipes in the catalogs: transitions (wipe, luma wipe, warp,
           warp wipe, DVE move, dissolve), effects, keys, titles
                                       |
      used in a shot as a composite: layers (picture + warp + matte + merge),
      and between shots as a join; recorded in the breakdown, never in code
```

After an outside review (ADR 0022's second amendment), five more things
hold from the first step: the composite is a **typed graph**; there is a
**colour contract** (working space, alpha, precision, luma's weights);
execution is **split across renderers** by a planner; every node has an
**identity** that makes caching and invalidation exact, and expensive results
are promoted to production records; and **conformance** between renderers is
tested continuously, across sizes, rates, bit depths and alpha.

Three things follow and every step below respects them:

1. **A composite is a production record.** A shot's layers and a join's recipe
   live in the breakdown as data (the filesystem is authoritative); a
   renderer turns the record into pictures and can be replaced.
2. **One definition per operation.** Luma is computed in one place per
   renderer; a luma key, a luma matte and a luma wipe call it.
3. **Renderers are judged by primitive.** A capability matrix says what each
   one implements; a recipe runs on any renderer that has its primitives, and
   the NumPy reference (float, linear, premultiplied, with OCIO) defines the
   right result and every renderer -- FFmpeg included -- is tested against it.

## Where things stand (2026-10-14)

- Signal: luma only, inside `mattes.py` and the `luma` shader.
- Matte: still and moving mattes for joins (SPEC-0011); VFX elements keyed on
  green; no matte operations.
- Merge: an overlay on a join (normal, screen, add); VFX elements laid over a
  shot; no Porter-Duff set.
- Warp: only inside transition shaders (cube, doorway, displacement...);
  nothing on a shot.
- Colour: looks (OCIO, LUTs) and a few VFX items.
- Filter: a few VFX items (blur-like, glow through Natron).
- Time: nothing besides the cut.
- Generate: solids, title cards, Blender effects, the VFX catalog's renders.
- Track: nothing.
- Animate: nothing general; beats (CT-0067) set shot lengths only.

## The steps

Each step gets a work record when it starts and is struck here when done.
"Done when" is the acceptance; "Limits" are the solvable ones known in
advance.

### C1. The primitives specified (SPEC-0012)

Done (`CT-0070`): `ai-context/specs/SPEC-0012-compositing-graph.md`, accepted
2026-10-14, with its operations as data and its examples validated by tests.

- Accept ADR 0022 -- done (2026-10-14, consolidated and accepted).
- What: each primitive's parameters, units and identity; the composite record
  as a **typed graph** (picture, matte, signal, sound, track, curve, metadata
  on its edges; wrong connections refused); the **colour contract** (working
  space scene-linear through OCIO, premultiplied or straight alpha at each
  edge, precision and HDR, luma's weights and transform named by the
  operation -- Rec.709 linear by default -- and luminance told apart from
  luma); **node
  identity** (a hash of operation, parameters, renderer version, inputs) and
  what is cached, what is promoted to a record, what is not deterministic;
  formats for tracks and curves apart from what makes them; how a renderer
  declares what it implements; how a graph is **split across renderers** and
  results handed over.
- Kept distinct: the compositing graph is a record a shot holds, not the
  production canvas nor the orchestration graph (CT-0023).
- Representative graphs written out for the existing operations (every
  transition family, a VFX element, a title, the music piece's joins), to show
  they can be expressed before anything is built (the review's last advice).
- Done when: the specification is accepted, and every existing transition,
  VFX item and title can be written as a recipe of its primitives on paper.

### C2. The reference renderer and the record

Done (`CT-0071`), for its own part: the NumPy reference evaluates 53 of the
55 ops of SPEC-0012 (the other two are recorded, never computed by it), with
node identity, a cache and memory bounded by the graph, not the length; shot
composites and recipe joins are assembled; matte joins and overlays are
graphs too, so luma is computed in one place; a GL renderer of the same
graphs (26 ops), checked against the reference, draws them about 27 times
faster when it covers them; `toast doctor` reports both. Decided on the way:
GL, not FFmpeg, is the fast renderer, and effects and titles move to the
graph in C6.

- What: the **NumPy reference** of each primitive in the `compositing` package
  (float, linear, premultiplied, OCIO; FFmpeg only to read and write files);
  the composite record read from the breakdown; then FFmpeg as the first
  production renderer of the ops it can do correctly, checked against the
  reference; `mattes.py`, the VFX catalog's keying and laying, and the overlay
  moved onto them. A capability matrix in `toast doctor`.
- The validator's three robustness gaps found by the second outside reading
  (depth cameras and counts in `merge.depth`, opaque nodes' ports, required
  parameters beyond `matte.key`) were closed at the start of this step.
- Done when: the existing joins, effects and titles render through it with
  their tests unchanged, and luma is computed in one place, in the working
  space of the colour contract (today it is FFmpeg's Y in display-encoded
  4:2:0).
- **The conformance suite starts here** and grows with every step: each
  primitive and recipe rendered on every renderer that claims it, compared
  within a tolerance, at several sizes, rates, bit depths and with straight
  and premultiplied alpha.
- A cache by node identity, with selective invalidation.
- A graph is run **whole by one renderer** here; splitting it across several
  is C9. Every later step that asks two renderers to agree (C5's GL and FFmpeg)
  asks it of single-renderer runs, checked by this suite, and does not depend
  on C9.
- Limits: frame-by-frame FFmpeg is slow for long composites; acceptable for
  the reference; the GL renderer of C5 and C9b is the fast path.

### C3. Animate: parameters over time

- What: keyframes with easing for any primitive's parameter; values driven by
  the music's beats (CT-0067) and later by tracks.
- Done when: a warp's scale pulses on every beat of the music piece, written
  in the breakdown.
- Limits: bars (D1b in `roadmap.md`) are needed for "on every bar".

### C4. Layers: the ADO move and the keyers

- What: a shot holds layers, each a source with a warp (place, size, rotation
  in three axes with perspective), a matte and a merge mode, animated (C3).
  Keyers as matte generators: luma, colour, difference. Borders and a drop
  shadow on a layer; a garbage matte drawn as a shape.
- Done when: a playing picture is flown into a corner over another, held and
  flown out with eased keyframes; a person shot on a light background is keyed
  over another picture; the user's "window replaced by a landscape" is made
  with a matte (fixed camera; a moving one needs C7).
- Room left for **2.5D** (ADR 0022 §8): a layer's warp in perspective and a
  depth signal per layer are in the record from here, so layers can later sit
  in a space with a virtual camera, parallax and occlusion without a Blender
  scene. Not built here; not precluded.

### C5. Transitions as recipes, and the warp wipe

Started early, inside C2 (`CT-0071`): transitions of kind `graph`, the
`warp.surface` primitive and three warp wipes (`warp-ball`, `warp-roll`,
`page-turn`) drawn by the reference; GL and the preview's own drawing remain.

- What: the transition catalog filed by family (dissolve, wipe -- geometric,
  luma, custom --, warp, warp wipe, move); the **warp wipe** the user asked
  for: the playing picture mapped onto a 3D object (ball, tube, page, tiles)
  that moves in perspective, revealing the next shot behind it -- as the
  Toaster's and the ADO's warps did (the tape, 12:09-12:22); mattes generated from a
  generator or a VFX recipe, cached; shaders that read moving textures. The
  **GL renderer of the graph** starts here, for the recipes transitions need,
  each run whole on GL and whole on FFmpeg and compared by the C2 suite.
- Done when: a warp wipe -- the outgoing picture wrapped into a ball (or rolled
  into a tube, or turned as a page) that spins and flies away while still
  playing -- runs the same in the reference, on GL and in the preview; no
  transition reimplements luma, a merge or a surface.

### C6. The catalogs re-expressed

- What: VFX items that are a primitive with a parameter (a colour key, a
  luma key, a blur) become presets of the primitive; element effects (fire
  over, smoke over) become layers with an alpha or luma matte; titles become
  generators on layers. Missing items found earlier: a horizontal crawl, a
  drop shadow, title colours from the look, posterise, solarise, colour
  cycling. A sheet for each gl-transitions shader worth using (6 of 117
  have one), and the Toaster-style shaders of `CT-0028`.
- Done when: no operation exists twice across the catalogs, and every item
  says which primitives it uses.

### C6b. Rich typography and animated lettering (intention, recorded 2026-10-14)

Recorded at the user's request during C2, to be investigated after the
primitives are consolidated; not part of C2, and no format, library or API is
prescribed here.

- **Inspiration**: the Amiga's Kara Fonts / Kara Collection -- ColorFonts and
  AnimFonts: decorative lettering, textured and dimensional type, metallic and
  glass-like materials, shadows, bevels, gradients, colour cycling, animated
  letters. **The historical reference, not the functional limit**: modern
  directions to look at include OpenType colour fonts, SVG fonts, procedural
  typography and per-character animation, without assuming all of them are
  built.
- **What the catalog should eventually offer**:
  - font selection: conventional fonts, colour fonts and other suitable
    typography formats;
  - visual styles: materials, textures, gradients, bevels, shadows, outlines,
    glow and other effects;
  - animation presets: scrolling, crawling, rotation, reveals, per-character
    animation and others;
  - composable recipes: text generation with warps, mattes, filters, curves
    and layers;
  - backend flexibility: FFmpeg, Blender and GL where each fits, without
    duplicating what they already do.
- **Principle**: typography is another composable capability of Cine
  Toaster -- recipes of the primitives (`generate.text` and the rest) -- not
  an independent effects engine, and not static images of styled text.
- **Acceptance direction**: each typography entry names the primitives it is
  built from and the renderer capabilities it needs, as every C6 entry does.

### C7. Time and track

- What: retime, speed ramp, freeze, reverse, frame blending, an offset
  between layers, trails and echoes (the ADO's Infinity). Point and planar
  tracking (OpenCV, permissive) whose data drives a warp or a matte.
- Done when: a speed ramp lands on a beat; trails follow a moving layer; a
  replaced window follows a moving camera.

### C8. Signals from models and from 3D

- What: depth and segmentation as signals, from a model run on a picture
  (depth estimation, a segment-anything model) or from Blender passes (Z,
  object index, alpha); the user's "integrate Blender renders into the
  AI-generated picture" with an alpha matte and a depth matte. Through the
  generation and Blender adapters, never in the Project Core. Licences
  checked against ADR 0011.
- Done when: a Blender-rendered object sits behind a person in a generated
  picture, ordered by depth.

### C9. Hybrid execution

- How results made by different mechanisms coexist in one composite (ADR 0022
  §9): each node live, accelerated, precomputed or offline; a subgraph whose
  inputs do not change while playing is rendered ahead and read back by its
  identity; an offline node's result is a production record. Real time (C9b)
  then needs only the live and accelerated parts to meet the deadline -- as
  the Toaster played live what LightWave had rendered beforehand.

- What: a planner that splits a graph across renderers (FFmpeg, GL, Blender,
  ComfyUI or other model runners, OpenCV), runs each part where it can --
  locally or on Runpod as a job with its cost -- and hands results over as
  files in the working space. ComfyUI and Blender join as renderers of the
  primitives they hold.
- Done when: one composite segments a person with a model, renders a set in
  Blender, and merges them in FFmpeg, from one record, with each part's cost
  recorded.

### C9b. Real time and streams

- What: the measurement of the old D5 (sources at once, real time on this
  GPU, a stream as a source, switching while playing); a real-time executor of
  the same graph (ADR 0022 §9), so the preview and a live output are the same
  program as the final render, not a second compositing language:
  - a deadline per frame (41.7 ms at 24 fps, 33.3 at 30, 16.7 at 60), measured;
  - a pool of pre-allocated buffers, no allocation while playing;
  - the GPU for merges, warps, mattes and colour;
  - a playback cache: a window of frames behind and ahead, with prefetch, for
    playing, scrubbing and time operations -- pages kept, not dropped;
  - planning: nodes fused, run in parallel, or precomputed;
  - degradation by policy when a deadline is missed (lower resolution, a
    proxy, the previous frame), never in the final render.
- Done when: the numbers are written down, and what can run live does, in the
  preview, from the same records.

### C11. A compositing view for the filmmaker

- What: layers, mattes, moves and effects shown and edited as a filmmaker
  thinks of them, with the typed graph beneath; agents build and change the
  graph through the same commands. On the React Flow canvas (ADR 0015), kept
  apart from the canvas's entity and step nodes (CT-0023).
- Done when: a layer's move and matte are edited in the interface and the
  breakdown changes, and an agent can do the same through MCP.

### C10. Loose ends kept from the demos line

- `toast check` reports a first shot's `transition` that nothing renders.
- `toast footage fetch` as a job; a changed declaration replaces the take it
  made; more than the first audio track.
- `toast build`: removed, or the assembly of a whole production at its frame.
- `rig`, `remotion`, `hyperframes`: a renderer each, or out of the vocabulary.
- A scene's own frame; a stretch's frame-accurate trim.
- `transition_overlay_without_alpha` and `transition_matte_incomplete` as
  checks at load (a cached probe), not only notes.
- Generated mattes from the VFX catalog are slow (163 s for 3 s of a fluid at
  640x360): render once, small, cached; say so before a cut waits on it.

## Order and dependencies

```text
C1 -> C2 -> C3 -> C4 ----> C5 -> C6
                   \        \
                    -> C7    -> C8
Conformance tests run from C2 onward, in every step.
C9 (hybrid execution) after C2 and before C8; C9b (real time) measures
beside any step and builds after C2. C11 after C4 and C5.
C10 is taken in the gaps.
D8 (the music piece) after C5; D9 (the reel) after C6.
```

C1 and C2 are the foundation and come first even though they show nothing
new: everything after them is cheaper because of them. C3 and C4 give the
ADO; C5 gives the warp wipe; C6 cleans the catalogs; C7 and C8 give the
techniques the user listed (matte to isolate a window, luma key, alpha matte
for Blender renders).
