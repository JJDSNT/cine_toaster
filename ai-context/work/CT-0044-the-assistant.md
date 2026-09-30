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

# Done later the same day: every room, the whole film, and the screen

These came from the user's questions: "put it in the other rooms"; "does it
see the whole project or only the screen?"; "can it command the screen?".
Before this, it saw only the screen and the scene in view, and it could only
point.

- **The whole film in every turn** (`reads.overview`): scenes with
  shots, chosen takes, findings, waiting gates and active runs; sequences;
  cast; budget (new `GET /api/budget`).
- **Reads it asks for by itself** (`reads.py`): `scene`, `shot`, `cast`,
  `screenplay` (text search), `budget`.
  - `action: read` loops back into the graph without chat messages, at most
    4 per turn; after that it must answer.
  - The results are cut at 3,500 characters.
- **Screen navigation** (`navigate` in shared state, with a fresh id per
  request). Rooms: the sidebar's rooms, `scene`, `compare`, `canvas`,
  `editor`. No confirmation, because it changes only the view.
  - The canvas follows `canvas` itself; other rooms leave for the control
    room's URL (`navigation.ts`, outside the CopilotKit chunk).
- **The control room drawer** (`assistant-drawer.js`):
  - an "Assistant" button in the header, beside "Find anything";
  - an iframe of `/app/assistant.html` (a new Vite entry,
    `assistant-main.tsx`);
  - `postMessage` both ways: context out after every room render, and
    highlight and navigate back;
  - scene room shot rows carry `data-shot-id` for the highlight.
  - `assistantSeen()` describes each room, including an open gate and its
    candidates, runs in progress, and the takes being compared.
- **One conversation per tab** (`threadId` in `sessionStorage`), across
  rooms and page loads. Followed navigations are remembered in the session.

**Validation.**

- `tests/test_assistant.py` has 11 tests. New ones cover:
  - the whole film in the prompt;
  - two reads then an answer, with no chatter;
  - reads bounded at 4;
  - navigation without confirmation, and unknown rooms ignored.
- Real model, control room, demo copy:
  - "in which scenes is something waiting for me?" answered for the whole
    film (SC-010 and SC-030) in 9 s;
  - "take me to P3's comparison of takes" landed on
    `/?scene=SC-030&shot=P3` with the comparison open, in 6 s;
  - "point at P2" put the outline on the scene room's P2 row, in 5 s;
  - the conversation was remembered across a page load.
  - Zero external requests.
- A bug found and fixed on the way: the first navigation request was
  skipped by an "old request" guard. It is now remembered per tab instead.

# Remaining
- ~~An API-key model adapter~~ done 2026-09-30: `ClaudeApi`, the official
  `anthropic` SDK (now in the `agents` extra).
  - Defaults: `claude-opus-5-5` at low effort, structured output through
    `output_config.format` with every object closed, and the server-side
    fallback (`fallbacks: "default"`) on.
  - A refusal or API error becomes a message in the chat.
  - Chosen with `CINE_TOASTER_MODEL=claude-api`.
  - Tested against a stand-in for the SDK client (3 tests). **Not yet run
    against the real API**: no key is configured on this machine.
- More actions as commands, each with a confirm, for example proposing a
  take (never selecting it) or drafting a screenplay change as a diff for
  the editor (ADR 0016).
- Agent threads per scope and permissions (SPEC-0001).
