# Terrain generation in the Cine Toaster Toolbelt — research proposal

Status: **research / candidate capability**, not an implementation commitment.
Scope: optional procedural terrain generation for cinematic environments, previs, storyboards and DCC/render workflows.

## Intent

Enable Cine Toaster agents and filmmakers to request, refine, inspect and export reproducible terrain assets through the existing Toolbelt/job/asset infrastructure. Cine Toaster owns cinematic intent, provenance and orchestration; specialized terrain tools own erosion and terrain algorithms. Do not make Blender, Unreal, a terrain engine, or an MCP server mandatory dependencies.

## Candidates to evaluate (not yet validated in this repository)

| Candidate | Possible role | Questions to validate |
| --- | --- | --- |
| Hesiod (Otto Link) | Headless external provider; graph/recipe-based terrain generation | CLI/batch interface, file formats, determinism, Linux availability, maintenance, licensing and asset terms |
| LibreTerrain | External provider, potentially agent-controlled via MCP | Existence/maturity of releases and MCP protocol, actual export options, performance, licensing, reproducibility |
| HighMap | Algorithm library or subprocess backend | Licensing ambiguity, ABI/build integration, isolation vs embedding, erosion quality |
| TerraForge3D | Alternative external generator | Scripting/automation, maintenance, supported platforms, output compatibility |
| QuadSpinner Gaea | Optional proprietary provider | Commercial automation terms, headless execution, output limits, supported platforms |
| Blender / Unreal native terrain tools | Consumers and possible generation alternatives | What can be produced natively; import, scaling, camera consistency and export automation |

Do not infer feature parity from feature lists or commit to a provider based on documentation alone. Reconfirm upstream project status, licenses, automation APIs, and output terms at implementation time.

## Proposed capability surface (names illustrative, not an existing API)

- `terrain.providers`: discover installed providers and supported capabilities.
- `terrain.generate`: request terrain from seed, scale, elevation, features and recipe.
- `terrain.inspect`: report bounds, resolution, height range and artifacts.
- `terrain.refine`: revise recipe or provider-native graph without losing provenance.
- `terrain.preview`: create a lightweight visual preview.
- `terrain.export`: produce portable heightmaps, masks and optional mesh.
- `terrain.validate`: check units, format, dimensions, missing data and consumer compatibility.

Prefer extending the actual Toolbelt/provider/job interfaces over introducing a parallel execution framework. Treat this as a design sketch until current code contracts have been reviewed.

## Portable artifact contract (candidate)

Inputs: provider or `auto`, versioned recipe, seed, dimensions in metres, resolution, vertical range, requested outputs and optional artistic constraints. Preserve provider-native projects/graphs as source artifacts.

Outputs: 16-bit heightmap or float EXR (verify precision/normalization and Unreal import compatibility), material/slope/erosion masks, preview, optional mesh (glTF/OBJ/USD where supported), plus metadata: provider/version, seed, recipe hash, units, origin, axis orientation, elevation datum, extent, license, source paths, timestamps, checksums, job ID and regeneration instructions.

A heightmap cannot express overhangs/caves: support mesh geometry as a separate capability, not as an implicit heightmap promise. USD and material fidelity across DCCs require explicit validation; no assumption of pixel-identical results.

## Proposed validations / acceptance experiments

1. **Repository fit:** inspect active development branch and actual Toolbelt/provider/job/asset/MCP contracts; identify extension points and avoid duplicate concepts.
2. **Provider smoke tests:** install and execute Hesiod and LibreTerrain independently; verify documented automation, headless operation, errors, resource usage and real outputs.
3. **Comparable fixture:** generate a mountain with a usable summit, valley and erosion at a fixed seed and physical extent; record versions, time, memory and disk use.
4. **Repeatability:** run the same recipe twice on the same version; compare hashes or numeric height tolerances; never promise cross-provider identical results.
5. **Interchange:** load outputs into Blender and Unreal Landscape where applicable; verify scale, coordinate system, height normalization, masks and camera placement. Validate mesh path separately.
6. **Cinematic proof:** use the animation demo's summit/orbit-camera idea to test spatial previs against rendered frames, without requiring character animation in Blender or Unreal.
7. **Agent safety:** capability discovery, explicit permissions for execution, bounded CPU/GPU/memory/disk, cancellation, timeout, error reporting and no unauthorized paid remote generation.
8. **Tests:** mocked unit tests without provider binaries; opt-in real integration tests; provenance and regeneration regression tests.
9. **Licensing:** independently verify code licenses, redistribution rules, asset/output restrictions and compatibility with commercial productions.

## Suggested sequencing

- P0: inspect existing contracts, verify upstream projects and licensing, define a minimal artifact schema and one deterministic fixture.
- P1: prototype one *external headless* provider (Hesiod candidate, conditional on smoke test); register with diagnostics and existing jobs.
- P2: prototype LibreTerrain/MCP if its protocol and builds are verified; compare ergonomics, quality and output.
- P3: optional HighMap/TerraForge3D/Gaea and Blender/Unreal-specific automation; avoid prematurely implementing a native terrain engine.

## Open decisions

- Which existing Toolbelt module and manifest own this capability?
- Which artifact format is canonical: EXR float vs integer heightmap, and what is the unit/axis contract?
- Do agents operate on semantic recipes only, or also provider-native node graphs?
- What constitutes an acceptable terrain preview and artistic review loop?
- How are large tiled terrains and disk budgets handled?
- What are the exact distribution and commercial-output license constraints for each provider?

This document records intent and a validation backlog. **No provider has been selected or integrated.**
