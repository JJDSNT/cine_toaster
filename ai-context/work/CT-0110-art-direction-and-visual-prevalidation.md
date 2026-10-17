---
id: CT-0110
title: Art Direction and independent visual prevalidation
type: work
status: review
owner: project
created_at: 2026-10-16
updated_at: 2026-10-16
tags: [agent-runtime, art-direction, visual-review]
---

# What

Add Art Direction and Visual Prevalidation roles to the existing public
LangGraph CoAgent. Develop versioned visual briefs from Inception, generate
candidates through existing jobs after explicit quota confirmation, inspect
actual image inputs and retain criterion-based findings separately from human
approval. Surface the records in the existing Creation situational GUI.

# Why

The director requested a creator/reviewer pair: polished material must serve
the film's intention and pass explicit checks, including age/identity continuity,
instead of relying on attractive output or self-approval.

# Done

- Implemented retained briefs, criterion-based reviews, pinned image evidence,
  optimistic revision/material checks, stale-review and human-request invalidation
  in the existing Creation journal and shared HTTP/Core operations.
- Added same-CoAgent Art Direction tools, separate visual reviewer calls,
  per-attempt quota interrupts, bounded generations/reviews, real existing job
  waits and non-overwriting adoption. Unsupported vision stops visibly.
- Codex CLI receives initial raster attachments in its disposable model request;
  shell/browser/filesystem image tools remain disabled. Other adapters are
  explicitly text-only in this slice; doctor reports this capability separately.
- GUI shows retained briefs, visual findings and stale state without authoring
  forms; existing human review remains separate.
- Added ADR 0030 and SPEC-0016, model/boundary/production-agent documentation,
  optional visual capability reporting in doctor and provider-independent routing.
- Real CoAgents/HTTP/browser acceptance passed on a disposable film with a
  synthetic model/raster: actual attachment transport, saved review, human gate,
  record refresh, reload and mobile. Evidence:
  `/tmp/cine-toaster-art-agents-cjh6gtyu/`.
- Inspected the existing roles, Creation journal, generation jobs, adoption,
  provider adapters, UI interrupts and canonical human review boundaries.
- Verified installed Codex CLI supports initial `--image` attachments; consulted
  official CLI documentation. Visual review must fail honestly on text-only
  adapters, not infer pixel findings from prompts or metadata.

# To do

1. Director to exercise the conversational/artistic experience on real material;
   do not modify/approve Demo 01 or generate its images during validation.
2. Separate follow-ups: durable job-completion agent resume, additional visual
   model transports and specialised reference research, only as production needs.

# Decisions

- No new provider selection, scheduler, worker queue or production engine.
- Visual prevalidation is advisory, never a human gate or an objective quality
  certification. Findings identify evidence, criteria, uncertainty and fixes.
- Preserve all briefs, candidate images and review attempts. No deletion,
  automatic master selection, canonical screenplay replacement or WAN changes.
- Generation costs quota and requires the existing interactive confirmation
  mechanism. Implementation permission is not consent to generate Demo 01 media.
- Existing job runtime owns long-running generation; bounded agent waits may
  leave a genuinely running job visible, with explicit continuation limits.

# Validation

Nineteen art tests passed, including criteria enforcement, real job/adoption,
quota refusal, changed-plan refusal, staleness, provider limitations and independent
review context. A live current-provider call correctly identified a red circle
from a synthetic raster attachment with image tools disabled. It verifies transport,
not artistic review quality, and used no image generation/real-film material.

Initial 14 art tests passed after correcting the synthetic generation fixture's
missing provenance (the real job runner requires it). The early full regression
started before that fixture correction; do not report that run green. Later
edge tests are being validated separately. Frontend tests and build passed.
Real inference/image generation is not implied by passing contract tests.

- Final focused regression passed twice (109 tests); final graph/visual-node
  checks passed all 19 art cases. Browser acceptance repeated after final target
  versus comparison-image linkage: `/tmp/cine-toaster-art-agents-kbpnarox/`.
- Existing Inception human-direction browser regression passed after the art
  changes: `/tmp/cine-toaster-inception-agent-a34q8ftf/`. Read-only actual Demo 01
  GUI/mobile/assistant inspection passed: `/tmp/cine-toaster-creation-live-go3ldgka/`.
- `toast doctor` reports visual transport available with explicit inference/login
  caveat. Final GUI and assistant info both returned HTTP 200 through Windows LAN.
- First full run: 1144 tests in 610.9 seconds, one failure from the earlier
  fixture lacking `generation` provenance. Its real job correctly refused the
  malformed fixture. Corrected fixture and final complete run passed (below).
- Demo 01 listener was absent at activation (`Connection refused`, no server
  process / 8787 listener). Announced and started one server, no process killed.
  It hosts the new graph with `codex-cli`, prints the same Windows LAN URL and
  detects its forwarding. GUI and assistant info both return HTTP 200 via LAN.
  Revision 6 / source digest remain
  `bf256fe23c37e42403aa62041b4af86f99da0dd123b67b8d69d270cfb529dfc2`;
  the prior pending assessment stays pending. No creative approval or film image
  generation occurred. No further server restarts planned for this slice.

## Final validation

- Full regression passed: **1149 tests in 598.4 seconds**, including all 19 art
  tests, the real reference-job integration and all existing heavy adapters.
  `PYTHONPATH=src .venv/bin/python tests/run.py -j 4`.
- Final focused runs: 109 passed; frontend five test files and production build
  passed (existing chunk-size / inlineDynamicImports warnings remain).
- Actual CoAgents browser acceptance, independent attachment transport, retained
  review/human gate, reload/mobile and existing Inception continuation passed.
  Current Codex CLI visual-input smoke passed on a synthetic image. No real-film
  visual quality, external research or generated-film-image quality is claimed.
- Demo 01 GUI + assistant info verified HTTP 200 through the Windows LAN URL;
  real-film GUI inspection read-only passed. No Windows rules changed in this slice.
- `git diff --check` passed. Server is left active; no further restart required.
