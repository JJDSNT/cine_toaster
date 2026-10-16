---
id: CT-0102
title: Master pictures not bound to a model -- the adapter chosen by production, scene or shot
type: work
status: done
owner: claude-code
created_at: 2026-10-16
updated_at: 2026-10-16
tags:
  - providers
  - pictures
  - architecture
---

# What

ADR 0025: a `PictureProvider` interface; Qwen Image Edit and Codex behind
it; the adapter chosen by `pictures: {provider}` in project.yaml, a scene,
or `derive.provider` on a shot (the nearest wins, Qwen the default);
`derive.from` required only by an adapter that repaints.

# Why

The user (2026-10-16): "master pictures, by principle, should not be fixed
to Qwen; each initiative could change the model". `pictures.py` (Core)
carried Qwen's price, wording and size; Demo 01 (CT-0099), an animated film
with no render to repaint, could not make a master picture at all.

# Done

- `providers/__init__.py`: `PictureProvider`, `picture_providers()`,
  `DEFAULT_PICTURE_PROVIDER`.
- `qwen_edit.py`: the interface (needs a source, dollars, its estimate,
  `make` over `edit`); `edge_score` moved to `pictures.py` as the film's
  measure, still importable from the adapter.
- `codex_image.py`: the interface (no source needed, quota, `make` over
  `generate`; a source, when given, is image 1 to keep the composition of).
- `pictures.py`: `picture_provider()` cascade; `PicturePlan` carries
  provider, level, model, cost; source and size optional.
- `project.py`: `pictures` read at production and scene; `derive.provider`.
- `jobs.py`: the budget holds only `usd`; Qwen's remote job and spend path
  kept; other adapters write the version and its provenance only.
- `toast picture` names the adapter and level, and says quota instead of a
  price.
- Fixed on the way: `_derive` dropped `style`, so `derive: {style: false}`
  (docs/styles.md) never kept a source's look; it is carried now.

# Decisions

- Qwen stays the default: a production that says nothing behaves as before.
- The edge score is kept for any adapter when there is a source.
- No ADR for video: LTX stays bound until a second video model is wanted
  (roadmap).

# Validation

- Existing tests unchanged and passing: `test_pictures`, `test_avoid`,
  `test_board`, `test_workflows`, `test_mcp`.
- `tests/test_picture_providers.py` (3): the cascade (Qwen default refuses
  no `from`; production chooses Codex; a scene overrides back); an unknown
  provider named with its level; a Codex master made end to end by a job
  against a fake `codex` executable -- a version with provider, level, quota,
  thread, the cast's face sent as its reference, no dollars spent with a
  zero budget.
