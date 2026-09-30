# ADR 0019: No desktop shell; Cine Toaster runs in the browser, served by its local runtime

Status: accepted (2026-09-30, the user's decision). Cancels plan step 14 and
the Tauri candidacy in ADR 0002, ADR 0015 and `development/frontend.md`.

## Context

Plan step 14 was a Tauri desktop shell around the runtime (the Phase 3
remainder). When it came up, the machine had neither Rust nor the WebKitGTK
development libraries, and a Windows app would have to be built on Windows.
Asked which system to target, the user cancelled the Tauri app.

## Decision

- There is no desktop shell. Cine Toaster is the local runtime (`toast serve`)
  and the pages it serves in the browser: the control room, the canvas, the
  screenplay editor and the assistant.
- The runtime keeps supervising its own sidecars (the Copilot Runtime,
  ADR 0018). That role was meant for Tauri, and it stays in Python.
- Native desktop needs (file dialogs, a dock icon, system notifications) are
  answered in the browser or the CLI. A future need for them is a new
  decision, not a return to this plan by default.

## Consequences

- The ordered plan ends at step 13. Phase 3's exit is met by the React app
  served by the runtime (ADR 0015).
- Nothing in the code assumed Tauri, so nothing is removed.
- Documents that named Tauri as the shell now point here.
