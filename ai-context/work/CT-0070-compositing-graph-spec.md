---
id: CT-0070
title: C1 -- the compositing graph specified (SPEC-0012)
type: work
status: review
owner: unassigned
created_at: 2026-10-14
updated_at: 2026-10-14
tags:
  - compositing
  - specification
---

# What

Step C1 of `development/compositing-roadmap.md`: SPEC-0012, the compositing
graph of ADR 0022 -- typed values, the colour contract, the primitives with
their ports and parameters, the composite in the breakdown, node identity and
recording, curves, renderer manifests, checks -- and a test of it on paper
against everything that exists.

# Why

ADR 0022 was accepted on 2026-10-14 (the user, with an outside review
concurring). The review's last advice: formalise the contracts, write
representative graphs, and check the existing operations fit, before
building.

# Done

- `SPEC-0012` drafted, reviewed once from outside, corrected; status `review`.
- Appendix B writes every existing transition family, VFX item and title as
  a graph. It found two operations missing -- `merge.channels` (chromatic
  aberration) and `merge.depth` (occlusion; also the first piece of 2.5D) --
  both added to the primitives. With them, everything is expressible, or
  expressible as an opaque node: gl-transitions shaders not re-expressed, OFX
  plugins, Blender simulations as `generate.render`.

## After the outside review (2026-10-14)

The review the user brought found six problems, all real when checked:

1. The luma wipe fed a signal straight into `matte.threshold`, which takes a
   matte: `matte.from_signal` was missing, in the TOML and in Appendix B (and
   in the warp wipe).
2. The luma key used `low` and `high`, which `matte.key` did not declare:
   its parameters are now stated per method.
3. Curves were used ("1 - progress", animated noise) but not defined:
   `curve.map`, `curve.combine`, `curve.noise`, the `{curve: node}` form, and
   the rules for time, keys and vectors; no expression language.
4. Depth from a monocular model and depth from a Blender camera are not
   comparable: `depth` (metric, one camera) and `depth_relative` are distinct
   kinds, `signal.align_depth` converts, and `merge.depth` refuses the
   relative kind.
5. Handover as half-float EXR for everything was wrong for depth, vectors and
   labels: a table per type (32-bit float for depth and vectors, 32-bit
   unsigned integers for segmentation).
6. Identity lacked the OCIO config's hash, the time context, frame size,
   renderer dependencies, external files by content, and model weights.

And its condition: the example graphs validated automatically. Done:
`cine_toaster.compositing.schema` holds the operations as data with a
validator; `ai-context/specs/SPEC-0012-examples/` holds 19 graphs (every
transition family, the warp wipe, a DVE move, an opaque shader, the window
replaced fixed and tracked, a luma key, an alpha matte from Blender, a Blender
object behind a person by depth, chromatic aberration, an element, grain, a
typewriter title, a beat pulse, trails) and 5 that must be refused -- two of
them the draft's own mistakes. `tests/test_compositing_schema.py` checks
them. Writing them found a clash: `curve.map` had a parameter named `op`, the
same as the node's own key; renamed `how`.

The specification is now `review`.

# Decisions

- **Premultiplied alpha inside the graph**, converted at the source: merges
  are sums, the compositing convention, and Blender's EXR is already so.
- **Default working space `Linear Rec.709 (sRGB)`**, the one `color.py` uses;
  a production may name ACEScg or another.
- **Luminance and luma are two operations**, each with named weights and
  transfer. The catalog's `luma` keeps Y' so its look does not change by
  surprise.
- **Opaque nodes are allowed and labelled**: a shader or plugin Cine Toaster
  does not decompose is a node with typed ports and one renderer; a recipe
  made only of them is shown as not portable.
- **Non-deterministic results are recorded in the production**, with
  provenance, on first run; the cache holds only what can be recomputed.
- **Handover between renderers is OpenEXR half**, linear, premultiplied.
- **A join's recipe is a graph with ports `from`, `to` and curve
  `progress`**; its `[expose]` list is the per-cut override CT-0050 left.

# To do

- Review of the draft (the user; an outside review if wanted).
- Then C2: the reference renderer against it.

# Validation

- `tests/test_compositing_schema.py` (6): every example valid; every invalid
  one refused for its reason; every primitive family used; curves drive
  numbers, not choices; only the two conversions allowed; ops named by family.
