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

# Decisions

- **The animator belongs to the node**, not to curve nodes: each letter needs
  the keys at its own time, which a curve of the graph cannot give per letter.
- **A settled line is the block**: per-letter drawing reproduces the block's
  layout exactly, so animating a title never moves where it ends up.

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
