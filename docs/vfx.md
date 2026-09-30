# Visual effects

Effects are chosen from a catalog, like titles, transitions and camera
moves. The **VFX** room plays each one on a neutral picture (rest the
pointer on a card). A shot lists its effects, applied in order, before its
title:

```yaml
- n: 12
  effects:
    - {id: film-grain, strength: 0.3}
    - {id: fire-over, element: fire-01, x: 0.7, y: 0.6, scale: 0.4, start: 0.5}
    - {id: camera-shake, strength: 0.5}
```

## Procedural effects (FFmpeg)

film-grain, vignette, light-leak, chromatic-aberration, glitch,
camera-shake, flash, focus-pull-in, old-film. They need nothing but FFmpeg.

## Element effects: the production's stock elements

fire-over, smoke-over, sparks-over, explosion-over and muzzle-flash
composite a stock element the production brings. Nothing is downloaded or
bundled: bring the packs you are licensed for (ActionVFX, FootageCrate, FX
Elements, your own renders) and describe each one:

```toml
# vfx_elements/fire-01/element.toml
id = "fire-01"
category = "fire"          # fire, smoke, sparks, explosion, muzzle-flash, dust, debris, water, weather, light
blend = "screen"           # screen or add (on black), alpha (with transparency), key (on green)
key_color = "0x00FF00"     # for key
file = "fire_01.mov"
loop = true
source = "FootageCrate, free pack"
license = "FootageCrate free licence"
```

These are the three forms stock libraries deliver: on black (blended with
screen or add), with alpha (ProRes 4444, PNG sequences), or on green
(keyed). An element effect without a matching element is an error
(`effect_problem`), not a stand-in.

Catalogs layer: built in, `CINE_TOASTER_VFX_PATH`, then the production's
`vfx/<id>/effect.toml`; elements come from `CINE_TOASTER_VFX_ELEMENTS_PATH`
and the production's `vfx_elements/`.
