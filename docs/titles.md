# Titles

Titles are chosen from a catalog, like transitions and camera moves. The
**Titles** room shows every item previewed by its own engine; type your own
text to see it drawn. A shot names one in its breakdown:

```yaml
shots:
  - n: 8
    kind: title_card          # a card: no take, the title on its background
    duration: 14.8
    title: {id: card, text: SINGULARITY, size: 40, fade_in: 1.4, fade_out: 1.4,
            font: fontes/Oswald.ttf, reason: the words disappear}
  - n: 9
    title: {id: caption, text: "03:13"}     # over the shot's chosen take
```

A bare string is a `card`'s text (`title: SINGULARITY`). Anything besides
`id`, `text` and `reason` is a parameter: `size` (pixels on a 720-line
frame), `color`, `position` (centre, bottom, top), `spaced` (letters
tracked out), `fade_in`, `fade_out`, `enter_at`, `font` (a file in the
production), `background` (a card's colour), `subtitle` (a lower third's
role, a card's second line). A neon sign also takes `color` (the tube),
`core_color`, `glow` (halo strength) and `ignite` (seconds of stutter).

## The catalog

| Category | Items | Engine |
| --- | --- | --- |
| cards | card, film-title | FFmpeg |
| reveal | typewriter, word-by-word | FFmpeg |
| motion | slide-up, grow | FFmpeg |
| lower thirds | caption, lower-third | FFmpeg |
| credits | credits-roll (lines separated by `\n`) | FFmpeg |
| texture | flicker, neon-sign (a pale core in a coloured halo, striking with a stutter, then a faint buzz) | FFmpeg |
| 3d | letters-turn-in, letters-rise | Blender |

Catalogs layer: built in, `CINE_TOASTER_TITLES_PATH`, then the production's
`titles/<id>/title.toml`, where a production keeps its own looks (its font,
its sizes) under its own ids.

## In the cut

When a scene is assembled, a `title_card` shot with a title becomes its
own segment, drawn on its background for the shot's duration; a shot with a
take and a title has the title drawn over the cut piece of the take, its
sound kept (the converted voice, when the cut hears one). A card is drawn,
not chosen: it has no take in the version's record.

## Engines

- **FFmpeg** (`drawtext`): text goes through files, so quotes, colons and
  accents never need escaping.
- **Blender** renders the letters as 3D objects (Workbench, on the CPU),
  with a transparent background, laid over the picture; the `.blend` is
  kept beside the frames so a title can be opened and changed by hand.
  Blender is found on PATH, in `CINE_TOASTER_BLENDER`, or unpacked under
  `~/.local/opt` or `~/ferramentas-ext`; `toast doctor` says which.

A title whose engine is missing is refused, not drawn by another; the
checks report it (`title_engine_missing`), and an unknown id is an error
(`title_unknown`).
