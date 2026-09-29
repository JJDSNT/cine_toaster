---
id: CT-0033
title: Spike — does CopilotKit work on the recommended stack?
type: work
status: done
owner: development agent
created_at: 2026-09-29
updated_at: 2026-09-29
tags:
  - interface
  - agents
  - copilotkit
  - ag-ui
  - spike
---

# What

Before the plan step 7 stack decision, the user asked whether CopilotKit works
on the recommended stack: React 19, Vite, @xyflow/react 12, with Cine Toaster's
Python runtime behind it.

# Done

A throwaway app was built in a scratch directory; no repository code changed:

- Vite 7, React 19, @xyflow/react 12.12.0, and CopilotKit 1.75.0 through its
  **v2 API** (`@copilotkit/react-core/v2`). The v1 API is deprecated since
  1.68.2.
- A **scripted Python AG-UI agent** served over plain `http.server` and SSE,
  with no LLM. Its state was the demo's real SC-030 records: 3 shots and 2
  cuts.
- The canvas drew the agent's state as React Flow nodes and edges. A
  CopilotKit frontend tool (`highlightShot`) let the agent highlight a node.
  The chat was driven in headless Chromium.

Two connection paths were tested:

| Path | Result |
| --- | --- |
| React → Python agent directly (`selfManagedAgents` + `HttpAgent`) | Works: state reached the canvas, text streamed, the frontend tool ran and its result went back to the agent. **But** CopilotKit logs: "`selfManagedAgents` is part of CopilotKit's Enterprise Intelligence tier. Provide a `publicLicenseKey` for production use." |
| React → **Copilot Runtime** (Node, `@copilotkit/runtime` v2, `createCopilotNodeListener`) → the same Python agent | Works identically, with no licence warning. |

# Findings

- **Compatibility:**
  - `@copilotkit/react-core` and `react-ui` 1.75.0 declare `react ^18 || ^19`;
  - `@xyflow/react` 12 needs React 17 or newer;
  - all are MIT.
- **The open path needs a Node process.** The self-hosted Copilot Runtime
  sits between the React UI and our Python agent. Tauri can supervise it as a
  sidecar next to the Python runtime. Calling the Python agent directly is
  gated as enterprise.
- **Telemetry:**
  - the Copilot Runtime enables telemetry by default
    (`COPILOTKIT_TELEMETRY_DISABLED=true` turns it off);
  - `@scarf/scarf` reports on `npm install` through a `postinstall` script
    (`SCARF_ANALYTICS=false`);
  - the browser made no off-machine request while the chat ran.
- **Weight:**
  - the client alone is 708 packages and 569 MB of `node_modules`, and a
    3.2 MB bundle (880 KB gzip);
  - with the runtime, `node_modules` reaches 783 MB.
- **The agent side needs nothing from CopilotKit.** It is plain AG-UI events
  over SSE (`RUN_STARTED`, `STATE_SNAPSHOT`, `TEXT_MESSAGE_*`,
  `TOOL_CALL_*`, `RUN_FINISHED`). This keeps the Agent Runtime behind the
  AG-UI boundary: CopilotKit is replaceable by `@ag-ui/client` plus our own
  chat UI, or by another AG-UI client.

# Decisions

- None taken here. The stack decision (plan step 7) and the CopilotKit
  decision (plan step 12) stay with the user.

# Validation

- Direct path and runtime path each driven end to end in headless Chromium:
  - `before: nodes=0`, then after "Destaque o P2":
    `scene=SC-030 nodes=3 highlighted=P2`;
  - the agent log shows the tool-result follow-up run.
- Network capture during the runtime-path run: no request left 127.0.0.1.
