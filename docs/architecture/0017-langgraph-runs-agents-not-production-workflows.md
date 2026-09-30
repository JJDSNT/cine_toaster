# ADR 0017: LangGraph runs the agents; production workflows stay built in

Status: accepted (plan step 11). The CopilotKit decision remains plan step 12.

## Context

Plan step 11 asked whether LangGraph should orchestrate production workflows,
by running the same workflow as the built-in engine (SPEC-0009) and
comparing. The user also expects to use LangGraph **with CopilotKit**
(CoAgents). The point is to talk to the AI while it knows what the person is
looking at. So the spike measured both roles: LangGraph as the
production-workflow engine, and LangGraph as the agent behind the chat
(CT-0043).

**As the production-workflow engine**, on the same `block` workflow, with the
same jobs and records and fake RunPod:

- **It works.** Every step ran in a new process, and the result was
  identical to the built-in engine: two edits, one generation, the same
  takes.
- **What held nothing:** the guarantee that checkpoints are disposable does
  not come from LangGraph.
  - After the checkpoint store was deleted, resuming the run failed.
  - A new run recovered without repeating paid work, but only because the
    nodes re-read the production records. That is what the built-in engine
    does by construction.
- **Pitfalls found:**
  - An interrupted node is re-executed from its start on resume, and its
    local values are lost. Opening a gate and waiting in one node opened a
    second gate on every resume, so the two had to be split.
  - Retrying after a failure re-ran the paid node and re-submitted the
    edit: three sends for one picture.
- **Cost:**
  - 40 more packages and +50 MB, including `langchain-core`, `pydantic`,
    `httpx` and `requests`, against a runtime of 6;
  - importing it takes 0.8 s, against 0.17 s.

**As the agent behind the chat** (LangGraph served over AG-UI with
`ag-ui-langgraph`, the self-hosted Copilot Runtime, and a CopilotKit v2
page), working end to end:

- **The agent knew what the person saw.** The page's `useAgentContext`
  arrived in the graph's state: scene, room, selected shot, blocks. It
  answered in Portuguese that the director was on P3, and why P3 needed
  attention.
- **Shared state.** The agent set `highlight: P3`, and the page drew it.
- **Human in the loop.** Asked to start the block's workflow, the agent
  interrupted, and CopilotKit rendered the confirmation in the chat. On
  "yes" it acted only through the `start_workflow` command, recorded with an
  agent actor. The run then stopped at the picture gate, which only a
  person decides.
- **The model through the Claude Code CLI**, with no API key. `claude -p`,
  with no tools, no settings, a short system prompt and a JSON schema,
  answered in about 4–7 s per turn.

## Decision

1. **Production workflows stay on the built-in engine** (SPEC-0009). Their
   state is production records, and `advance` is idempotent by
   construction. LangGraph adds weight and resume semantics that need care
   around paid steps, but no capability this workflow lacks.
2. **LangGraph is the Agent Runtime's orchestrator**, behind the
   `orchestration/` and agent adapter boundaries, as an **optional extra**
   (`agents`). The core, CLI and control room never need it.
3. **An agent acts only through application commands.** Starting a
   workflow, proposing a take, drafting a screenplay change: each is a
   command, recorded with an agent actor.
   - **An agent never decides a human gate.** It may prepare the decision,
     summarise the candidates and point at a problem.
   - **A consequential action is confirmed by the person first**, through an
     interrupt.
4. **What the person sees is given to the agent as context** by the
   interface, with each turn. It is read-only context, never a second copy
   of the film.
5. **The model sits behind a model adapter.**
   - For a person working on their own machine, the first adapter is the
     Claude Code CLI with their own login (`claude -p`): no key, and
     nothing stored by us.
   - An API-key adapter serves any other use.
   - LangGraph checkpoints of agent threads are disposable operational
     state, in `XDG_STATE_HOME`.

## Consequences

- Plan step 12 (CopilotKit) starts from a working CoAgent path. It must
  settle:
  - the Node runtime, which is required on the open path: the direct path is
    Enterprise (CT-0033);
  - disabling the development inspector, which otherwise fetches
    `cdn.copilotkit.ai/notifications` and Google Fonts
    (`enableInspector={false}` stops every external request);
  - telemetry off in the runtime;
  - the runtime crashing when the Python agent drops a connection;
  - a custom interrupt message, which rendered as "Confirm?" instead of the
    agent's text;
  - the weight: 926 MB of `node_modules` for the client, runtime and build.
- SPEC-0001 (agent threads and provider sessions) gains its first concrete
  shape: a LangGraph thread per scope, with the checkpoints disposable.
- If the built-in engine ever needs what LangGraph offers (branching
  sub-flows, time travel), this ADR is revisited. The spike code is kept in
  `ai-context/work/spikes/CT-0043/`.
