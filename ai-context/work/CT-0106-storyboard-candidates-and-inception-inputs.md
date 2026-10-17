---
id: CT-0106
title: Reviewable storyboard candidates linked to screenplay shots and Inception inputs
type: work
status: review
owner: codex
created_at: 2026-10-16
updated_at: 2026-10-16
tags: [storyboard, gui, provenance, demo-01]
---

# What

Implement the missing storyboard-candidate write/read path, then populate Demo
01's opening three shots with actual draft drawings so the director can review
Inception and Screenplay & Storyboard as connected screens. Preserve all older
images and clearly expose the remaining 21 shots without candidates.

# Why

The current pilot finds zero shot stills for 24 proposed shots. Concept studies
and six clay compositions are not a visual storyboard. The director authorised
advancing here to evaluate the two screens (CT-0103/0104/0105).

# Done

- Audited screenplay coverage, still discovery, reference snapshots, candidate
  journals and human gates. At the start the GUI read discovered final/composed stills,
  but had no storyboard-candidate association operation.
- Scope chosen: first complete vertical slice is Wake (SC-010 P1/P2/P3), not
  an assertion that the whole film's storyboard is complete.
- Generated and visually inspected three opening draft drawings using the
  built-in image tool, retaining its original outputs. They remain unreviewed
  by the director and are not designated as masters.
- Implemented and tested shared Core/CLI/HTTP import/read operations, MCP tools
  and bounded Agent Runtime reads; the GUI previews retained drawings with
  ordered thumbnails, exact-version URLs, drift findings and input/use links.
  Discovered stills and 3D composition remain separate.
- Imported three SC-010 drawings into Demo 01 through the application command.
  Prompts, actual input image hash and original output paths are retained;
  generation used the built-in tool outside a Cine Toaster job, explicitly
  disclosed. No provider model/cost was reported or invented. Verified 66
  existing production files unchanged; the 13 reference records remain intact.
- Inception manual candidate/generation/round forms and input-editing controls
  are removed following the director's correction; the GUI is situational for
  the person, not an authoring form surface for the AI. Opening a saved
  candidate now shows read-only content. Copilot-first concept actions
  and readiness assessment remain follow-up requirements, not delivered here.
- Fixed a real visibility gap: the normal Control Room Storyboard only read
  final stills and wrongly appeared empty while the pilot held three drawings.
  It now reads the same candidate journal, distinguishes drafts from stills,
  and links to exact versions beside the screenplay. No Core rewrite or
  copies into final-still paths; no additional generation started.

# To do

1. Final director clarification: three populated opening shots are sufficient
   for review; do not generate the remaining 21. Clearly point to SC-010
   P1/P2/P3 and integrate the normal storyboard entry point. Remove manual
   authoring forms from Inception instead of merely collapsing them.
2. Continue concept actions/readiness and later master handoff only as focused
   follow-up slices. Preserve the existing take/assembly lineage paths.

# Decisions

- The director clarified that the GUI is a situational tool for the human:
  agents perform work through operations; the person reviews and enters at
  explicit approval/rejection gates with direction. The earlier response
  mistakenly proposed completing all shots; that proposal is superseded.
  Three opening drafts suffice when clearly located. No further generation
  was started. Remove authoring forms, preserve agent commands and all records.
- A storyboard candidate is neither a master image nor an approval. Use a
  separate project-owned journal/assets, not copies into the discovered-still
  folder to simulate integration. Do not rewrite screenplay/scene manifests.
- Freehand story drawings do not require a blockout or a final face choice.
  Composition studies remain an explicitly separate view.
- Keep dense provenance collapsed and do not add a primary manual-entry form;
  CLI/HTTP/MCP/copilot reads use shared commands. The broader copilot-first
  authoring and cross-module decision inbox remain CT-0105 follow-up work.
- No new paid API provider, automatic gate decision or destructive operation.
- Director refinement is recorded in CT-0105: theme-oriented concepts with
  evolve/reject actions, destination-specific readiness for script/storyboard,
  fewer primary forms, and an understandable later path through 3D composition,
  shot masters and stills. This slice must keep those roles distinct; it does
  not implement that entire journey or infer creative approval.

# Validation

- Eight storyboard Core/CLI/HTTP tests passed: immutable inputs/versions,
  concurrency, failed commit, invalid inputs, symlinks, corruption and drift.
  All 14 Creation tests and eight MCP tests passed.
- Frontend build and five frontend test files passed (existing large-chunk and
  inlineDynamicImports deprecation warnings remain).
- Disposable Creation acceptance passed with advanced forms collapsed:
  `/tmp/cine-toaster-creation-review-kv_bp083/`.
- Disposable storyboard version/reload/back, reference/use trace, missing and
  error feedback, mobile and read-only preservation checks passed:
  `/tmp/cine-toaster-storyboard-review-j1sw8o1q/`. An initial test selected a
  partially covered scene's populated first shot; corrected the test to choose
  a genuinely empty scene before rerunning. Browser cancellation can log
  pre-existing BrokenPipe errors on abandoned reads; no page errors occurred.
- Real Demo 01 storyboard inspection passed:
  `/tmp/cine-toaster-storyboard-review-28lis15_/` (final count clarification);
  final desktop/mobile screenshots visually inspected. Screenplay/composition/chat
  regression passed at `/tmp/cine-toaster-storyboard-preproduction-review/`;
  all 13 Inception records/rounds and actual chat composer/context passed at
  `/tmp/cine-toaster-creation-live-fg6o3hfj/`. No browser test calls a model or
  writes the real film.
- Full regression passed: `PYTHONPATH=src .venv/bin/python tests/run.py -j 4`,
  1068 tests in 615 s, including heavy adapters. Final frontend build/tests and
  `git diff --check` passed. An additional focused MCP run passed all eight
  tests, including the new project-scoped storyboard import contract.
- Server left running at `http://127.0.0.1:8787` with the assistant. CT-0103
  remains open for the director's actual workflow/usability validation; this
  review slice does not close the process incident or approve creative work.
- After the final human-situational clarification, rebuilt the form-free GUI;
  five frontend test files passed. Replaced obsolete form-authoring browser
  acceptance with agent-produced records plus read-only human inspection:
  `/tmp/cine-toaster-creation-review-e4jsvy7q/`. Real 13-reference/chat-context
  inspection passed at `/tmp/cine-toaster-creation-live-i38h4_0s/`. The normal
  Storyboard entry, three images and exact screenplay links passed at
  `/tmp/cine-toaster-storyboard-review-7ztceme4/` (also checks the normal
  navigation's three-drawing count); final screenshots inspected.
  Production records remained unchanged. The 1068-test run above preceded
  this final UI-only refinement; no Python runtime changed afterward.
