---
id: SPEC-0011
title: Transition mattes and overlays — a join shaped by a picture, and a picture riding it
type: specification
status: accepted
implementation: partial
owner: project
created_at: 2026-10-14
updated_at: 2026-10-14
tags:
  - transitions
  - compositing
  - demos
---

# Goal

A join between two playing pictures can be shaped by a third picture, the
**matte**, and can carry a fourth, the **overlay**, on top of it. This is what
the Video Toaster's organic wipes did: smoke, ink, a burst, an animated object
crossing the frame while the next shot appears behind it (CT-0064, roadmap D3).

Today a transition is a function of two pictures and a progress
(`getFromColor`, `getToColor`, `progress`). Every shape it draws is a formula
in its shader. `luma` and `displacement`, the two gl-transitions shaders that
read a picture, are left out of the catalog because nothing gives them one.

Layers within a shot (a picture flown over another and held) are not this
specification; they are D4 and will have their own. This one is limited to
the join.

# Terms

- **Matte**: a picture whose brightness decides, pixel by pixel, how much of
  the incoming picture is seen. Black is the outgoing picture, white the
  incoming.
- **Still matte**: one image. Its brightness is the **order** in which pixels
  change: as `progress` rises from 0 to 1, a pixel changes when `progress`
  passes its brightness (the gl-transitions `luma` rule).
- **Moving matte**: a clip. Its frame at a moment of the join **is** the mix at
  that moment. It must start black and end white; the frames between are the
  shape of the join.
- **Overlay**: a picture with alpha (a still or a clip), composited over the
  joined picture for the length of the join.
- **Softness**: how many brightness levels the change of a still matte is
  spread over, so its edge is not a hard line.

# Where a matte or an overlay comes from

From the transition item, or from the join that uses it. Both are allowed
because both happen: a shader that ships with its texture (`luma` with a
gradient), and a production that has its own ink-blot clip and wants a
catalog wipe shaped by it.

## In the catalog item

```toml
id = "ink-wipe"
kind = "matte"                 # new kind: no shader of its own
[inputs]
matte = "ink.mp4"              # a file in the item's directory
overlay = "ink-edge.mov"       # optional, with alpha
softness = 0.08
```

A `glsl` item may also declare inputs. Each `sampler2D` uniform the shader
declares names an input of the same name:

```toml
id = "luma"
kind = "glsl"
upstream = "gl-transitions:luma"
[inputs]
luma = "gradient-radial.png"
```

A shader whose `sampler2D` has no input is refused, as today.

## On the join

```yaml
- n: 4
  transition:
    id: matte-wipe             # a built-in item that is only a matte
    matte: mattes/splash.mp4   # relative to the production
    overlay: mattes/splash-edge.mov
    softness: 0.05
    reason: the next scene arrives as a wave
```

A join's `matte` or `overlay` replaces the item's input of the same name.
Paths are relative to the production and must stay inside it, as every asset
path does.

## Generated mattes

A matte may also be generated, not drawn: `matte: {effect: <vfx id>, ...}`
renders an item of the VFX catalog on black for the join's length and uses
its brightness. This is one source among the others, not the purpose of this
specification; it exists because the prototype showed it works (roadmap D3).
A generated matte is rendered once per join and parameters, kept in the
cache, small, and enlarged.

# Behaviour

1. **Timing.** A moving matte is played across the join: its first frame at the
   join's first frame, its last at the last. A matte shorter or longer than
   the join is retimed to it, and said in the version's notes. An overlay is
   played at its own rate from the join's start; one shorter than the join
   ends early, and is said.
2. **Size.** A matte or overlay of another aspect than the frame is scaled to
   cover the frame and centred; never letterboxed, since black in a matte is a
   meaning, not a border.
3. **Moving pictures.** Both pictures keep playing through the join, as
   transitions already do (measured in CT-0064). A matte never freezes them.
4. **Completion.** At progress 0 only the outgoing picture is seen and at 1
   only the incoming, whatever the matte: a moving matte that does not reach
   white is completed over its last tenth, and said.
5. **Overlay last.** The overlay is composited after the two pictures are
   joined, with its own alpha; `blend: normal | screen | add` (default
   normal). An overlay with no alpha channel is refused, not keyed.
6. **The same everywhere.** The browser preview, the GL renderer and the FFmpeg
   stand-in give the same join from the same inputs, within compression.

# Renderers

- **GL** (`shader_render`): binds each input as a texture after the two
  pictures; a moving matte's texture is rewritten every frame with the frame
  for that progress. The host also provides `getMatte(vec2 uv)` for `matte`
  items, so a `matte` kind needs no shader of its own.
- **FFmpeg stand-in**: the incoming picture takes the matte as its alpha
  (`alphamerge`) over the outgoing one; a still matte is turned into a moving
  one by a threshold ramp; the overlay by `overlay` or `blend`. This is the
  path the prototype took.
- **Preview** (the Transitions room): binds the inputs as textures; a moving
  matte as a `<video>` texture.

# Checks

As implemented (CT-0069): the first two are checks when the scene loads; the
last two need the picture probed and are said in the version's notes when
the cut is made.

- `transition_input_missing` (error): an input the item or the join names is
  not there, or a shader's `sampler2D` has none.
- `transition_input_outside` (error): an input path leaves the production or
  the item's directory.
- `transition_matte_incomplete` (warning): a moving matte that does not start
  black or end white.
- `transition_overlay_without_alpha` (error).

# Acceptance criteria

- `luma` and `displacement` are in the catalog, each with a texture of its own
  and a licence for it, and run in the preview and the version.
- A join through a moving matte between two playing clips is the same in the
  GL and the FFmpeg renderer: the middle frame differs by less than a few
  levels per channel.
- A still matte with softness gives an edge that is not a hard line.
- An overlay with alpha is seen over the join, and nowhere else.
- A version's notes say when a matte or overlay was retimed or completed.
- Every check above has a test and a practice that explains it.

# Deferred

- Per-join parameter overrides other than the inputs (CT-0050's to-do).
- A matte that is itself joined to the music's beats (D1b).
- Layers within a shot (D4).
