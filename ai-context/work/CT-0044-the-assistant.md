---
id: CT-0044
title: Plan step 12 — the directing assistant (CopilotKit + LangGraph, CLI model)
type: work
status: done
owner: development agent
created_at: 2026-09-29
updated_at: 2026-09-29
tags:
  - agents
  - copilotkit
  - langgraph
  - decision
---

# What

Turn the CT-0043 CoAgent spike into a product feature and decide the agent
interface (plan step 12). The result is an assistant beside the canvas that
knows what the person sees, answers from records, points at shots, and acts
only through commands after a yes. Decision: ADR 0018.

# Done

- **Extra `agents`** (`pyproject`, `make install-agents`): langgraph, the
  SQLite checkpoint package, ag-ui-langgraph, fastapi and uvicorn.
- **`cine_toaster.agents`:**
  - `models.py`: the model adapter protocol; `ClaudeCli` runs `claude -p`
    with no tools, no settings and no session, a system prompt and a JSON
    schema. A missing CLI is reported in the chat.
  - `runtime_client.py`: the agent reads `/api/scene` and acts through
    `/api/commands` with actor `assistant` (agent).
  - `assistant.py`: the graph.
    - `page_context` reads AG-UI context from objects or dicts.
    - `scene_digest` summarises blocks, runs, waiting gates, declared and
      approved masters, and findings. It says a master is *declared*, not
      that it exists.
    - Actions: `start_workflow` and `resume_workflow` only. There is no gate
      action, and an unknown action is ignored.
    - The confirm node interrupts with the agent's own message, and after
      the command reports the run's real state from the records.
  - `server.py`: FastAPI plus the AG-UI endpoint in a thread. Conversations
    are in memory, disposable. The serializer allow-lists AG-UI `Context`.
- **`assistant_host.py`:**
  - `AssistantHost` starts the agent thread and supervises the Node
    runtime, with backoff when it keeps dying.
  - `proxy()` streams `/api/copilotkit` to it, answering 503 while it is
    down.
  - `unavailable_reason()` checks the extra, Node, the bundle and the
    model.
- **`toast serve --assistant`**. The ports are the runtime's `+1` (agent)
  and `+2` (Copilot Runtime).
- **Frontend:**
  - `copilot-runtime.ts` is bundled by `vite.runtime.config.ts` into
    `web_assets/copilot/copilot-runtime.mjs`, one 2.6 MB file that needs no
    node_modules. It logs uncaught errors and stays up.
  - `Assistant.tsx` is lazy-loaded. It uses `CopilotKitProvider` with the
    inspector off, `useAgentContext` (room, scene, focus, selection),
    `useAgent` state for the highlight, `useInterrupt` for the Yes/No card,
    `CopilotChat` and the dark theme.
  - `App.tsx`: an Assistant toggle shown only when `/api/copilotkit/info`
    answers, a highlight outline on the pointed shot, and the panel under
    the details.
  - `@ag-ui/client` is pinned to CopilotKit's own 0.0.59.
- **`toast doctor`** reports "Assistant". Docs are `docs/assistant.md` and
  ADR 0018.

# Validation

- `tests/test_assistant.py` (8 tests: fake model, fake runtime). They
  cover:
  - answering from page and records, and the highlight;
  - an action waiting for yes, then the command, and the truthful run
    status;
  - "no" changing nothing;
  - no gate decisions;
  - a missing model said in the chat;
  - context parsing and the digest;
  - a full AG-UI turn over HTTP (FastAPI TestClient) streaming text and the
    shared-state snapshot.
- Frontend: typecheck, build and 11 tests.
- **End to end, real model**, on a demo copy with no RunPod credentials so
  nothing could spend, driven headless through `/app/`:
  - an 8.6 s answer naming P3 and highlighting it;
  - it refused to decide the gate;
  - it proposed starting block A, and the confirm card showed its message;
  - on "Sim", `start_workflow` was recorded with actor `assistant`
    (agent). The run's first paid step refused for lack of credentials.
- Zero external requests from the page.
- Supervisor: the runtime was killed with `-9`; the proxy answered 503,
  then 200 two seconds later with a new process.

# Remaining

- The assistant in the vanilla control room's rooms (scene room, gates,
  comparison), with the same context contract.
- An API-key model adapter, for use beyond one person's machine.
- More actions as commands, each with a confirm, for example proposing a
  take (never selecting it) or drafting a screenplay change as a diff for
  the editor (ADR 0016).
- Agent threads per scope and permissions (SPEC-0001).
