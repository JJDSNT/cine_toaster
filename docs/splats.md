# Gaussian splats

A Gaussian splat is a captured place (or object) that can be seen from any
camera. Cine Toaster draws splats with **Spark** (World Labs, MIT: three.js
and WebGL2) in a headless Chromium (Playwright), with a transparent
background. Formats: `.ply`, `.spz`, `.splat`, `.ksplat`, `.sog`.

```bash
make install-splat          # Playwright and its Chromium; Spark and three.js are fetched once
```

## A location seen through its splat

A location may declare the splat of its set, and where the plan sits in it:

```yaml
# locations/listening-station/location.yaml
splat:
  file: station.spz
  position: [3.0, 1.0, -2.3]   # the plan's origin in the splat, in three.js axes (y up)
  rotation: [180, 0, 0]        # Euler degrees (many captures are upside down), or a quaternion
  scale: 0.6                   # splat units per metre
```

```bash
toast splat plate <project> SC-030 P2 --frames 24
```

renders the shot's camera move (the same poses as the blocking frame) through
the splat: `renders/splat/SC-030/P2.mp4` and its first frame, which can be
listed as the location's plate for that camera and so become the start of a
master picture (`derive: {from: location:CAM-C}`).

## A splat as an element

```toml
# vfx_elements/butterfly/element.toml
splat = "butterfly.spz"
blend = "alpha"
[params]
rotation = [180, 0, 0]
radius = 2.5
spin = 60
```

The element is drawn on a turntable (centred on its bounds) and composited.

## Speed

Without a GPU the browser rasterises in software (SwiftShader): about 10 s a
frame at 480×270 for a million splats; the first frame waits until the
splat is drawn. Results are cached. On a machine with a GPU the same page
renders in real time.

## What else exists (study, CT-0047)

Dynamic (4D) splats are sequences of PLY or `.sog4d` (SuperSplat 4D);
Blender 5.3 (November 2026) imports and renders splats natively (PLY, SPZ,
USD). Splats are made from photos or video through COLMAP and a trainer
(gsplat, nerfstudio, Postshot, Polycam, KIRI, Luma) and edited in SuperSplat.

## NeRF: the camera goes out, the render comes back

NeRFs are rendered by nerfstudio on a CUDA GPU (often a remote one). Cine
Toaster writes the shot's camera move as the `camera_path.json` that
`ns-render camera-path` reads, from the blocking frame's poses:

```bash
toast nerf path <project> SC-030 P3 --frames 48 --width 1280 --height 720
# -> exports/nerf/SC-030/P3.json, and the ns-render command to run on the GPU machine
```

The location places the plan in the NeRF's world:

```yaml
nerf:
  config: outputs/station/nerfacto/config.yml
  position: [0, 0, 0]
  rotation: [0, 0, 0]   # Euler degrees XYZ
  scale: 0.25           # NeRF units per metre
```

The rendered video comes back as a plate or an element. Keyframes are
OpenGL camera-to-world matrices (row-major) with three.js's vertical field
of view, as nerfstudio's `get_path_from_json` reads them; the file was
checked against that code, not yet against a running nerfstudio.
