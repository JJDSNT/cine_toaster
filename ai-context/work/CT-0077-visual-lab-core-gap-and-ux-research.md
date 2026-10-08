# CT-0077 — Visual Lab: Core gap and UX research

Status: research, 2026-10-08. UX-first; no feature/schema approved. Related CT-0066–73, CT-0076.

## Goal

Evaluate a Visual Lab for early visual decisions tested across representative locations. The product is a complete variable filmmaking pipeline; Blender, Unreal (planned), ComfyUI and image/video models are possible resources, not mandatory stages or UI organizing principles.

## Verified Core findings

- `src/cine_toaster/looks.py`: look YAML sections include palette, motion, generation, grade, rules; resolver uses project/sequence/scene/shot precedence and reports origin. This supports a visual contract but does not itself constitute an approved production-wide baseline.
- `src/cine_toaster/styles.py`: separate direction, technique, format axes with style definitions and reference vocabulary. Do not conflate authorial manner, scene mood and image texture.
- `src/cine_toaster/state.py`: `SceneState.approved_pictures` resolves per-shot approved picture gates; decisions and append-only scene decision journal exist. They are not automatically project-wide visual approval.
- `src/cine_toaster/project.py`: effective scene/shot references and approved pictures appear in the production view.
- `src/cine_toaster/providers/qwen_edit.py`: image edit adapter uses source and identity references, prompt, seed and size; its job is not an arbitrary model comparison system.
- `tests/test_pictures.py`: plate-based master-image derivation and versioning are tested.

## UX hypothesis

A dedicated Visual Lab **activity/space** may be justified, but its place in top-level navigation remains a design decision. Start with task-based prototype, not a fourth permanent workspace by assumption.

1. Choose representative conditions (not only named locations): interior/exterior, artificial/daylight, character/empty set, surface/material, spatial continuity and distinct narrative moods.
2. Define authorial language, shared visual characteristics, per-scene moods and intentional exceptions separately.
3. Run model/workflow candidates with traceable inputs and note controls that cannot be made equivalent.
4. Compare candidate master images side by side, with provenance and perceived mood/texture/continuity assessments.
5. Approve an **evolving visual baseline** (intent + references + representative images + scope), not necessarily a single model.
6. Show downstream impact before changing the baseline; preserve revisions and user authority.

## Important distinction

Per-shot picture approval answers 'is this image acceptable for this shot?'. A production visual baseline answers 'what visual identity should guide future shots?'. Existing scene gates cannot simply be relabeled as film-wide approval. Investigate reuse/extension of existing looks, style and decision machinery rather than duplicating it.

## Candidate test matrix

| Scenario | Spatial input | Mood challenge | Pipeline comparison |
| --- | --- | --- | --- |
| Claire's room | integrated Blender hospital | intimate, oppressive artificial light | Codex vs Qwen master |
| Hospital corridor | same spatial model | shared texture but different dramatic mood | cross-location continuity |
| Geneva exterior | hospital exterior and surroundings as needed | natural light and urban scale | indoor/outdoor coherence |
| Boreal station | optional 3D or 2D references | snow, polar light, isolation | portability beyond hospital |

These are **proposed test conditions**, not claims of existing approved assets. Do not require a full 3D Geneva or Unreal deployment to test the lab.

## Open gaps to investigate

- How project-level visual baseline approval, scope, exceptions and revision history could reuse existing Core concepts.
- Whether candidate experiments and their full provenance are already captured in job metadata.
- How to trace dependency from approved baseline to master images, derived videos, VFX and edit; avoid false precision in impact counts.
- How model capabilities, settings and spatial conditioning differ across providers.
- Whether a Visual Lab is a permanent workspace, preproduction activity or contextual tool within existing workspaces.
- How users can intentionally choose divergent moods without false continuity warnings.

## Research acceptance criteria

Prototype with a new production and an established production; validate exploration, approval, exception and revision tasks. Test with and without 3D references and with at least two image models. Preserve stable navigation and progressive disclosure. Document findings before implementation or an ADR.
