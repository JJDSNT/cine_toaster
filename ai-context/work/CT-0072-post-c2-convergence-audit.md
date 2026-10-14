---
id: CT-0072
title: Post-C2 convergence audit -- competing compositing paths and duplicated decisions
type: work
status: done
owner: unassigned
created_at: 2026-10-14
updated_at: 2026-10-14
tags:
  - compositing
  - architecture
  - audit
---

# What

The audit the user asked for before C2 is treated as closed (2026-10-14):
C2's purpose was to eliminate competing implementations of the same
cinematic capabilities, not only to add a graph. 700 passing tests show the
covered behaviour works; they do not show the old paths are gone. This record
inspects the code for (1) operations still executed outside the graph, and
(2) -- the user's addition -- **decisions** made in more than one place, even
where the code differs legitimately: two renderers may draw `warp.surface`
differently, but neither may decide on its own how a recipe is read, what a
parameter defaults to, or how a picture is fitted to the frame.

C3 was paused at its first commit (`c1facca`) for this.

# Method

Searched the source outside `compositing/` for FFmpeg compositing filters
(`xfade`, `alphamerge`, `overlay=`, `blend=`, `geq`, `colorkey`, `lut3d`,
`drawtext`, `crop`/`scale`/`pad` used to place pictures), GL contexts, PIL
drawing of film pictures and preview shaders; and inside `compositing/` for
parameter defaults and derived values written in both renderers.

# Findings

## C2 blockers -- duplication that contradicts C2

