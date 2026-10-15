# Amiga Demo Reel

Cine Toaster is named after NewTek's Video Toaster, whose demo reel was a
slideshow carried by its transitions. This production is that reel: an opening
narration, cards, transitions chosen for a reason, one look.

Every part of it runs with **no API key**. That is the point of it. A demo that
needs a credential is a demo most people never see run.

| Piece | How it is made | Status |
|---|---|---|
| Cards | `source: composed`, each a title from the catalog: this production's own `reel-card` (`titles/`) | works today |
| Transitions | the catalog, including this production's own `amiga-copper-bars`; a scene's first join is its `enter` | works today |
| Narration | declared, cast and placed in the mix; spoken offline by `toast voice` | made by `make build`, not checked in |
| Music bed | a sound-catalog item or a fetched CC0 recording, its licence recorded | not chosen |

```bash
toast check .
toast voice .                                # speaks the lines, beside their scenes
toast assemble-sequence . the-reel --scenes  # each scene, then the reel
toast serve .
```

The reel is assembled like any film: each scene becomes a kept version, and
the sequence is cut from those. Its cards are drawn by the same compositing
graph as every composite (`toast still` draws one frame of one).

## What it demonstrates

- **Five transitions**, each with the editorial reason it was chosen, so the
  catalog's `use_when` can be read against the choice actually made.
- **A project-local transition** (`amiga-copper-bars`) referenced by a shot
  rather than merely loadable — the production-owned side of the boundary in
  [`docs/production-tooling.md`](../../docs/production-tooling.md).
- **A look** whose motion rules drive the pacing, declared once at project level
  instead of restated per scene.
- **Declared shot fields.** `copper_phase` and `scanline_rate` are this reel's
  own vocabulary. They are named in `project.yaml` under `shot_fields`, carried
  as data, and shown under the label the production chose. An undeclared field
  would still be kept, and would be reported rather than ignored.
- **Composed shots with dialogue**, which is how the narration is cast, timed,
  and placed in the mix.

## The narration is made, not shipped

The reel casts its narration, names the voice and places it in the mix.
`toast voice` speaks it offline with Piper and writes it beside its scene
(`scenes/010-cold-boot/sound/`), with a record of the words and the voice it
was given, so a line that is rewritten is spoken again.

The audio is not checked in: the tool makes the same file from the same line
on any machine, and a second copy in the repository would only drift.
