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

Three things follow and every step below respects them:

1. **A composite is a production record.** A shot's layers and a join's recipe
   live in the breakdown as data (the filesystem is authoritative); a
   renderer turns the record into pictures and can be replaced.
2. **One definition per operation.** Luma is computed in one place per
   renderer; a luma key, a luma matte and a luma wipe call it.
3. **Renderers are judged by primitive.** A capability matrix says what each
   one implements; a recipe runs on any renderer that has its primitives, and
   the FFmpeg form is the reference others are tested against.

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

- What: each primitive's parameters, units and identity; the composite record
  (a small graph: sources, operations, the order of layers); how a renderer
  declares what it implements; how a recipe declares what it needs.
- Accept ADR 0022 first (the user).
- Done when: the specification is accepted, and every existing transition,
  VFX item and title can be written as a recipe of its primitives on paper.

### C2. The reference renderer and the record

- What: a `compositing` package with the FFmpeg form of each primitive; the
  composite record read from the breakdown; `mattes.py`, the VFX catalog's
  keying and laying, and the overlay moved onto it. A capability matrix in
  `toast doctor`.
- Done when: the existing joins, effects and titles render through it with
  their tests unchanged, and luma is computed in one place.
- Limits: frame-by-frame FFmpeg is slow for long composites; acceptable for
  the reference, addressed in C9.

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

### C5. Transitions as recipes, and the warp wipe

- What: the transition catalog filed by family (dissolve, wipe -- geometric,
  luma, custom --, warp, warp wipe, move); a join may warp each picture as it
  is revealed (the **warp wipe** the user asked for); mattes generated from a
  generator or a VFX recipe, cached; shaders that read moving textures.
- Done when: a warp wipe -- the outgoing picture bending along a map while the
  incoming one is revealed through a luma matte -- runs the same in the
  preview, on GL and in FFmpeg; no transition reimplements luma or a merge.

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

### C9. Real time, streams, and renderer parity

- What: the measurement of the old D5 (sources at once, real time on this
  GPU, a stream as a source, switching while playing); a GL renderer for the
  composite graph, so the preview and a live output are the same program;
  ComfyUI and Blender as renderers where they hold primitives the others do
  not; tests that a recipe gives the same pictures on each renderer within a
  tolerance.
- Done when: the numbers are written down, and what can run live does, in the
  preview, from the same records.

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
C9 measures beside any step; it builds after C2.
C10 is taken in the gaps.
D8 (the music piece) after C5; D9 (the reel) after C6.
```

C1 and C2 are the foundation and come first even though they show nothing
new: everything after them is cheaper because of them. C3 and C4 give the
ADO; C5 gives the warp wipe; C6 cleans the catalogs; C7 and C8 give the
techniques the user listed (matte to isolate a window, luma key, alpha matte
for Blender renders).