| # | Where | What | Smallest correction |
|---|---|---|---|
| B1 | `assembly._join_pictures` -> `build._shader_join` -> `shader_render.ShaderTransition` | gl-transitions shaders run by a **second GL pipeline**, outside the graph: its own context, 8-bit display-encoded RGB frames read through pipes, flipped; orchestrated by the assembly, not the executor | The GL renderer runs `opaque.gl` itself (the shader's source in its pipeline, float textures); the assembly draws a shader join as a graph with an `opaque.gl` node. Opaque shaders were authored for display-encoded pictures, so the node converts to the display encoding and back around them, declared in SPEC-0012. |
| B2 | `compositing/reference.py` and `compositing/gl.py` | **Duplicated decisions**: defaults written in both (`warp.surface` perspective 35, light 0.4, detail 48, supersample 2; `mix` 1; `low`/`high`/`gamma`); the threshold's softness floor 0.002 in both and in `mattes.py`; blur's radius-to-sigma and kernel reach in both | Defaults declared once with the ops in `schema.py` and read by both renderers; the derived values (`threshold_spread`, `blur_kernel`) as functions in one module, used by both and by `mattes.py`. A test that both renderers read them. |
| B3 | `reference.read` vs `assembly.render` | **Duplicated decision on fitting a picture to the frame**: the assembly letterboxes (`scale ... decrease, pad`), the reference stretches to the frame (`scale=W:H`), so a take of another aspect is distorted in a composite and not in a cut | One conform rule in the frame-access layer (`compositing.reference.conform_filter`), used by both: fitted within the frame, centred, the rest transparent in a composite (black in a cut). A test with a 4:3 take in a 16:9 frame. |
| B4 | `web_assets/app.js` `MATTE_SHADER`, `sampleMatte` | The Transitions room previews `matte` items with **its own** GLSL copy of the threshold rule | `matte-wipe`'s preview made by the graph (`mattes.recipe`) like every recipe's, played as a clip; `MATTE_SHADER` removed. (Previews of gl-transitions shaders run the shader's own source: legitimate, L3.) |

## Removable legacy code

| # | Where | Why it can go |
|---|---|---|
| R1 | `build.py` (`toast build`, the `build` job kind, `draw_card`, `_concatenate`, `_assemble`), `tests/test_build.py`, its mentions in `docs/jobs.md`, `docs/transition-library.md`, `README.md` | A third way to make pictures and joins: PIL cards, its own `xfade` chain, its own shader joins. Superseded by the assembly (`assemble-sequence --scenes`, which `make build` already uses); nothing in the control room or MCP starts it. CT-0065 left "keep or remove" open: remove. |
| R2 | `shader_render.ShaderTransition` and `build._frames` / `_shader_join` | Used only by B1 and R1. After them, only `gl_unavailable_reason` remains, moved beside the GL renderer. |
| R3 | `tests/test_shader_render.py` | Tests R2; replaced by conformance of `opaque.gl` in the GL renderer. |

## Planned migration -- kept, with an owner and a stage

| # | Where | What | Owner, stage |
|---|---|---|---|
| P1 | `vfx.py` (`_chain`: grain, vignette, light leak, glitch, shake; element laying with `colorkey`/`overlay`) | Effects drawn by FFmpeg chains, duplicating filter, key and merge | C6: effects re-expressed as recipes; element effects as layers with a matte |
| P2 | `titles.py` (`drawtext` effects, Blender letters) | Titles drawn by FFmpeg and Blender | C6 and C6b (typography) |
| P3 | `assembly._draw_title` | Calls P1 and P2 over takes and composites | C6, with them |
| P4 | `assembly` FFmpeg `xfade` stand-ins (`[render].ffmpeg` modes) | A declared, reported substitute for a shader when GL cannot run | C5: when a reviewed item is re-expressed as a recipe its stand-in goes; until then each use is said in the version's notes |
| P5 | `formats.reframe_filter` (`crop`, `scale`) | A format's reframing: a crop and scale, i.e. a warp | C10, delivery: a `warp.transform` in the graph |
| P6 | `color.bake_look` + `media/grading.py` (`lut3d`) | A production's look applied by FFmpeg | C6: `colour.lut` in the graph |

## Legitimate backend specialisation

| # | Where | Why it is legitimate |
|---|---|---|
| L1 | `compositing/reference.py` and `compositing/gl.py`, op by op | Two drawings of the same op, sharing geometry (`transform_corners`, `surface_mesh`), curves (`curve_factory`) and, after B2, defaults and derived values; held together by the conformance tests |
| L2 | `reference.read` / `write` (FFmpeg decode and encode) | Frame access, not compositing |
| L3 | Preview of gl-transitions shaders in WebGL | Runs the shader's own source, the same program `opaque.gl` runs |
| L4 | `board.py` (PIL) | Draws storyboard boards, not film pictures |
| L5 | `assembly` still holds and audio laying | Frame access and sound, not picture compositing |

# Done

1. **B2** -- `compositing/semantics.py` holds the defaults (`DEFAULTS`) and
   derived values (`threshold_spread`, `blur_kernel`); both renderers and
   `mattes.recipe` read them; their literals are gone.
2. **B3** -- `reference.conform_filter` fits a picture within the frame,
   centred (transparent around in a composite, black in a cut), used by
   `reference.read` and the assembly's held stills.
3. **B1** -- the GL renderer runs `opaque.gl` (the shader's source with the
   gl-transitions host, display-encoded in and out, not flipped); the
   assembly draws a shader join as a graph (`shader_recipe` -> `_graph_join`);
   identity hashes the shader file and texture ports.
4. **R1-R3, with the capability kept** (the user, mid-way: "eliminate the
   competing execution path, not a useful capability"). Tracing every caller
   showed `toast build` was the only thing that drew `engine: text` cards and
   wrote the stills of composed shots. Before removing it:
   - cards became graphs (`cards.py`: the look's background, each line as
     `generate.text`, merged over), assembled like any composite;
   - a still became the graph at an instant: `assembly.still` (and
     `toast still <project> <scene> <shot> [--at s]`) uses the same frame,
     rate, starts, beats, inputs and renderer choice as the cut
     (`_source_frame`, `_starts`, `_composite_pictures` were factored out of
     `render` so neither can drift); the scene assembly keeps each graph-drawn
     shot's middle frame as its still (taken from the frames it draws, not a
     second drawing), adopted to `stills/<scene>/<shot>.png` as a derived file
     that replaces the last;
   - showing a frame has one rule (`reference.shown`) for a film and a still.
   Then removed: `build.py`, `shader_render.py`, the `build` job kind,
   `toast build`, `tests/test_build.py`, `tests/test_shader_render.py`.
   `gl_unavailable_reason` moved to `compositing/gl.py`. The catalog test that
   reviewed items declare a stand-in moved to `test_transitions.py`. CLI,
   jobs, MCP, the control room, docs and specs were searched: no caller left.
5. **B4** -- `matte-wipe` has a `preview.webm` drawn by
   `transitions.render_preview` from `mattes.recipe` with a sample matte; the
   Transitions room plays it; `MATTE_SHADER`, `sampleMatte` and the softness
   uniform are gone from `app.js`.
6. **Documented** -- ADR 0022 §5 (convergence) and Consequences; SPEC-0012
   (`opaque.gl` contract; frames in and out: conform, display, still);
   SPEC-0007, -0008, -0011; the compositing roadmap (convergence in every
   step's "done when", owners P1-P6, C2 closed after this, the still's limits
   in C10); `docs/transition-library.md`, `docs/jobs.md`, the reel's README.

# Remaining (owned elsewhere)

P1-P6 above, with their steps. Limits introduced here, in the roadmap's C10:
a still inside a join (the sequence's instant), titles/effects over a
composite missing from its still until C6, a still's cost growing with its
instant, a still of a take-cut shot, and the Renders room, which nothing
writes now.

# Decisions

- **Decisions count as duplication**, not only code (the user). A renderer
  may differ in how it draws; it may not differ in what a recipe means.
- **Opaque shaders run in the display encoding**: they were written for it,
  and running them on linear light would change every one of them silently.
- **A still is the cut's frame**, not a re-drawing: the graph at an instant,
  with every decision the cut makes (the user).
- **Cards are centred**: `generate.text` places a line by its centre; the
  quick build's left-aligned layout was not kept.
- A still is a derived file: adopting a new one replaces the last without
  asking (`derived` on a job's file), unlike a version.

# Validation

- `tests/test_convergence.py`: defaults read once (both renderers follow a
  changed default), conform never stretches, `opaque.gl` mixes in the display
  encoding at each frame's centre and keeps the picture's top, the quick
  build and its job kind are gone, the browser holds no matte rule, a matte
  preview is drawn by `mattes.recipe`.
- `tests/test_stills.py`: a card is a graph of the look's colours; a still at
  three instants of a card and a moving composite matches the assembled
  cut's frame at the same instant on three bounds (the user asked that a
  global mean not hide a local divergence): mean under 2/255 (measured 1.3;
  one frame off on the moving shot is 3 to 7), every 10x10 region under
  6/255 (measured 4.6), every pixel under 32/255 (measured 24, on letter
  edges, from H.264's colour subsampling); the stills the cut keeps match
  `still` at the middle; a take-cut shot is refused.
- The removal is tested, not only the replacement: `build.py` and
  `shader_render.py` are gone, `build` is no job kind, `toast build` is
  refused by the CLI.
- Every reference to the removed paths searched (`git grep` for `toast
  build`, `shader_render`, `ShaderTransition`, `draw_card`, `_shader_join`,
  `BuildCancelled`, the `build` job, `--engine`): none executable in `src/`
  or `tests/`; the rest are history in closed work records, left as they
  are; the open records (CT-0064, -0065, -0069) say it was removed.
- The Renders room had lost its producer: it now shows each sequence's
  latest version, and says what will appear when there is none.
- A still says when a title or effects over its composite are missing from
  it (`toast still` prints the note); the documentation does not present it
  as the final picture for those shots.
- On the music piece: `toast still ... SC-030 P1 --at 2.0` drew the inset
  over the Earth (about a minute: the cost limit recorded in C10).
- Full suite: 704 tests pass (2026-10-14), after every change above.
