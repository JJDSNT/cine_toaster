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
| 11 | OpenVDB volumes | Blender imports `.vdb`, renders with alpha → element | openvdb.org `explosion.vdb` / `smoke.vdb` | todo |
| 12 | OpenUSD scenes | Blender imports USD; Cine Toaster exports its plan (room, cameras, marks, set pieces) as USD | usd-wg sample; the demo's set as USD | todo |
| 13 | OpenFX plugins | Natron (an OFX host) run headless (`NatronRenderer`) on a generated project | an openfx-misc effect on a take | todo |
| 14 | Alembic caches (added) | Blender imports `.abc` | a cache rendered as an element | later |
| 15 | Gaussian splats | Spark (three.js, MIT) viewer + camera path rendered headless; Blender 5.3 native | a `.ply`/`.spz` scene as a location plate / moving camera | study + example |

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
