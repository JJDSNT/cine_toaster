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

1. the [gl-transitions](https://github.com/gl-transitions/gl-transitions)
   shader bank, a git submodule at `vendor/gl-transitions` (see below);
2. built-ins distributed with Cine Toaster;
3. directories in `CINE_TOASTER_TRANSITIONS_PATH`;
4. a production's optional `transitions/` directory.

Later catalogs override earlier items with the same ID. This permits project
pinning and customization without modifying application code. All asset paths
are constrained to their transition directory.

`examples/amiga-demo-reel/transitions/amiga-copper-bars/` is a working example
of the third catalog. Its film-specific colour, pattern, and editorial purpose
stay with the production while Cine Toaster owns only the loader and shader
contract. See [Production-specific tooling](production-tooling.md) for the
general ownership rule.

## gl-transitions: reviewed and unreviewed

gl-transitions' shaders follow the contract above, so they run unchanged. Its
licences are MIT, with one BSD-2 and one BSD-3 item: permissive, so ADR 0011
allows the submodule. A clone needs `git submodule update --init` (`make
setup` runs it), and a wheel carries the shaders and their licence.

Every upstream shader is listed as **unreviewed**: its name, author, licence
and parameters come from its own header, but nobody has said when it serves a
film and it declares no FFmpeg stand-in. The Transitions room keeps these in a
collapsed bank, and an agent should not propose one.

A shader is **reviewed** by writing a manifest that names it instead of an
asset. The manifest adds the editorial contract and the stand-in, and replaces
the raw item:

```toml
id = "film-burn"
name = "Film Burn"
kind = "glsl"
upstream = "gl-transitions:FilmBurn"   # licence and author come from the shader
# ...description, guidance, use_when, avoid_when, [render]
```

Two upstream shaders (`luma`, `displacement`) need an extra texture that no
renderer supplies, and are left out.

## Parameters

A shader declares its parameters as uniforms with a default in a comment:

```glsl
uniform float count; // = 10.0
uniform ivec2 size;  // = ivec2(4)
```

The catalog reads them, and both the preview and the render set them. An unset
uniform is zero, and many transitions do nothing at zero. A uniform without a
default, or of a type the renderers cannot supply, keeps the shader out of the
catalog.

## Rendering

A join is drawn by the assembly as a compositing graph (ADR 0022). A GLSL
item's own shader is an `opaque.gl` node, run by the GL renderer (ModernGL,
the `gpu` extra) in the display encoding it was written for; a recipe (`graph`
kind) and a `matte` join are drawn by the GL renderer or the NumPy reference.
When GL cannot run, a reviewed shader's `[render].ffmpeg` stand-in is used and
the version says so; an item with no stand-in, such as every unreviewed
shader, becomes a straight cut, also said. A join replaces the end of the
outgoing shot and the start of the incoming one, so the running time is the
same either way. A recipe's preview clip is drawn from its graph by
`transitions.render_preview`.

Since CT-0076 the built-in catalog is filed by family -- `dissolve`,
`wipe/geometric`, `wipe/luma`, `wipe/custom`, `warp`, `warp-wipe`, `move`,
`stylised` -- and its reviewed items are recipes of primitives, except two
that say why they stay shaders (`opaque_reason`). A recipe that replaces an
upstream shader names it in `upstream`, so the raw shader is not listed
beside it. A join's matte may be a file or a generator:

```yaml
transition: {id: matte-wipe, matte: {gradient: {kind: conic}}}          # a clock, drawn
transition: {id: matte-wipe, matte: {noise: {kind: perlin, scale: 4}}}  # an organic order
```

Recording a per-shot parameter override, and WebM compositing roles, are
deferred.
