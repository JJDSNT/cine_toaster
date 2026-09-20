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
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

The project also supports its configured environment through `uv` when the
local cache is writable.

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
