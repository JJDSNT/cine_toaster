# ADR 0024: Signals are production records -- what they are, where they came from, what was done to them

Status: accepted (2026-10-15, CT-0081, C8 step 1), on the user's direction after the C8 audit.

## Context

C8 brings values per pixel from outside the graph: depth from a renderer's
pass or from a model, segmentation, motion vectors. SPEC-0012 already told a
metric depth (from a named camera) from a monocular model's relative depth,
and refused to merge depths across cameras -- but once a relative depth was
aligned to a scene, it was a `depth` like a Blender Z pass: nothing said that
it was a model's guess, how it was fitted, or how good it was. A result was
also meant to be "recorded" (SPEC-0012 §5) with nowhere to record it.

## Decision

1. **A signal is a resource of the production**, `signals/<id>/`, not a
   node's private result: one depth of a shot serves compositing, tracking,
   effects and tools to come. It belongs to the medium it describes.
2. **Three axes, never mixed**:
   - its **kind** (SPEC-0012's: depth, depth_relative, segmentation,
     vectors, normals, ...) -- what the values are;
   - its **origin** -- `geometric` (a renderer's or a surface's own
     geometry), `estimated` (a model's), `authored` (a person's) -- where the
     values came from; a transformation never changes it, and a signal
     derived from another inherits it: **an estimated depth aligned to a
     scene stays estimated**;
   - its **transformations** -- each a step of its provenance (an
     alignment: method, reference, parameters, residual).
3. **Provenance is a chain** that can be rebuilt: what made each step (a
   renderer, a model, a person: name, version, parameters), from what
   (media and files by content hash, signals by revision and data hash).
4. **Invalidation is explicit**: a signal whose medium, input files or
   parent signals changed -- transitively -- is stale and refused, with the
   reason. Values identical by content change nothing.
5. **Quality is known or unknown, never invented**: the maker's declared
   confidence and errors actually measured (against what, by what metric,
   how) are kept apart; with neither, a signal's quality is `unknown`.
6. **Time and space are part of the contract**: a clock (rate, origin on its
   medium; ADR 0023), its resolution and pixel coordinates, and for a depth
   its camera (metric), unit (metric only) and quantity (distance, z, or
   their inverse) with its direction.
7. **Corrections are a person's, apart**: a patch of a frame, in force or
   reverted, the recorded data untouched (as tracks' are, CT-0080).
8. **No maker in the Core**: recording is one command any adapter calls
   (`signals.record_signal`); the Core knows no Blender, no model.

## Consequences

- The graph reads a signal by id (`signal.read` with `signal`), checked
  once, at the instant its source shows (`of`), and refuses a record whose
  kind or camera differs from what the node declares -- so SPEC-0012's
  validation keeps holding.
- An operation can now require geometric depth, warn on estimated, or
  weigh by measured error -- the distinction is data.
- The Blender and model adapters (C8 steps 2-3) write records; nothing they
  produce is read any other way.
