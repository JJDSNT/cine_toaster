---
id: CT-0047
title: VFX modalities, external engines, game engines and Gaussian splatting — study and working examples
type: work
status: doing
owner: development agent
created_at: 2026-09-30
updated_at: 2026-09-30
tags:
  - vfx
  - color
  - usd
  - openvdb
  - openfx
  - unreal
  - unity
  - gaussian-splatting
---

# What

The user's direction (2026-09-30): grow the VFX catalog (CT-0031) into one
that covers effects for titles, objects, sets and whole shots — fire,
smoke, melting, shattering, disintegration, particles, liquids, weather,
electricity, holograms, distortions, optical effects — through every
delivery and execution modality, **each with at least one working
example** that proves the path: in the catalog → configured → executed or
imported → previewed → composited → exported. Plus two studies: how Unreal
Engine and Unity can take part in the pipeline, and Gaussian splatting
(static and dynamic) as a spatial medium for sets and cameras. What the
user may have forgotten is left to the development agent's judgement.

# The modalities, and the example each needs

| # | Modality | How it runs in Cine Toaster | Example to prove it | State |
|---|---|---|---|---|
| 1 | FFmpeg filters | `vfx.py` procedural effects | film-grain, glitch, … (9) | done (`4017787`) |
| 2 | Video on black (screen/add) | element `blend: screen` | fire element | done |
| 3 | Video with alpha (ProRes 4444, qtrle, VP9 alpha) | element `blend: alpha` | alpha smoke | done |
| 4 | Chroma key (green/blue) | element `blend: key` | green sparks | done |
| 5 | Video + separate matte | element `matte:` file, `alphamerge` | Blender-rendered element with its matte | done |
| 6 | PNG sequence with alpha | element `file: frames/f_%04d.png` | Blender-rendered particles | done |
| 7 | OpenEXR sequence (linear, half float) | element `format: exr`, OCIO to display | Blender-rendered sim in EXR | done |
| 8 | OpenColorIO | a config (ACES studio or Blender's), transforms baked to `.cube` for FFmpeg `lut3d`; `look` effects | EXR linear → sRGB; a look | done |
| 9 | Blender scripts | engine `blender` effect items (like titles) | sparks-burst, disintegrate | done |
| 10 | Blender projects (`.blend`) | a production `.blend` with declared parameters, rendered headless | a `.blend` element project | done |
| 11 | OpenVDB volumes | Blender imports `.vdb`, renders with alpha → element | openvdb.org `explosion.vdb` / `smoke.vdb` | done |
| 12 | OpenUSD scenes | Blender imports USD; Cine Toaster exports its plan (room, cameras, marks, set pieces) as USD | usd-wg Teapot; the demo's set as USD | done |
| 13 | OpenFX plugins | Natron (an OFX host) run headless (`NatronRenderer`) on a generated project | bloom, lens distortion, glow | done |
| 14 | Alembic caches (added) | Blender imports `.abc` | a cache rendered as an element | later |
| 15 | Gaussian splats | Spark (three.js, MIT) viewer + camera path rendered headless; Blender 5.3 native | a `.spz` as a location plate / element | done |

Engines are external programs run on files, never linked (ADR 0011): FFmpeg,
Blender (4.5 LTS in `~/ferramentas-ext`, 5.2 LTS in `~/.local/opt`),
Natron, OpenColorIO (the `opencolorio` Python wheel, BSD-3).

# What the user may have forgotten (the agent's additions)

- **Alembic** (geometry caches between tools), next to USD and VDB.
- **Render passes and Cryptomatte** (multichannel EXR: depth, motion
  vectors, normals, object IDs) for compositing, defocus and relighting.
- **Matchmove / camera tracking**: an element stuck to something in a
  generated take needs the camera solved (Blender's tracker; COLMAP, which
  also feeds Gaussian splatting).
- **AI mattes and depth**: segmentation (SAM 2) and depth estimation
  (Depth Anything) produce mattes and depth for generated takes, without
  rotoscoping — a natural source for modality 5.
- **Houdini / EmberGen**: the industry's simulation tools; they export VDB
  and flipbooks, which modalities 6, 7 and 11 already accept.
- **LUTs (`.cube`) and ACES**: the practical face of OCIO for grading.
- **Lottie**: vector motion graphics beside the title catalog.
- **OpenTimelineIO**: editorial exchange with DaVinci, Premiere, Unreal.
- **Provenance and licence per asset**, and **heavy renders on a remote GPU**
  (RunPod) under the same budget ceiling.

# Unreal Engine and Unity: how they can take part (study)

- **Unreal**: Movie Render Queue renders Level Sequences from the command
  line, with a Python executor for full control; multi-pass EXR out.
  Scenes and cameras come in as USD (Unreal's USD Stage) or FBX; editorial
  as OTIO through a (C++) plugin. Role in Cine Toaster: a *render engine
  behind an adapter*, fed the plan (set, cameras, moves) as USD and
  returning takes/passes with lineage. Heavy (GPU, Windows or a Linux
  build); likely on a remote machine.
- **Unity**: the Recorder renders Timeline cinematics to video or image
  sequences, launched from the command line in the Editor (not in
  players); Cinemachine drives procedural cameras; USD and Alembic
  packages import scenes. Same role: an adapter fed USD, returning takes.
- The bridge both share with Blender is **USD**: Cine Toaster exporting its
  geometry (room, set pieces, cameras with lenses and moves, marks) as a
  USD stage is the concrete, testable first step, and it is engine-neutral.

# Gaussian splatting (study)

- Static 3DGS: formats PLY (the training output, float, SH3), SPLAT,
  KSPLAT, SPZ (about 10× smaller than PLY, keeps SH), SOG (spatially
  ordered, streamable). Dynamic (4DGS): sequences of PLY, `.sog4d`;
  SuperSplat (4D) edits and plays both.
- Creation: from photos or video via COLMAP + training (gsplat,
  nerfstudio, Postshot, Polycam, KIRI, Luma); from a single image
  (KIRI's 4DGS work); editing in SuperSplat.
- Rendering: Spark (World Labs, three.js/WebGL2; PLY, SPZ, SPLAT, KSPLAT,
  SOG; meshes and splats together; LoD streaming in 2.0); Blender 5.3
  (November 2026) imports PLY/SPZ/USD splats natively and renders them in
  Workbench, EEVEE and Cycles; the KIRI 3DGS Render add-on for earlier
  Blender.
- Role in Cine Toaster: a **location whose look is a splat** — the set
  captured once, then any camera of the plan rendered through it as a
  plate (the start of a generation, SPEC-0010), with set pieces and
  subjects from the plan composited in. Camera moves from the catalog run
  through the same poses as the blocking frame.

# Order of work

1. Element formats: PNG and EXR sequences, video + matte (5, 6, 7), with
   OCIO (8) for EXR — the examples rendered by Blender (9).
2. Blender effect items (9) and a `.blend` project element (10).
3. OpenVDB (11) through Blender.
4. USD: import (12) and the plan exported as USD (the Unreal/Unity bridge).
5. OpenFX through Natron (13).
6. Gaussian splats: a Spark render of a camera path over a `.ply` (15).
7. Alembic (14) if time allows.

Each step ships its example, a test, and the line in this table.

# Sources

- OpenVDB sample models: https://www.openvdb.org/download
- USD-WG assets: https://github.com/usd-wg/assets ; NVIDIA packs:
  https://docs.omniverse.nvidia.com/usd/latest/usd_content_samples/downloadable_packs.html
- Natron releases (2.5.0, OFX host, NatronRenderer):
  https://github.com/NatronGitHub/Natron/releases ;
  https://natron.readthedocs.io/en/rb-2.5/guide/getstarted-about-features.html
- OpenColorIO: https://pypi.org/project/opencolorio ; ACES configs:
  https://github.com/AcademySoftwareFoundation/OpenColorIO-Config-ACES/
- Unreal MRQ command line:
  https://dev.epicgames.com/documentation/en-us/unreal-engine/using-command-line-rendering-with-move-render-queue-in-unreal-engine
- Unity Recorder: https://docs.unity3d.com/Packages/com.unity.recorder@latest/index.html ;
  Cinematic Studio: https://docs.unity3d.com/Manual/CinematicStudioFeature.html
- Splat formats: https://swyvl.io/blog/gaussian-splat-formats-ply-spz-ksplat/ ;
  SuperSplat 4D: https://github.com/forgrabbit/supersplat4d ;
  Spark: https://github.com/sparkjsdev/spark ;
  Blender 5.3 splats: https://radiancefields.com/blender-5.3-will-bring-native-3d-gaussian-splat-import-and-rendering
- Free VDB assets for Blender: https://cgheven.com/blog/free-vdb-assets-how-to-find-import-use-blender-2026

# Done: phase 1 and 2 (2026-09-30)

- `color.py`: OpenColorIO (the `opencolorio` wheel 2.5, built-in ACES
  studio config), `exr_to_display` (premultiplied alpha divided out before
  the display transform, straight-alpha PNGs, cached), `bake_look` (an OCIO
  view as a `.cube` for FFmpeg's `lut3d`). OpenEXR read with the `OpenEXR`
  wheel 3.5.
- `vfx.py`: elements as video, image or EXR sequences (`%04d`), a separate
  `matte` (`alphamerge`), or a `.blend` `project` rendered headless
  (`_blender/project.py`) into cached EXR; `engine = "blender"` items
  (`sparks-burst`, `disintegrate`) render an element on the fly with the
  shot's parameters (`_blender/element.py`, Cycles CPU, transparent film);
  `aces-film-look`.
- `vfx_examples.py` + `toast vfx examples|list`: six example elements, one
  per form, made on this machine (17 s), each composited the same way.
- Found: hiding a particle emitter from render hides its particles
  (`show_instancer_for_render` instead); EXR emission above 1 clips to
  white in an un-tone-mapped view (ACES view for fire-like elements);
  ACES 2.0 maps display white to about 0.71.
- Tests: `ModalityTests` (PNG sequence, video + matte, EXR through OCIO,
  the baked look; the six examples when Blender is present).

# Done: phase 3, OpenVDB (2026-09-30)

- `_blender/volume.py`: import (`object.volume_import`; `.vdb` or a `%04d`
  sequence), centre and scale, Principled Volume with `density` and, from a
  `temperature` grid, blackbody emission through an attribute scaled to
  kelvin (the sample stores about 0–2), a sun, a turntable spin, Cycles CPU
  with a coarse volume step rate; EXR with alpha.
- Element `volume = ...` (format `openvdb`), shading `[params]` in
  `element.toml`, overridable per shot. Samples: smoke.vdb (density) and
  explosion.vdb (density, temperature, velocity), both rendered and
  composited (explosion 24 frames at 480×270 in about 80 s on 8 CPU
  threads, then cached).
- `toast vfx examples` also downloads OpenVDB's `smoke.vdb` once into a
  shared asset folder and registers `example-openvdb`.
- Test: `OpenVdbTests` (skipped without Blender or the sample).

# Done: phase 4, OpenUSD (2026-09-30)

- `usd_export.py` + `toast usd export`: room, set pieces, subjects (moving),
  one camera per shot with lens and move sampled from `blocking.state_at`
  every 4 frames; Z up, metres, 24 fps, ids in `customData`. `usd-core` 26.8.
- Checked in Blender (USD import, one render per shot camera) against the
  blocking frames: same framing at P2 start/end and P3 start.
- Found on the way: USD cameras measure lens and aperture in tenths of a
  stage unit (with metres, 50 mm is 0.5; Blender read 5000 mm); Blender's
  importer merges an Xform with a single child and drops its animation, so
  each subject is its own animated shape.
- Element `usd = ...` (format `openusd`) rendered by `_blender/usd.py` with
  the stage's materials, through a named camera or a turntable; the USD-WG
  Teapot (Apache-2.0) rendered and composited in 7 s.
- Tests: `tests/test_usd.py` (the stage's structure; the P3 camera centres
  Mara as the frame does; subjects move per shot; USD import when Blender
  and the sample are present).

# Done: phase 5, OpenFX through Natron (2026-09-30)

- Natron 2.5.0 installed headless under `~/.local/opt/Natron` (its Qt
  installer driven by a control script; its post-install desktop-database
  step needs stub `update-desktop-database` etc.). 580 plugins: openfx-misc,
  openfx-io, CImg, G'MIC, Arena, Shadertoy.
- `_natron/chain.py` (run by `NatronRenderer -w Out 1-N`): reader, the
  plugins in order with parameters set by their own names, writer. Found:
  headless, the reader does not detect the sequence's range (given
  explicitly), the writer falls back to the project's HD format whatever
  its `formatType` says (a project format of the picture's size is added:
  `addFormat("Name WxH 1")`, chosen by name), and a 2D parameter is set with
  `set(x, y)`, not `setValue`.
- `vfx.py`: `engine = "ofx"` items; a shot's OFX effects run first as one
  chain (frames out as PNG, back into a clip with the sound), then the
  FFmpeg effects. Items: ofx-bloom (with `mix`), ofx-lens-distortion,
  ofx-glow. `toast doctor` reports Natron.
- Test: `OpenFxTests` (lens distortion bends the grid; the sound survives).

# Done: phase 6, Gaussian splats (2026-09-30)

- `splat.py`: Spark 2.3 + three.js 0.180 (fetched once into the shared asset
  folder, with the one three.js addon Spark imports), a page rendered in
  Playwright's Chromium with SwiftShader WebGL2, a transparent background;
  poses as position/target/lens; the plan (Z up) mapped to three.js (Y up);
  a location's `splat:` transform (position, rotation, scale); `centre`
  frames an element on its bounds; the first frame waits until something is
  drawn (Spark sorts in a worker).
- `toast splat plate <project> <scene> <shot>`: the shot's move through the
  location's splat → video + first frame (the plate), without rewriting
  the location. Element `splat = ...` (format `gaussian-splat`, turntable,
  cached).
- Speed on CPU: about 10–13 s a frame at 480×270 for Spark's butterfly
  sample; real time on a GPU.
- Tests: `tests/test_splat.py` (axis mapping, shot poses from the plan,
  rotations and turntables; a real render when Chromium and the sample are
  present).

# NeRF (noted 2026-09-30, the user asked whether it is worth supporting)

Worth it as an *input*, not as a renderer of its own. In production,
Gaussian splats have largely taken NeRF's place: they render in real time,
are editable, and the same captures train both (nerfstudio trains NeRFs
and splats from the same COLMAP data, and `splatfacto` is its splat
method). What a NeRF adds is quality on thin, view-dependent detail at a
far higher rendering cost, on a CUDA GPU. The useful support is therefore:

1. export a shot's camera move as a **nerfstudio camera path** (the poses
   `shot_poses` already computes) so `ns-render` renders it on a GPU
   machine (RunPod, under the budget ceiling);
2. bring the result back as a plate or element (an image sequence: already
   supported);
3. prefer converting captures to splats where possible, which Cine
   Toaster renders itself.

Not started; the export in (1) is small and could follow the splat work.
