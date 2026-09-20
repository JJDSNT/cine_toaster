---
id: CTX-DEVELOPMENT-TESTING
title: Testing
type: guide
status: active
owner: project
created_at: 2026-09-20
updated_at: 2026-09-20
tags:
  - development
  - testing
  - validation
---

# Testing

## Current command

Run the repository suite with:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

or, in the configured environment:

```bash
uv run --with pytest python -m pytest -q
```

Both run the same 140 tests. The suite needs no network and no external binary.

## Current inventory

| File | Covers |
| --- | --- |
| `test_commands.py` | commit, supersede, no-op repeat, stale revision, ineligible take, unknown resources, authored file untouched, unrelated state preserved, event on success only, atomic write, future schema version refused |
| `test_http_commands.py` | HTTP reaches the same command; each domain error maps to its status code; static assets cannot escape the asset root |
| `test_cli_takes.py` | CLI parity, JSON output, exit codes, `check` passing and failing |
| `test_geometry.py` | geometry parsing, axis, eyeline height, eyeline direction, and sanity checks, including the cases that must produce no finding |
| `test_assemblies.py` | version snapshots, verdicts and supersession, rollback semantics, refusal to restore a snapshotless or stale version, cut differences |
| `test_providers.py` | graph patching, keyframe wiring, control resolution, video detection, and every branch of job persistence — all offline |
| `test_knowledge.py` | frontmatter parsing, layer overrides, rejection of unknown checks and statuses, refuted records, provider claims, coverage arithmetic |
| `test_project.py`, `test_index.py`, `test_scanner.py`, `test_application.py`, `test_transitions.py`, `test_web.py` | loading, indexing, classification, project identity, transitions, path safety |

A check that must stay silent is as much a test as one that must fire. The
geometry suite asserts both, because a continuity checker that reports a correct
scene is worse than no checker.

## Test layers

- Unit tests cover parsing, validation, commands, revisions, and adapters with
  controlled inputs.
- Integration tests operate on temporary copied projects and assert filesystem
  results, API behavior, and emitted events.
- Contract tests ensure CLI, HTTP, future desktop, and agent tools produce the
  same domain result for the same command.
- Spike tests record measurements and limits; they are not silently promoted to
  product guarantees.

## Canonical write requirements

Every production mutation tests:

- valid success and resulting canonical representation;
- missing project and resource IDs;
- invalid relationships, such as a take from another shot;
- stale revision conflict;
- atomic failure behavior with the original file intact;
- event emission only after a successful commit;
- path traversal and symlink boundaries where applicable;
- repeat or idempotency behavior;
- preservation of unrelated and unknown supported data.

## Job requirements

Job implementations test state transitions, cancellation races, provider
failure, progress normalization, process loss, application restart
reconciliation, project switching, and result adoption. Tests must distinguish
staged output from canonical production state.

## Frontend requirements

Frontend tests focus on production outcomes: opening a scene, reviewing
alternatives, selecting a take, resolving conflicts, observing background work,
and retaining user control over agent-driven navigation.

Playback spikes use representative image, audio, and video fixtures and record
platform, codec, duration, frame rate, synchronization error, and resource use.

## Handoff

Every work record lists exact commands and outcomes. Note platform or external
provider validation that was not run; do not report a mocked adapter as proof of
real FFmpeg, ComfyUI, Tauri, or agent-provider behavior.
