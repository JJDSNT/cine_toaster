# Amiga Demo Reel

Cine Toaster is named after NewTek's Video Toaster, whose demo reel was a
slideshow carried by its transitions. This production is that reel: an opening
narration, four cards, four transitions, one look.

Every part of it runs with **no API key**. That is the point of it. A demo that
needs a credential is a demo most people never see run.

| Piece | How it is made | Status |
|---|---|---|
| Cards | `source: composed` — drawn from data, never generated | works today |
| Transitions | the catalog, including this production's own `amiga-copper-bars` | works today |
| Narration | declared, cast and placed in the mix; needs an audio tier to exist | not generated |
| Music bed | CC0, needs the same tier to fetch and record its licence | not fetched |

```bash
toast serve .
toast check .
toast shots . --scene SC-030
```

## What it demonstrates

- **All four transitions**, each with the editorial reason it was chosen, so the
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

## Sound is declared, not yet made

The reel casts its narration, names the voice and places it in the mix. It does
not ship the audio, because Cine Toaster cannot yet make it: there is no TTS and
no sound library in the tool.

Checking in a file the tool cannot reproduce would be worse than not having one.
The asset would have no provenance and no way to be remade, which is exactly the
problem the end card claims the reel does not have.

Declaring it anyway is the honest production state, and it is what an audio tier
gets built against.
