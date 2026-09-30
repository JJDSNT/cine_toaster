# The directing assistant

An assistant in every room: the control room's rooms, the canvas, the
comparison of takes. It knows what you are looking at and the whole film,
looks things up by itself, points at shots, and takes your screen where you
ask. It starts work only when you say yes, and it never approves or refuses a
picture or a take for you.

```bash
make install-agents     # once: LangGraph and AG-UI (the agents extra)
make ui                 # builds the canvas and the Copilot Runtime file
claude                  # once, to log in to Claude Code: the assistant uses your login, no API key
toast serve <project> --assistant
```

Press **Assistant** in the control room's header, or in the canvas (`/app/`).
The conversation follows you from room to room, and from the control room to
the canvas, for as long as the browser tab is open.

## What it sees

With each message it gets three things:

- **The screen.** The room, the scene, the selection, and what in the room
  waits for you: an open gate and its candidates, the takes being compared.
- **The whole film.** Every scene, with its shots, chosen takes, findings,
  waiting gates and active workflow runs; the sequences; the cast; and the
  budget.
- **The scene in view.** Its blocks, runs, gates and master pictures.

When a question needs more, it **looks things up by itself**, up to four
times before answering. These lookups only read, never change anything:

- a scene;
- a shot: its action, camera, lines, master picture, and takes with where
  they came from;
- the cast;
- a search in the screenplay;
- the budget.

It knows nothing else, and says so rather than guess.

## What it can do

- **Point:** it can highlight a shot, on the canvas or in the scene room.
- **Take you somewhere:** it can open any room, a scene, a shot's comparison
  of takes, the canvas or the screenplay editor. That only moves the screen,
  so it does it without asking and tells you where it took you.
- **Propose:** it can offer to start a block's workflow, resume a stopped
  run, change a cut, or change **several cuts of a scene together** (a
  passage reworked as one idea). The question appears in the chat, listing
  every cut of a set, and nothing happens until you answer **Sim**. A set is
  taken whole or not at all: one cut the runtime refuses refuses the set,
  and an accepted set is one decision with one revision. The command is
  recorded with the actor `assistant` (an agent), and it reports what the
  run actually did.
- **Not decide:** gates stay yours (SPEC-0009). It can explain the
  candidates; it cannot choose one.

## How it runs

In the control room the assistant lives in a drawer: the same page as in the
canvas, in an iframe on the same origin. The room tells it what is on screen
after every render, and follows what it asks.

`toast serve --assistant` starts, on your machine:

- **the runtime**, as always;
- **the assistant** (LangGraph over AG-UI), in the same process;
- **the Copilot Runtime**, one bundled Node file, restarted if it stops.

The page talks only to the runtime, which forwards `/api/copilotkit`.
Telemetry and CopilotKit's development inspector are off, so nothing leaves
the machine except the model's own calls.

The model is reached through an adapter, chosen with `CINE_TOASTER_MODEL`:

- `claude-cli` (the default): the Claude Code CLI (`claude -p`) with your
  login, so no API key.
- `claude-api`: the Claude API through the official SDK, for use beyond one
  person's machine. Credentials come from `ANTHROPIC_API_KEY` or an
  `ant auth login` profile.
  - The model is `claude-opus-5-5` at low effort (`CINE_TOASTER_MODEL_ID`
    and `CINE_TOASTER_MODEL_EFFORT` override them).
  - The API's own fallback serves a turn the model declines, and a turn
    declined by every model is said in the chat. A turn takes several seconds. Conversations are kept in
memory, and a restart forgets them, never the film. See ADR 0017 and ADR
0018.
