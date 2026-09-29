---
id: CT-0031
title: VFX, motion graphics and titles through external tools (Natron, Friction, Blender)
type: work
status: ready
owner: unassigned
created_at: 2026-09-29
updated_at: 2026-09-29
tags:
  - vfx
  - motion-graphics
  - titles
  - adapters
  - future
---

# What

Support shots that need compositing, motion graphics or titles by driving
external tools behind one adapter boundary, the way generation providers sit
behind theirs:

| Tool | What it would do | Licence | How |
| --- | --- | --- | --- |
| [Natron](https://github.com/NatronGitHub/Natron) | Node compositing: keying, roto, tracking, and plates over generated takes | GPL-2.0 | External program. `NatronRenderer` renders a `.ntp` project headless. |
| [Friction](https://github.com/friction2d/friction) | Vector and raster motion graphics: lower thirds, animated graphics | GPL-3.0 | External program. Headless render not yet verified. |
| Blender + [QuickTitling](https://github.com/snuq/QuickTitling) | Title scenes in Blender's sequencer, built from presets | GPL-2.0+ (addon, v0.6.8, Blender 5.1) | The user installs the addon. Cine Toaster only calls Blender. |

# Why

The user asked to record it (2026-09-29). Composed shots are drawn today as
Pillow cards (`build.py`); a real title, a composite, or a graphic has no path.
`toast doctor` already detects Blender and lists it as unwired.

# Constraints

- **ADR 0011:** all three are copyleft. They are run as separate programs and
  exchange files. None is vendored, submoduled, linked or copied, and no code
  is taken from them.
- A VFX or title step is a **step node** (CT-0023/CT-0024). Its output is a
  take with lineage: inputs, tool, version, and project file. It is never an
  in-place edit of a take.
- The tool's project file (`.ntp`, Friction's scene, `.blend`) is produced by
  the step and kept with the take, so the result can be reopened and re-run.
- Each tool is added to `toast doctor` only when something calls it.
- Natron's upstream has been largely inactive since 2.5 (2022); check its
  state again before investing.

# To do

1. Decide the first need from a real production: title, composite, or
   graphic.
2. Spike the matching tool headless: input files in, render out, project file
   kept.
3. Define the adapter contract and the step's record, after the jobs runtime
   (plan step 6) and the generation adapter (plan step 9).

# Decisions

- External tools only; no GPL code in the repository.

# Validation

- Licences checked from the repositories on 2026-09-29: QuickTitling
  `1c699e6` (GPL block in `__init__.py`) and Friction `138c85c`
  (`LICENSE.md`, GPL-3.0).
