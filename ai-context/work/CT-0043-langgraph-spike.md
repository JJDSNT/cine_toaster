---
id: CT-0043
title: Plan step 11 — LangGraph spike, with CoAgents (CopilotKit) and a CLI model
type: work
status: done
owner: development agent
created_at: 2026-09-29
updated_at: 2026-09-29
tags:
  - langgraph
  - copilotkit
  - agents
  - spike
  - decision
---

# What

Run the built-in `block` workflow on LangGraph and compare them (plan step
11, CT-0023). At the user's request, also try LangGraph as a **CoAgent**
with CopilotKit, so the AI can be talked to and knows what the person is
looking at. Also at the user's request, the model is reached through the
**Claude Code CLI** instead of an API key.

Outcome: ADR 0017. The spike code is in `spikes/CT-0043/`: scripts with
fake RunPod, the agent, the CLI model adapter, the React page, the runtime
and the driver.

# Measurements

**Weight** (Python 3.12, fresh environments):

| What | Packages | Size | Import |
| --- | --- | --- | --- |
| Cine Toaster runtime | 6 | 23 MB | 0.17 s |
| + `langgraph`, `langgraph-checkpoint-sqlite` | 46 | 73 MB | 0.8 s |
| LangGraph + `ag-ui-langgraph` + FastAPI + uvicorn | 53 | 58 MB | — |
| + the `copilotkit` Python SDK (not needed) | 95 | 148 MB | — |
| CopilotKit v2 client + runtime + Vite (`node_modules`) | 1254 | 926 MB | — |

All licences are MIT or Apache-2.0.

**Workflow on LangGraph** (`block_graph.py`: `StateGraph`, SQLite
checkpointer, the gate as `interrupt()`, the same jobs and records):

- **Scenario A** (start, ask again, approve, finish), every step in a new
  process: the same result as the built-in engine (editor, editor, video;
  takes `BLOCK-AV1`), with 12 checkpoints.
- **Scenario C** (the checkpoint store deleted while a gate waits):
  - resuming the thread fails;
  - a new thread recovers everything without repeating paid work, but only
    because the nodes re-read the records.
- **Pitfall 1: re-execution.** An interrupted node re-runs from its start
  on resume, and its local values are gone. Opening a gate and waiting in
  one node opened a new gate on each resume, so opening and waiting had to
  be separate nodes.
- **Pitfall 2: retry repays.** After a node failure, each retry re-ran the
  paid picture node: 3 sends to the editor for one picture.

**CoAgent** (`director_agent.py` over AG-UI → Copilot Runtime (Node,
telemetry off) → CopilotKit v2 page, driven headless):

- `useAgentContext` values arrive in `state["ag-ui"]["context"]` as AG-UI
  `Context` objects.
  - The agent answered from them: "Você está no plano P3 da cena SC-030…
    O P3 é o plano que precisa de atenção".
- **Shared state.** The agent's `highlight: P3` reached `useAgent().state`,
  and the page drew it.
- **Interrupt.** Asked to start block A, the agent interrupted, and
  `useInterrupt` rendered Yes/No in the chat. On Yes it called
  `dispatch("start_workflow")` with actor `director-assistant` (agent).
  - The records show the run, the picture made, and the gate **waiting
    for a person**.
- **Issues for step 12:**
  - the development inspector fetches `cdn.copilotkit.ai/notifications`
    and Google Fonts; `enableInspector={false}` leaves zero external
    requests;
  - the Node runtime crashed when the agent failed mid-stream (an unhandled
    socket error);
  - the interrupt rendered the default "Confirm?" rather than the agent's
    message (the value's shape).
- **Model through the CLI.** `claude -p --output-format json --tools ""
  --no-session-persistence --setting-sources "" --system-prompt …
  --json-schema …` returned structured answers in about 4–7 s, with no API
  key: it uses the user's own login.
  - Replacing the default system prompt cut the tokens from 9.8k to 7.9k
    of cache creation per call.
  - The reported cost is the API equivalent; under a subscription it counts
    against the plan's limits.
  - This fits one person's own local use. Anything served to others needs
    an API-key adapter.

# Decision

See ADR 0017.

- Production workflows stay built in.
- LangGraph runs agents, as an optional extra.
- Agents act only through commands, never decide gates, and ask before
  consequential actions.
- The page gives the agent what the person sees.
- The model sits behind an adapter, the CLI first.

# Remaining (plan step 12)

- The CopilotKit decision (ADR):
  - Node runtime supervision;
  - inspector off, telemetry off;
  - runtime robustness;
  - interrupt rendering;
  - weight.
- The real Agent Runtime extra (`agents`): a model adapter (CLI or API key),
  agent tools that are Cine Toaster commands and queries, threads per scope
  (SPEC-0001).
- The chat inside the control room or canvas, with the room's context
  (scene, shot, open gate, selected take).
