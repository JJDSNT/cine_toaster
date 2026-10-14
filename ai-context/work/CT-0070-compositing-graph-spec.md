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

- `SPEC-0012` drafted, status `draft`, awaiting review.
- Appendix B writes every existing transition family, VFX item and title as
  a graph. It found two operations missing -- `merge.channels` (chromatic
  aberration) and `merge.depth` (occlusion; also the first piece of 2.5D) --
  both added to the primitives. With them, everything is expressible, or
  expressible as an opaque node: gl-transitions shaders not re-expressed, OFX
  plugins, Blender simulations as `generate.render`.

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

- On paper only, by design: Appendix B.
