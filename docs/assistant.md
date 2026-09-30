# The directing assistant

An assistant beside the canvas that knows what you are looking at, answers
from the production's records, points at shots on screen, and starts work
only when you say yes. It never approves or refuses a picture or a take for
you.

```bash
make install-agents     # once: LangGraph and AG-UI (the agents extra)
make ui                 # builds the canvas and the Copilot Runtime file
claude                  # once, to log in to Claude Code: the assistant uses your login, no API key
toast serve <project> --assistant
```

Open `/app/` and press **Assistant**.

## What it sees

With each message, the page sends what you are looking at: the room, the
scene in focus, and what is selected (a shot, a take, a cut, a workflow
run). The assistant also reads a short digest of that scene from the
runtime: blocks, workflow runs and their steps, gates waiting for you,
declared and approved master pictures, and findings. It knows nothing
else, and says so rather than guess.

## What it can do

- **Point:** it can highlight a shot on the canvas.
- **Propose:** it can offer to start a block's workflow, or resume a stopped
  run. The question appears in the chat, and nothing happens until you
  answer **Sim**. The command is then recorded with the actor `assistant`
  (an agent), and it reports what the run actually did.
- **Not decide:** gates stay yours (SPEC-0009). It can explain the
  candidates; it cannot choose one.

## How it runs

`toast serve --assistant` starts, on your machine:

- **the runtime**, as always;
- **the assistant** (LangGraph over AG-UI), in the same process;
- **the Copilot Runtime**, one bundled Node file, restarted if it stops.

The page talks only to the runtime, which forwards `/api/copilotkit`.
Telemetry and CopilotKit's development inspector are off, so nothing leaves
the machine except the model's own calls.

The model is reached through the Claude Code CLI (`claude -p`), with your
login: no API key. A turn takes several seconds. Conversations are kept in
memory, and a restart forgets them, never the film. See ADR 0017 and ADR
0018.
