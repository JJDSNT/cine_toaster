---
id: CT-0014
title: Evaluate OpenMontage and record what may be reused
type: work
status: done
owner: unassigned
created_at: 2026-09-22
updated_at: 2026-09-22
tags:
  - evaluation
  - licensing
  - boundaries
  - providers
---

# What

Read OpenMontage against Cine Toaster's needs, decide how its mechanisms may be
reused, and record both the licence boundary and the specific findings so the
question is not reopened from memory.

# Why

OpenMontage covers ground Cine Toaster will have to cover: style as data,
prompt construction from structured shot language, mechanical quality gates, and
a provider registry spanning fifty generation providers. It was cloned and run
end to end to find out what of it is worth having.

The reuse route considered first was a git submodule. That route had to be
resolved before any of the findings could be acted on, because it would have
settled Cine Toaster's licence as a side effect.

# Done

- Installed and ran OpenMontage end to end: Remotion render validated by
  `ffprobe` (1920x1080, h264 + aac, 30 fps, 25 s), offline Piper narration, and
  the full suite at 1828 passed.
- Read its artifact schemas, pipeline manifests, director skills, style
  playbooks, prompt builder, transition path, and scoring libraries.
- Established the licence position and recorded it as ADR 0011.
- Recorded the mechanisms worth reimplementing and the parts to leave alone.

# To do

- `CT-0015` — the `cast` entity: sheet, executable reference, and generation
  lineage.
- `CT-0016` — remove Portuguese from the schema, the two demo productions, and
  the documentation.
- A mechanical plan score, in the family of `toast check`, once `cast` and the
  format work have settled.

# Decisions

- **No OpenMontage source enters this repository** (ADR 0011). It is AGPLv3
  with no exception, Cine Toaster serves a web interface, and Cine Toaster has
  no LICENSE file. Reaching five YAML playbooks through a submodule would have
  attached sixty thousand lines of Python and decided the licence question by
  accident.

- **Reimplement, do not copy.** The structures are reusable and the files are
  not. Anything traceable to OpenMontage names the source and what was taken.

- **Worth reimplementing**, in order of value:
  - A mechanical plan score. `lib/slideshow_risk.py` scores six dimensions from
    0 to 5 — repetition, decorative visuals, weak motion, weak shot intent,
    typography overreliance, unsupported cinematic claims — and refuses to
    proceed at 4.0. It runs before assets are generated and again before
    composition. It is the same idea as `toast check`: a structural refusal that
    needs neither a human eye nor a model's judgement.
  - Prompts derived from structure rather than written per shot. Its builder
    composes five layers — camera, movement, subject, lighting, style — from
    enumerated shot language. Our breakdowns already carry the inputs.
  - Consistency anchors that belong to the style, not to the scene.
  - The anatomy of a style playbook as data: identity, visual language,
    typography, motion with pacing rules, audio, asset generation, quality
    rules. The shape is good; the five files are AGPL and ours must be written.
  - The capability-registry pattern behind the provider layer — discovery,
    declared cost, declared fallback — as the natural growth of CT-0012.

- **Not worth taking:**
  - Its Remotion transition layer. The schema advertises fade, dissolve, cut and
    wipe; the renderer reduces everything to an opacity fade against the scene
    background, computed independently per cut, so a dissolve is a dip to black.
    `@remotion/transitions` is a declared dependency that nothing imports and
    `TransitionSeries` appears zero times. Only its FFmpeg path does real
    `xfade`, and it exposes two transition types.
  - Its linear eight-stage pipeline, and its flat model where a scene is a
    single shot. Eleven of its thirteen pipelines share one spine and differ
    only in tools and skills.
  - Its handling of character continuity in generative work, which does not
    exist. No artifact holds a character: `required_assets` entries are free
    text, the asset manifest has no character id and no reference lineage, and
    the playbook has no character field. `character_design` is real but reaches
    only the rigged-animation pipeline, where identity is structural because the
    character is a rig. The guidance contradicts itself inside one file:
    `asset-director.md:118` says not to reuse the exact phrasing across images,
    and `:203` asks whether identity is anchored verbatim across shots.

- **The evaluation confirmed two existing decisions rather than challenging
  them.** CT-0008 recorded that the continuity model came from importing a real
  production rather than from design; OpenMontage designed instead, and has no
  continuity model. CT-0011's native-format decision holds, but it is the route
  by which Portuguese entered the schema, which is what CT-0016 addresses.

# Validation

- OpenMontage's own suite: 1828 passed, 12 skipped, 3 xfailed.
- Licence confirmed at `LICENSE:1` and `README.md:776`: AGPLv3, no exception,
  no dual licence.
- Claims about its behaviour were read from source, not from its documentation:
  `remotion-composer/src/Explainer.tsx:441`, `tools/video/video_stitch.py:616`,
  `lib/shot_prompt_builder.py`, `lib/slideshow_risk.py`,
  `schemas/artifacts/scene_plan.schema.json`,
  `schemas/artifacts/asset_manifest.schema.json`.
- No file from OpenMontage was copied into this repository.
