---
id: CT-0073
title: Surfaces from Blender -- an external UV mesh for warp.surface (proposed)
type: work
status: ready
owner: unassigned
created_at: 2026-10-14
updated_at: 2026-10-15
tags:
  - compositing
  - warp
  - blender
---

# What

The user's idea (2026-10-14): model the *shape* of a deformation in Blender
-- a page curling, a flag, a curved screen, an organic surface -- and apply it
in Cine Toaster to playing footage through `warp.surface`, without rendering
the video in Blender:

    Blender: mesh + UVs (+ optional animation) -> exported geometry
    -> warp.surface: projection, remapping, deformation
    -> the graph: video + matte + merge + other effects

Only the **geometry** is reused. Materials, lights, particles and simulations
are a different integration: Blender rendering a picture, which is
`generate.render` / `opaque.blender` (SPEC-0012) and C8-C9. Asked for now:
evaluate, and document the interface, **without widening C2** (closed by
CT-0072) or building it before its turn.

# What the implementation supports today (checked in the code)

| Question | Today | Where |
|---|---|---|
| Arbitrary geometry? | **No.** Four parametric shapes (`plane`, `sphere`, `cylinder`, `page`), generated as a regular grid of `detail` cells | `warp._surface_points`, `surface_mesh` |
| UV coordinates? | **Implicit only**: each grid vertex's (u, v) is its own place in the picture, origin top left. No UVs of its own; UVs outside 0..1 cannot occur | `surface_mesh` |
| Hidden faces, overlap | A **depth buffer**: the nearest face wins, in both renderers. No back-face culling: a face turned away shows the picture from behind (a tube shows its inside) | `_rasterise`; GL `DEPTH_TEST` |
| Animation | **Parameters over time** (morph, rotate, translate, scale are curves): the mesh is rebuilt every frame from them. No vertex animation | the renderers call `surface_mesh` per frame |
| Camera, projection, depth | One pinhole camera on the axis, looking at the picture's centre; distance from `perspective` (vertical field of view, degrees) with the picture one unit high; a `depth` signal out (distance per pixel), named by `camera` for `merge.depth` | `surface_mesh`; SPEC-0012 `warp.surface` |
| Light | `light` darkens faces turned from the camera, from normals estimated on the grid | `surface_mesh` |

What makes an extension cheap: both renderers already draw the **same mesh
description** (`surface_mesh` returns per-vertex screen x, y, depth z, u, v
and shade; the reference rasterises it, GL draws it with a depth test). Only
the **topology** is assumed: both walk a `rows x columns` grid into
triangles.

# The interface (proposed, not built)

**Step 1 -- a static UV mesh** (what the user suggested starting with):

- `warp.surface` gains `shape: mesh` and a `mesh` parameter (type `file`,
  so its identity is its content, as every file parameter's is already).
- The file is **glTF 2.0 binary (`.glb`)**: Blender exports it natively
  (`export_scene.gltf`, GLB, selected object), it carries positions,
  triangle indices, normals and `TEXCOORD_0`, and later shape keys,
  animation and cameras -- one format for every step. OBJ was considered:
  static only, so a second format later.
- Read: one mesh, one primitive, triangles; its `TEXCOORD_0` is the place in
  the picture (glTF's UV origin is top left, as ours; Blender's exporter
  flips from its own bottom-left). A mesh without UVs, with more than one
  primitive, or over a vertex budget is refused when the scene loads, with
  the reason.
- Space: the mesh's units are picture heights, its origin the picture's
  centre, +y down the picture, the camera on -z looking at +z -- the space
  the parametric shapes already live in -- so `rotate`, `translate`, `scale`,
  `perspective`, `light` and `depth` keep their meaning on a custom mesh. The
  Blender side is told this convention (a note and, later, an export script
  under the Blender adapter).
- `morph` on a mesh: 0 is the flat picture (each vertex at its UV), 1 the
  mesh; the bend in between is a linear blend -- the same contract as the
  parametric shapes.
- UVs outside 0..1 read the picture by an `edge` parameter (`transparent`,
  `extend`, `mirror`), as `warp.displace` and `warp.procedural` do. Several
  faces may share UVs (the same part of the picture twice). A new `faces:
  both | front` (default `both`, today's behaviour) culls faces turned away.
- Both renderers move from a grid to **indexed triangles**; the parametric
  shapes become meshes made in code, so there is still one mesh path.
  Conformance: the same `.glb` drawn by the reference and GL, compared as
  the other warps are.

**Step 2 -- animation**, after step 1 is in use:

- **Shape keys** (glTF morph targets): `morph` drives the first key's weight
  -- a page modelled flat and curled in Blender, turned by a curve in Cine
  Toaster, in time with the music (C3). Further keys by name, each a curve.
- **Baked vertex animation** (a cloth flag, a simulation): sampled at the
  composite's frame rate, Blender's frames mapped to seconds by its rate;
  Alembic considered against glTF's per-frame morph targets when it is built.
- **The file's camera** (`camera_from: mesh`): the glTF camera's field of
  view and placement instead of ours, so a shape framed in Blender is seen
  in Cine Toaster as it was there.

# Where it goes

After C3 (curves drive `morph`) and C4 (layers carry a warp), as C5b in
`development/compositing-roadmap.md`. It needs no planner (C9): the mesh is
data read by both renderers, not a Blender run.

# Decisions

- Geometry only; Blender's renderer is another integration (the user).
- glTF binary, one format for static, shape keys, animation and camera.
- The parametric shapes become code-made meshes: one mesh path, not two.

# Validation

- Findings above read from `compositing/warp.py`, `compositing/gl.py` and
  `compositing/schema.py` on 2026-10-14. Nothing built.
