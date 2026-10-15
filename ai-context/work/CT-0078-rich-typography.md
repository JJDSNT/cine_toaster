---
id: CT-0078
title: C6b -- rich typography and animated lettering
type: work
status: doing
owner: unassigned
created_at: 2026-10-14
updated_at: 2026-10-15
tags:
  - compositing
  - typography
  - titles
---

# What

Step C6b of `development/compositing-roadmap.md` (the user: "avance no
C6b"), recorded during C2 as an intention with the Amiga's Kara Fonts --
ColorFonts and AnimFonts -- as the historical reference, not the limit.
Typography as recipes of the primitives, not an effects engine of its own,
every entry naming its primitives. Turned into stages by what the engine
lacked:

- **A. Per-letter animation** (AnimFonts): missing -- `generate.text` drew a
  block.
- **B. Styles** (ColorFonts): fills (gradient, picture), outlines, shadow,
  glow are *supported by the graph* -- the text as a matte over any picture --
  and are exposed, not built (ADR 0022); bevel and emboss need a primitive.
- **C. Colour fonts** (OpenType COLR/CBDT): an option of the generator.
- **D. Lottie as an input** (the user's addition): a spike on a renderer.

# Done

## Stage A -- letters with their own time

- `generate.text` takes an animator, `letters`: keys each letter plays from
  its own start (offset in pixels at 720 lines, turn, scale, opacity, each
  eased -- Bézier included), `stagger` between letters in an `order`
  (forward, backward, from the centre, shuffled), a `start`, and a `wave`
  running along the line. Letters are placed where the whole block would put
  them -- Pillow's own line layout reproduced -- so a settled line is the text
  drawn whole; spaces take no place in the order. One drawing
  (`reference._letters_coverage`), uploaded by GL.
- Checked when the graph loads (`semantics.letters_problem`): unknown keys,
  orders, times, an animator that moves nothing.
- The title catalog: an effect `letters` and three items -- `type-drop`
  (letters fall in turning), `type-wave` (a wave along the line), `type-pop`
  (from the centre out, a Bézier overshoot).

## Stage B -- styles

- **Exposed, not built** (ADR 0022's rule): a title's `style` compiles into
  the graph's own nodes, every part made from the letters' alpha so it
  follows their animation and fades -- `fill` (a gradient or a picture, even
  a video, seen through the letters; a gradient spread over the lines' height
  where the text stands, unless `span: frame`), `outline` (a ring in its
  colour beneath), `cycle` (colour cycling), `glow` and `shadow` (behind).
  Any title takes one; checked when the title is expanded.
- **New primitive**: `filter.bevel` -- the picture lit as if raised, its
  blurred alpha a height; the light's direction decided once
  (`semantics.light_direction`), the lighting in one function for each
  renderer, identical on GL.
- **Gradients with up to eight stops** in both renderers (they used the first
  and last colours only): a chrome's bands, a rainbow.
- `colour.cycle` on GL, its hue matrix decided once (`semantics.hue_turn`).
- Items `chrome` (metal: bands, bevel, dark rim, shadow) and `colour-font`
  (the Amiga's ColorFonts: a rainbow cycling, a white rim, a shadow).
- Found on the way: a gradient across the frame left the letters a near
  uniform slice of it -- fills now follow the text's band.
- **The 1980s chrome** the user pointed to (three image searches: chrome
  metallic lettering, retro chrome text, Kara Fonts chrome -- the pages could
  not be read by the tools, so the look was taken from its known traits):
  sky over a sharp dark horizon with a warm ground reflected below, double
  rims, a lean, glints. Two gaps in the primitives, closed: gradient stops at
  chosen places (`at`: two close together make the horizon) and `skew` on
  `warp.transform` (in the geometry both renderers share). Exposed in the
  style: rings (`outline` as a list, inner first), `slant`, `glints`
  (four-pointed stars of stretched soft glow, twinkling in turn, upright after
  the letters lean). `chrome` is now the horizon chrome.

## Stage C -- colour fonts

- `generate.text` draws a colour font in its own colours: layered glyphs
  (COLR, versions 0 and 1) and bitmap ones (CBDT, Apple's sbix -- emoji),
  told by the font's table directory (`reference.colour_glyphs`). Pillow's
  FreeType draws them; GL uploads the reference's drawing, as for every text.
- A bitmap font has only the sizes it was drawn at: it is read at one of
  them and its drawing scaled (`_colour_font`).
- Of `colour` it takes the opacity, as a browser does; `glyph_colours:
  false` draws it in `colour`, as a plain font. Its outline is the drawing
  grown round (a round stroke) in `colour` beneath it; `hollow`, the outline
  alone. Its alpha is the text as a matte, so styles, fades and every title
  take a colour font as they take a plain one -- no title item needed: a
  title's `font` is enough.
- `toast doctor`: "Colour fonts" (FreeType 2.10 for COLR 0, CBDT and sbix;
  2.13 for COLR 1), with the remedy.
- A test font made for the purpose (`tests/fixtures/fonts/colour-test.ttf`,
  COLR: red below, blue above, a yellow diamond), with the script that
  builds it with fontTools -- needed only to remake it, not a dependency.
- Not drawn yet, recorded in `development/roadmap.md` with how: SVG glyphs
  (OT-SVG fonts draw as plain ones), and a colour font's letters under the
  letter animator (drawn in `colour`).

## Stage D -- Lottie as an input (spike, then adopted)

- **The spike**: three engines on ten files -- a probe made here (an eased
  square fading in) and nine samples from rlottie's and lottie-web's
  repositories (MIT): fills, masks, strokes, a gradient background, a
  loader, confetti, a star, an illustration, two lottie-web demos.
  - ThorVG (`thorvg-python` 1.1.3, LGPL 2.1 binding of the MIT engine):
    read all ten; 0.7 to 6 ms a frame at 480 pixels; draws text layers.
  - rlottie (`rlottie-python`, LGPL): read all ten, agreed with ThorVG on
    the probe to the pixel; slower on heavy files (confetti 37 ms against
    6); leaves text layers out; differs from ThorVG on a mask sample, the
    confetti's opacity and the star's stroke.
  - Skottie: `skia-python` (BSD) does not expose it -- out.
  - `python-lottie` stays out (AGPL).
- **Adopted: ThorVG, as a source format**, not a node: every file a graph
  reads goes through `reference.read`, which now hands a Lottie file (JSON,
  or a dotLottie archive's first animation) to the adapter
  `compositing/lottie.py`. It draws each frame with straight alpha in the
  display encoding -- the clip a PNG sequence becomes -- fitted by
  `conform_box`. So layers, elements, a title's fill and both renderers take
  it with nothing new to expose (ADR 0022). It plays at its own frame rate;
  `start`, `hold` and `stretch_to` work as for a clip.
- `toast doctor`: "Lottie", with the remedy; the extra `motion`.
- A demonstration: rlottie's confetti and star as two layers over the demo's
  sun (scratch, not committed: samples from LottieFiles, through rlottie).
- Left, recorded in `development/roadmap.md` with how: step 2 (converting
  what our primitives express into the graph), looping, which of the two
  engines is right where they differ, fonts for text layers.

## A shot drawn once (the user, 2026-10-15)

The limitation recorded in C6 ("a shot drawn in one graph"), asked for by the
user to close C6b: remove the three passes, keep one graph, no intermediate
encodes.

- Before: composite -> mp4 (4:4:4, crf 12); effects over it -> `.fx.mp4`;
  title over that -> mp4; then the cut re-encoded each piece (4:2:0, crf
  18): up to four encodes of a shot before the film's.
- Now: `compositing/shot.py` chains fragments -- each effect list and title
  is a graph with one port, `picture` -- after the shot's picture, renaming
  their nodes so none meets the base's (`chain`, `shot_graph`). The picture
  is the composite, or the take, the still, or the title's card as the port.
  A take is treated, then titled; a card titled, then treated (as before).
- `assembly._shot_drawing` builds and draws it once, by GL when it holds
  every op; `_draw_shot` writes it once, straight in the cut's piece format
  (`reference.PIECE`), and lays the take's sound (or the converted voice)
  under it by copy. The cut joins that piece as it is (`Segment.piece`).
- `titles.title_graph`/`card_picture` and `vfx.effects_graph` give the
  fragments; `titles.render` and `vfx.render` use them for previews and
  single renders, so there is one way to build each.
- `toast still` runs the same graph: a still holds the title and effects,
  and a shot cut from a take now has a still (a recorded limitation closed).
- Kept stills: every shot drawn by a graph now keeps its middle frame, not
  only composites.
- **OpenFX in the same graph** (the user: resolve it before the time base
  and C7). An OFX effect compiles to `opaque.natron` like any effect, in the
  order written (before, plugins ran first, out of order). `compositing/
  natron.py` stages it in `reference.render`: what feeds the node is drawn
  (GL when it can), written as float OpenEXR, run through Natron's chain
  script with EXR in and out, and read back as the node's value -- a port
  of the rest of the graph, which GL then draws. Adjacent plugins are one
  Natron run. `vfx._ofx` (mp4 in, PNG out, mp4 back) is gone, and with it
  the assembly's old pass functions (`_render_composite`, `_draw_title`).
- A still picture is drawn by the same path (read once, written once as the
  piece), instead of an mp4 held and then cut again.

## Review of stages B and C (the user, 2026-10-15) -- to return to

The user's observations, kept with ours so the work comes back to them:

- **Colour fonts were mixed up with emoji support.** The reference is the
  Kara ColorFonts look: lettering drawn with a material -- chrome, gold,
  stone -- its gradients, reflections, bevel and rim part of the type's own
  drawing. Emoji use the same technology (COLR, CBDT) for another purpose;
  they come free with stage C but are not its goal, and the demonstration
  should not have been made with them.
- **The glints are not part of such fonts** (interesting, but not standard):
  ColorFonts were still; animation belonged to AnimFonts or to the edit.
  Putting them in `chrome` by default went past the reference.
- **The goal is the look, not the format**: reading the Amiga's original
  ColorFont files (bitplane bitmaps) is not wanted.
- Ours: the three references sent (Google image searches for 1980s chrome
  and Kara Fonts chrome) could not be read by the tools, so the chrome was
  built from known traits -- which widened the drift. Images sent as files
  would serve as the reference.

What to do when this is taken up:

1. Demonstrate and test stage C with real decorative colour typefaces under
   the OFL (Nabla, Bungee Spice, Honk), not emoji; documentation names emoji
   a by-product.
2. `chrome` still by default, as a ColorFont is; glints stay a style option
   (`glints`), in an item of their own (say `chrome-sparkle`) or off.
3. Compare our `chrome` with real Kara chrome lettering (images from the
   user) before calling the look right.

# Decisions

- **The animator belongs to the node**, not to curve nodes: each letter needs
  the keys at its own time, which a curve of the graph cannot give per letter.
- **A settled line is the block**: per-letter drawing reproduces the block's
  layout exactly, so animating a title never moves where it ends up.
- **A style is recipes, not an effect**: only the bevel was missing from the
  engine; the rest is the letters as a matte and their alpha blurred, moved
  and filled.
- **Lottie is a format a source reads, not a node**: the graph already
  reads files with alpha; a node of its own would have been a second way
  in (ADR 0022). ThorVG over rlottie for speed and text layers.
- **A colour font keeps its colours** and takes only the text colour's
  opacity: a title's default colour is an off-white that would otherwise
  dim every colour font (found by the title test); browsers do the same.
  The outline keeps `colour`, which is what it is for.

# Validation

- `tests/test_lettering.py`: letters land where the block puts them (centred,
  left, right); each letter has its own time; the orders; a wave runs along
  the line; a mistaken animator is refused; the items are in the catalog; GL
  draws what the reference draws.
- Found on the way: the `letters` builder called with no animator (the
  catalog's generic tests do) gave an invalid graph -- it now falls back to
  each letter fading in after the one before; and the wave test averaged over
  the whole frame instead of the letters' own columns (the test's mistake).
- Full suite after stage A: 787 tests pass.
- `tests/test_lettering.py` (B): a style that cannot be drawn is refused; a
  fill runs across the letters, not the frame; an outline rings them in its
  colour; a shadow falls below and to the right; a bevel lights the faces
  turned to the light and darkens the others; a style follows the letters'
  animation; the items name the bevel and the cycling; GL draws the styled
  items and many-stop gradients as the reference does.
- Full suite after stage B: 796 tests pass.
- With the 1980s chrome: gradient stops make a sharp horizon where placed;
  `skew` leans a picture; two rings in their colours; a slant moves the
  upper half; glints shine at their moment and not always. Full suite: 799
  tests, one failing once -- `test_stems`' loudness of a stretch at exactly its
  0.5 dB bound (sound, untouched here); it passed three runs alone. Recorded
  in the roadmap as an intermittent test to make deterministic.
- Stage C (`ColourFontTests`): a colour font is told from a plain one; its
  glyphs keep their colours (blue above, red below, yellow at the centre);
  the text colour gives only its opacity, `glyph_colours: false` one colour
  throughout; an outline rings it in the text colour, the glyph intact over
  it, `hollow` the ring alone; a `fade` title in a colour font keeps red and
  blue; Noto Color Emoji draws at any size and in several colours; GL draws
  a colour font with an outline as the reference does.
- Found on the way: the test font's layers stood off-centre -- TrueType
  places an outline by the glyph's left side bearing, which the script had
  left at zero.
- Full suite after stage C: 806 tests pass.
- Stage D (`tests/test_lottie.py`): a Lottie file is told from other JSON;
  it plays with its transparency, eased fade and move, its colour decoded;
  it keeps its own frame rate under the film's; it holds its last frame or
  is gone; it stretches over another length; it is fitted as any picture;
  a dotLottie archive is read; a layer takes it over a picture; without
  ThorVG it says what to install. GL draws a Lottie layer as the reference
  does (mean difference 1e-7, by hand).
- Full suite after stage D: 815 tests pass.
- A shot drawn once (`tests/test_shot_graph.py`): a fragment reads the
  picture so far and keeps its own names (ports, curves); fragments follow
  in order; with no base the picture stays a port; in a cut, a take with a
  vignette and a caption is drawn in one graph -- no composite, effects or
  title file, not cut again -- and its still is the cut's frame with the
  vignette. `test_stills`' per-pixel bound re-measured: x264 at a letter's
  edge in a 160x90 frame gives 28 to 50/255 for one encode of the same
  still by the path taken (the old two encodes happened to stay under 32);
  bounded at 64, the mean and regional bounds unchanged. Full suite: 819
  tests pass.
- OpenFX staged (`OpenFxStagingTests`, `NatronTests`): adjacent plugins are
  one Natron run, in order, over what feeds them, drawn first (Natron
  mocked); the graph validates; with Natron, an empty chain returns frames
  unchanged to half-float precision, light above white included (measured:
  mean 1e-5 on the demo's sun); a cut draws a shot with an OFX lens
  distortion and a vignette in one graph, nothing written between. A lens
  distortion at k1 = 0 differs by 0.0045 on average: the plugin's own
  resampling, not the round trip. Full suite: 823 tests pass.
