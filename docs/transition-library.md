# Transition Library

Cine Toaster treats transitions as a shared visual vocabulary. The library is
available across productions, while a production records only the transition
identifier, parameters, and the editorial reason for choosing it.

Each transition is stored in its own directory:

```text
transition-id/
├── transition.toml
├── transition.glsl  # executable two-input transition
└── preview.webm     # optional rendered preview
```

A WebM-only item uses `transition.webm` as its asset. It is initially a visual
reference for filmmakers and agents, not a parameterized two-input effect.
Future WebM roles may include alpha overlays and luma mattes, but those should
be introduced as explicit compositing contracts rather than inferred from a
video filename.

## GLSL contract

GLSL items follow the open GL Transition v1 shape. A shader implements:

```glsl
vec4 transition(vec2 uv);
```

The host provides:

- `float progress`, from `0.0` to `1.0`;
- `float ratio`, the output width divided by height;
- `getFromColor(vec2 uv)` for the outgoing image;
- `getToColor(vec2 uv)` for the incoming image.

At progress `0.0`, only the outgoing source should be visible. At `1.0`, only
the incoming source should be visible.

## Semantic metadata

The manifest describes both implementation and editorial intent:

```toml
id = "diamond-wipe"
name = "Diamond Wipe"
kind = "glsl"
asset = "transition.glsl"
category = "geometric"
description = "The incoming shot expands from the center."
guidance = "Use as deliberate graphic punctuation."
energy = "high"
motion = "outward"
duration_ms = 900
tags = ["retro", "centered", "playful"]
use_when = ["A chapter change should be overt"]
avoid_when = ["A performance should remain emotionally invisible"]
license = "CC0-1.0"
```

`guidance`, `use_when`, `avoid_when`, `energy`, `motion`, and `tags` are the
AI-facing contract. An agent should use them together with the adjacent shots,
scene tone, and editorial intention; it should never choose from the transition
name alone.

## Catalog locations

Catalogs are loaded in this order:

1. built-ins distributed with Cine Toaster;
2. directories in `CINE_TOASTER_TRANSITIONS_PATH`;
3. a production's optional `transitions/` directory.

Later catalogs override earlier items with the same ID. This permits project
pinning and customization without modifying application code. All asset paths
are constrained to their transition directory.

`examples/amiga-demo-reel/transitions/amiga-copper-bars/` is a working example
of the third catalog. Its film-specific colour, pattern, and editorial purpose
stay with the production while Cine Toaster owns only the loader and shader
contract. See [Production-specific tooling](production-tooling.md) for the
general ownership rule.

## Current boundary

The first implementation is a preview and guidance bank. It executes GLSL live
against two sample frames and plays WebM references. Applying a transition to a
timeline, rendering through FFmpeg, recording a project selection, downloading
third-party packs, and parsing adjustable shader uniforms are deferred.
