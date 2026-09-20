---
id: CT-0012
title: Move the generation providers into the tool
type: work
status: done
owner: unassigned
created_at: 2026-09-20
updated_at: 2026-09-20
tags:
  - providers
  - boundaries
---

# What

First step of separating the tool from the film: the generation data plane moves
out of the production's script folder and into Cine Toaster, in English, behind
a capability boundary.

# Why

Singular is the film; Cine Toaster is the tool. About 70% of the production's
5,400 lines of scripts are tooling that knows nothing about the film, and
keeping it beside the film means every later production would start by copying
it.

This tier was chosen first because it has zero film knowledge, so it moves
without judgement calls, and because it is what makes Cine Toaster able to
generate rather than only decide.

# Done

- `providers/__init__.py`: `GenerationResult` with a namespaced provenance
  envelope, an `ImageToVideoProvider` protocol, and typed provider errors.
- `providers/runpod.py`: credentials, transport, and a persistent serverless job
  that survives an interrupted session.
- `providers/comfyui.py`: workflow patching by node type, image collection.
- `providers/ltx.py`: LTX 2.5 image-to-video with keyframes, identity LoRA and
  control video, plus the workflow graph as a shipped asset.
- `tests/test_providers.py` (28), all offline.

# Decisions

- **Only the data plane moved.** Reading `rp.py` changed the plan: 324 of its
  lines are control plane — data centres, GPUs, volumes, pods, endpoints — which
  runpodctl and the Runpod MCP already do. A film tool duplicating infrastructure
  management would be the same mistake as the exporter. It stays with the
  production as ops tooling.
- `sys.exit` became typed exceptions. A library that exits cannot be used by a
  server or an agent.
- The capability protocol has exactly one method, because exactly one capability
  exists. A wider interface written before a second provider would describe an
  imagined provider.
- The workflow JSON ships with the provider. Node ids are stable per file and
  change on re-export, so the file and the ids that index it belong together.
- Credentials are never logged or returned. A token was once exposed in a tool
  result on this production; the module is written so a caller gets a
  missing-key error rather than a value it might echo.

# Deliberate temporary duplication

`ferramentas/ltx.py` and `comfy.py` stay in the production and keep working,
because `cena_ltx.py` imports them and the film is in production. The duplicate
is removed when the orchestrator moves (tier 4), which also removes
`ferramentas/ct_state.py`. Recorded here so the duplication has a named end
rather than becoming permanent.

# Validation

- 140 tests passing, offline. The provider suite exercises graph assembly,
  keyframe wiring across both sampling passes, the resolution the control LoRA
  forces, video detection by file header, and every branch of job persistence:
  fresh submit, resume, refusal to resend a different request, a vanished job,
  a failure reported inside a successful response.
