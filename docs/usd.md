# OpenUSD: the plan out, scenes in

## A scene's plan as a USD stage

```bash
make install-usd
toast usd export <project> SC-030              # -> exports/usd/SC-030.usda
```

The stage holds what the plan says: the room (floor and walls, or only the
ground outdoors), the set pieces as boxes, the subjects (a capsule for a
person, a box for an object) moving as the shots move them, and one camera
per shot (`/Scene/Cameras/P3`) with its lens and its move, sampled from the
same poses the blocking frame draws. Z up, metres, 24 frames per second;
the shots are laid end to end on the timeline, and each prim carries its
Cine Toaster ids in `customData`. Lens and apertures follow USD's
convention (tenths of a stage unit: 50 mm is `0.5`).

It opens in Blender (checked: each shot camera frames the subjects where
the blocking frame draws them), and imports into Unreal (USD Stage) and
Unity (the USD package) as the start of a previs or a render there.

## USD scenes as elements

An element may be a USD stage, rendered by Blender with its materials:

```toml
# vfx_elements/teapot/element.toml
usd = "Teapot/Teapot.usd"
blend = "alpha"
[params]
camera = ""        # a camera in the stage; empty: frame it all and turn by `spin`
spin = 60
```

The USD-WG sample assets (github.com/usd-wg/assets, Apache-2.0) work.
