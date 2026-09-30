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

## Every form an element arrives in

`element.toml` describes the element however it was delivered:

| Form | `element.toml` |
| --- | --- |
| Video on black | `file = "fire.mov"`, `blend = "screen"` (or `add`) |
| Video with alpha (ProRes 4444, qtrle, VP9) | `file = "smoke.mov"`, `blend = "alpha"` |
| Green or blue screen | `file = "sparks.mp4"`, `blend = "key"`, `key_color = "0x00B140"` |
| Video with a separate matte | `file = "fire.mp4"`, `matte = "fire_matte.mp4"`, `blend = "alpha"` |
| PNG sequence with alpha | `file = "frames/f_%04d.png"`, `blend = "alpha"` |
| OpenEXR sequence (scene-linear) | `file = "frames/f_%04d.exr"`, `colorspace = "Linear Rec.709 (sRGB)"`, `view = "..."` |
| A Blender project | `project = "sparks.blend"`, `frames = 36` |
| An OpenVDB volume (or `%04d` sequence) | `volume = "explosion.vdb"`, `[params] density, fire, temperature, spin` |

EXR frames go through **OpenColorIO** to the picture's encoding before they
are composited (premultiplied alpha handled, cached). The config is
`CINE_TOASTER_OCIO`, else `$OCIO`, else OCIO's built-in ACES studio config;
`view` picks the output view, for example `ACES 2.0 - SDR 100 nits
(Rec.709)` for a filmic roll-off of fire's highlights, or `Un-tone-mapped`.
A Blender project is rendered headless with a transparent background into
scene-linear EXR (cached), then treated like any EXR sequence.

`toast vfx examples <project>` renders a small element with Blender and
registers one example of each form under `vfx_elements/example-*`, to see
every path working on this machine. `toast vfx list <project>` lists the
catalog and the elements with their forms.

## Effects Blender renders for the shot

`sparks-burst` and `disintegrate` (a word or an object coming apart into
drifting dust) are rendered by Blender with the shot's parameters when the
shot is drawn, through the same EXR and OpenColorIO path, then composited.

## Looks

`aces-film-look` applies an OpenColorIO view (ACES 2.0's tone scale by
default) baked to a 3D LUT that FFmpeg applies; `strength` mixes it with
the original.

## OpenVDB volumes

A `.vdb` (a simulation's smoke, fire, clouds) is rendered by Blender as a
volume: its `density` grid is the density, its `temperature` grid (when it
has one) blackbody emission scaled to kelvin by `temperature`, lit by a sun
and turned by `spin` degrees over the shot, with a transparent background
into scene-linear EXR, then through OpenColorIO like any EXR element.
OpenVDB's own samples (openvdb.org/download) work: `smoke.vdb` (2.5 MB)
and `explosion.vdb` (72 MB, with fire). `toast vfx examples` downloads
`smoke.vdb` once into `~/.local/share/cine-toaster/assets/openvdb`.
