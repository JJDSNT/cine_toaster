# ADR 0022: Luma, matte, warp and wipe are compositing primitives, not effects

Status: proposed (2026-10-14, CT-0069, from the user's direction while
SPEC-0011 was being built; awaiting the user's acceptance).

## Context

Cine Toaster grew three catalogs, each with its own renderer: transitions
(GLSL shaders, FFmpeg stand-ins), VFX (FFmpeg filters, Blender, Natron) and
titles. SPEC-0011 added a fourth way to draw: a join shaped by a matte.

Built that way, the same operation is written again in each place. A matte
already existed three times before anyone named it: the VFX catalog keys a
stock element on green and lays it with its alpha; the luma `geq` in
`mattes.py` turns brightness into a mask for a wipe; the `luma` shader does
the same on the GPU. A luma key, a luma matte for a layer and a luma wipe are
one piece of information -- a picture's brightness -- used three ways. And the
catalog files `displacement` (which moves pixels) beside `luma` (which
reveals them) as if they were the same kind of thing.

The user's direction (2026-10-14):

- matte is a compositing resource; luma is information in the picture that
  can feed many effects;
- warp is a family of spatial transformations, reusable in VFX, compositing
  and transitions;
- wipe is a family of transitions based on masks: luma wipes, geometric
  wipes, custom wipes;
- they combine: a **warp wipe** deforms the picture while the next one is
  revealed;
- these are primitives shared by every renderer -- FFmpeg, Blender, ComfyUI
  and others -- and the catalogs should be built on them, not duplicate them.

## Decision

1. **Four primitives, each defined once, independent of any renderer.**
   - **Luma**: a picture's brightness as a signal, 0 to 1, with a range
     (black point, white point) and a softness. Not an effect: an input.
   - **Matte**: a mask that says how much of a layer is seen, pixel by pixel.
     It may come from a file, a picture's alpha (**alpha matte**: a Blender
     render over a generated picture), a picture's luma (**luma matte**), a
     key (**luma key**, a colour key), a shape, or a generated picture.
   - **Warp**: a spatial transformation of a picture -- move, scale, rotate in
     perspective, displace along a map, ripple, bend -- with parameters that
     may change over time.
   - **Wipe**: a transition that reveals the incoming picture through a matte
     whose coverage goes from nothing to everything over the join: geometric
     (a formula), luma (a picture's brightness as the order), or custom (a
     moving matte).
2. **Effects, transitions and layers are compositions of primitives.** A luma
   wipe is wipe(matte = luma(picture)). A warp wipe is wipe with a warp on the
   outgoing picture and on the incoming one. A matte painting is a layer whose
   matte isolates a window. A luma key is a layer whose matte is luma(itself),
   inverted. The catalogs name combinations and give them editorial guidance;
   they do not reimplement the operations.
3. **Each renderer implements the primitives, not the catalog.** FFmpeg,
   GL shaders, Blender, and later ComfyUI or others, each provide luma, matte,
   warp and wipe as they can, and say which they cannot. A catalog item
   declares the primitives it uses; the renderer that can run all of them is
   chosen, as `[render]` chooses a stand-in today.
4. **The catalogs are organised by family.** Transitions are filed as wipes
   (geometric, luma, custom), warps (displacement, ripple, swirl, perspective
   moves such as `cube` and `doorway`), warp wipes, and dissolves. VFX items
   that are only a primitive with a parameter (a luma key, a matte from a
   colour) move out of the VFX catalog into the primitives they are.
5. **Layers (D4) are built on the same primitives**: a layer is a picture,
   a warp (its place, size and perspective over time) and a matte.

## Amendment: the primitives the first list missed (2026-10-14)

Asked to check whether a primitive had been left out, the list was read
against what a compositing engine (Nuke, Fusion, an OFX host, the Toaster and
the ADO) cannot do without. Four were missing that everything else depends
on, and two of the four named ones are a level above the rest.

**Signals, of which luma is one.** Brightness is one channel a picture
carries; the same role is played by its alpha, each colour channel, hue and
saturation, and by channels other tools produce: depth (a Blender Z pass, or
a depth model run on a generated picture), motion vectors, normals, a
segmentation. A luma key and a depth key are the same operation on different
signals. *Signal* is the primitive; luma is its most used instance.

**Merge.** A matte says how much of a layer is seen; merge says how two
layers combine -- over, under, in, out, atop (Porter-Duff) and the blend
modes (screen, add, multiply, overlay, difference). Without it a matte does
nothing. The overlay of SPEC-0011 and every VFX element already merge,
each its own way.

**Colour.** A function of each pixel's colour: a LUT, curves, levels, a hue
shift, posterise, solarise, colour cycling -- the Toaster's ChromaFX. The
looks (OCIO, LUTs) already do part of it.

**Filter.** A function of a pixel's neighbourhood: blur, sharpen, glow,
defocus, edges (the ChromaFX "line art" mode), erode and dilate (which also
grow and shrink a matte).

**Time.** A picture at another moment: retime, speed ramp, freeze, reverse,
frame blending, an offset between layers, and feedback -- trails and echoes,
the ADO's Infinity. Nothing in Cine Toaster operates on time today except the
cut.

**Generate.** A picture made from parameters, not read: solid, gradient,
noise, shapes, text (the character generator), particles, a render. Most
mattes are generated.

Two more are not operations on pixels but feed every operation:

**Track.** Where something is in each frame (a point, a plane, the camera),
measured from the picture. A window replaced by a matte follows the window
because a track drives the matte's warp.

**Animate.** Every parameter of every primitive may change over time:
keyframes with easing, and values driven by other data -- a track, or the
music's beats (CT-0067), which makes a cut-to-the-beat pulse a parameter like
any other.

And two of the first four are **families built from primitives**, not
primitives themselves: a **wipe** is a merge of two pictures through a matte
whose coverage is driven by the join's progress; a **warp wipe** is that,
with a warp on each picture driven by the same progress. **Warp** and
**matte** stay primitives. A matte's own operations (invert, combine as
union, intersection or difference, grow, shrink, feather) are filters and
merges applied to a matte, not new primitives.

The primitives, then: **signal, matte, merge, warp, colour, filter, time,
generate**, fed by **track** and **animate**. Transitions, effects, keys,
titles and layers are compositions of them, and the catalogs are recipes.

## Consequences

- The order of work this implies is `development/compositing-roadmap.md`.

- SPEC-0011's matte and luma become the first implementation of two
  primitives. `mattes.py` is their FFmpeg form; the `luma` shader its GL form.
  Both are already checked against each other.
- The transition catalog's `category` is replaced by a family, and items such
  as `displacement` (filed as "organic" beside `luma` in CT-0069) are refiled
  as warps.
- The VFX catalog loses what is a primitive; its element effects (fire over,
  smoke over) become layers with an alpha or luma matte.
- A renderer is judged by which primitives it implements, which makes adding
  one (ComfyUI, for example) a bounded piece of work.
- Before D4 is specified, a specification of the primitives themselves is
  needed: their parameters, their identity, and what each renderer provides.
