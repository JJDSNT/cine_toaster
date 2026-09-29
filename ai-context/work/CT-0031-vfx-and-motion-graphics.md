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

# Target experience

Effects and titles are **chosen from catalogs the same way transitions are**
(`docs/transition-library.md`); the user's direction, 2026-09-29. There are
two new catalogs, `effects` and `titles`, with the same shape as the
transition catalog:

- one manifest per item: id, name, category, description, guidance,
  `use_when` and `avoid_when`, energy, tags, licence and author;
- declared **parameters with defaults**, as shader uniforms are today. For
  titles these are text slots (headline, subtitle, name and role) plus colour
  and timing;
- a **preview** shown in a bank room, as the Transitions room shows its bank;
- **per-engine rendering declared by the item**, never inferred: for example
  `[render] natron = "project.ntp"`, `friction = "…"`, `blender = "…"`, and a
  declared fallback. An item with no rendering for the available engine is
  refused, not substituted, as transitions are;
- the same layering: built-in, external path, production, and a reviewed or
  unreviewed state for items imported in bulk;
- a shot records only the id, its parameter values and the reason for the
  choice (`effect: {id, params, reason}`, `title: {id, text, reason}`), and
  checks report unknown ids.

The external tools are engines behind these catalogs, like ModernGL and FFmpeg
for transitions. The user picks an effect, not a tool.

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

0. Generalise the transition catalog's loader (layers, manifest, params,
   per-engine render, reviewed state) so that effects and titles reuse it
   rather than copying it.
1. Decide the first need from a real production: title, composite, or
   graphic.
2. Spike the matching tool headless: input files in, render out, project file
   kept.
3. Define the adapter contract and the step's record, after the jobs runtime
   (plan step 6) and the generation adapter (plan step 9).

# Decisions

- External tools only; no GPL code in the repository.
- Effects and titles are catalog items chosen like transitions. The tools are
  engines, not the interface.

# Validation

- Licences checked from the repositories on 2026-09-29: QuickTitling
  `1c699e6` (GPL block in `__init__.py`) and Friction `138c85c`
  (`LICENSE.md`, GPL-3.0).
