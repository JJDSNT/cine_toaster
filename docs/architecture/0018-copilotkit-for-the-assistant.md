# ADR 0018: CopilotKit carries the assistant; its Node runtime is an optional, supervised sidecar

Status: accepted (plan step 12). Amends [ADR 0015](0015-react-canvas-beside-the-control-room.md),
which kept Node a build tool only.

## Context

ADR 0017 made LangGraph the orchestrator of agents, served over AG-UI. Plan
step 12 decides the agent interface. The user expects LangGraph with
CopilotKit, so the director can talk to the AI while it knows what they are
looking at.

The facts, from CT-0033, CT-0043 and this step (CT-0044):

- **Connection paths.** CopilotKit's direct browser-to-agent path is its
  Enterprise tier. The open path needs its Copilot Runtime, which is Node.
- **The runtime bundles into one file.** With Vite, the Copilot Runtime
  becomes one 2.6 MB module that runs with Node and **no `node_modules`**.
  It ships in the package like the canvas.
- **Outside calls.** The development inspector calls
  `cdn.copilotkit.ai/notifications` and Google Fonts. With
  `enableInspector={false}` the page made no external request, and the
  runtime starts with telemetry off.
- **Crashes.** A dropped agent connection crashed the whole runtime
  (CT-0043). The runtime now logs uncaught errors and stays up, and a
  supervisor restarts it: it was killed and back in 2 s.
- **Real turns.** On a demo copy, in the canvas, with the model reached
  through the Claude Code CLI, turns took 8.6 s and:
  - named the selected shot and highlighted it;
  - explained what the block lacked;
  - refused to decide the picture gate;
  - proposed starting the workflow, asked in the chat with its own
    message, and on "Sim" started it through the command, as an agent
    actor;
  - then said truthfully that the run had stopped for lack of RunPod
    credentials.
- **Weight.** The client chunk is 1.75 MB (478 KB gzip), fetched only when
  the assistant panel opens. `frontend/node_modules` grows to about
  900 MB, which is needed only to build.

## Decision

1. **The assistant's interface is CopilotKit (v2 API)** in the React app
   (`/app/`), in a panel beside the canvas. It is loaded only when the
   runtime reports the assistant on.
2. **Its Copilot Runtime is an optional sidecar.** It is one bundled file,
   started and supervised by `toast serve --assistant`, telemetry off.
   The Python runtime proxies `/api/copilotkit` to it, so the page talks to
   one origin.
   - **Node becomes a run-time requirement for the assistant only.** The
     control room, the canvas, the CLI and every command keep needing only
     Python. This amends ADR 0015 for this one feature.
3. **The protocol boundary is AG-UI.** CopilotKit stays replaceable by
   `@ag-ui/client` and a chat of our own, and the agent by any AG-UI agent.
   Nothing in the Core knows about either.
4. **Development tooling that calls out is off.** That means the inspector,
   and telemetry in the runtime.
5. **The agent is a client of the runtime.** It reads through the HTTP API
   and acts only through `/api/commands`, after an interrupt the person
   answers, never on a gate (ADR 0017). Workflows it starts run in the
   runtime's own job manager.

## Consequences

- `toast doctor` reports "Assistant". It needs:
  - the `agents` extra (`make install-agents`);
  - Node 20+;
  - the built bundle (`make ui`);
  - a model adapter: the Claude CLI, logged in.
- The vanilla control room does not have the assistant yet. It is in
  `/app/`. Bringing it into the control room's rooms is a later step, with
  the same context contract.
- An upgrade of CopilotKit has to keep `@ag-ui/client` pinned to the version
  CopilotKit itself uses. 1.0.1 against CopilotKit's 0.0.59 did not
  type-check.
- Leaving CopilotKit means replacing `Assistant.tsx` and the bundled runtime
  file. The agent does not change.
