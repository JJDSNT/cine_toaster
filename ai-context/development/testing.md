---
id: CTX-DEVELOPMENT-TESTING
title: Testing
type: guide
status: active
owner: project
created_at: 2026-09-20
updated_at: 2026-10-15
tags:
  - development
  - testing
  - validation
---

# Testing

## Current commands

The suite is split by one mark, `@heavy("why")` (`tests/heavy.py`), on the
tests that need Blender, a model's inference, a voice engine or a long
render -- never on a contract:

```bash
make test-fast    # every test but the heavy ones: while working (about 10 min)
make test-heavy   # only the heavy ones: after changing an adapter
make test         # the whole suite, the final authority: before a step closes
```

Without make: `PYTHONPATH=src python3 tests/run.py [fast|heavy] [--times]`;
`--times` lists the slowest test classes, their class set-up included. One
module: `PYTHONPATH=src python3 -m unittest tests.test_signals`.

On 2026-10-15: 1018 tests, 40 of them heavy; the whole suite about 15 to 17
minutes on this machine. Most of the time is not in the heavy tests: retimed
sound, deliveries and generation lead (`--times`).

What a test needs and does not find -- FFmpeg, GL, Blender, the vision or
voice environment, fetched models -- makes it skip with the reason, never
fail; `toast doctor` says how to install each. A recorded fixture keeps a
real case in the fast suite (`tests/fixtures/c8/da2-occlusion.npz`: a
model's wrong occlusion, checked without the model).

## Current inventory

Test files are named for what they cover (`test_<area>.py`, about 100).
GL is checked against the reference, never the reverse
(`test_compositing_gl.py`, `test_gl_signals.py`), on llvmpipe and, with
`GALLIUM_DRIVER=d3d12`, on WSL's GPU.

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
