# The directing assistant

An assistant in every room: the control room's rooms, the canvas, the
comparison of takes. It knows what you are looking at and the whole film,
looks things up by itself, points at shots, and takes your screen where you
ask. Consequential production actions wait for confirmation, and it never approves or refuses a
picture or a take for you.

The same conversation now has a Production Coordinator and an Inception
specialist (ADR 0029). The Coordinator routes new-film/creative development to
Inception; the current role and actual stop state appear above the chat.
Inception can do authorised draft work without asking you to fill forms:
save concept versions, save concept-linked screenplay candidates, and publish
readiness assessments for your review. It cannot approve its own proposal,
overwrite the canonical screenplay, delete images or generate them without a
separate integrated/authorised capability.

The Creation workspace updates its saved results after agent writes. Approve
direction / Request changes save a human production decision, then hand its ID
to another turn in the same CoAgent. The graph rereads the real decision and
current sources before working. If the assistant is unavailable, the decision
remains saved but no running task is implied. This is not an always-on event
daemon; restart/offline recovery and durable automatic background dispatch
remain separate work. Conversations/checkpoints are still in memory.

```bash
make install-agents     # once: LangGraph and AG-UI (the agents extra)
make ui                 # builds the canvas and the Copilot Runtime file
toast serve <project> --assistant --agent-provider <adapter>
```

For the director's phone on a trusted LAN, add `--host 0.0.0.0` and report the
computer's actual LAN URL, not localhost. Startup prints detected URLs and a
read-only Windows/WSL forwarding check; it does not automatically open firewalls
or prove phone reachability. The unauthenticated runtime must not
be exposed to the internet. WSL may require separately authorised forwarding /
firewall configuration; see [the onboarding guide](making-a-film.md#open-the-gui-on-the-local-network).

Press **Assistant** in the control room's header, or in the canvas (`/app/`).
The conversation follows you from room to room, and from the control room to
the canvas, for as long as the browser tab is open.

## Directing / Shot Planning and Script Supervisor / Continuity

### Advancing approved storyboard inputs

**Awaiting you** (`/app/decisions.html`) exposes saved current requests across
workspaces. For explicitly displayed existing scene/shot targets, **Approve &
advance** retains an approved stage input and initiates another turn through
this same CoAgent. The Coordinator routes storyboard development to the existing
Art Direction role. Its `save_storyboard` tool publishes a registered reference
image through the shared storyboard command, linking exact input/decision hashes
and preserving prior drawings. It cannot register an arbitrary path or publish
outside the approved target.

New drawing generation reuses existing jobs and separate quota consent. Current
output images must be visually prevalidated before a whole-scope human review
request. Reusing an image is not a generation claim or approval. Source changes
block consumption; additive briefs/references/drawings do not invalidate their
own approved input. **Continue approved work** is an explicit bounded retry,
not durable background dispatch. Local proposed-shot IDs still need a future
canonical-promotion contract; final storyboard/3D/master decisions remain separate.

The existing Production Coordinator can delegate screenplay shot planning or
continuity audits to these roles in the same public assistant (CT-0111).
Ask, for example, “Develop the decoupage for this scene and review continuity.”
The scene must be linked to its canonical screenplay; optional saved art briefs
can inform the proposal. Plans and reviews are retained in the film, not only
chat, and shown in **Screenplay & Storyboard → Directing & continuity**.

Continuity uses a fresh review call, the existing ledger and computed checks.
It labels authored facts, computation, inference and uncertainty, and can audit
canonical continuity without creating a plan. This textual review does not
inspect images. Direction can correct a plan and ask for a scoped human
decision. Requesting changes retains another version through the same CoAgent.
Approval is not canonical shot promotion, storyboard approval or generation
permission; those downstream operations are not implemented by these roles.
The loop stops honestly at eight reasoning steps/two reviews or a real gap;
there is no hidden background continuation.

## Art Direction and Visual Prevalidation

Art Direction and Visual Prevalidation (CT-0110) run inside the same assistant.
Before advancing, the Inception agent interviews you about what the film's
format needs (a music video: the song, performance or narrative, lyrics,
length, where it will be shown). It asks only what the records do not already
say, a few questions at a time, each with why it matters. Answer in **Awaiting
you** or at the terminal (`toast intake <film> --answer QUESTION "your words"`);
your words are kept as records, and answering the last question lets the
agent continue. The questions for each format live in its style
(`[[intake]]` in `style_assets/<format>/style.toml`, SPEC-0020).

Ask it to develop a visual direction or review existing reference images against
an intention. It saves briefs and image-based findings in Creation; no manual
forms are needed. Each generation attempt asks for quota consent over its exact
plan. A visual precheck is advisory; human creative approval stays separate.
Text-only model adapters cannot inspect pixels: `toast doctor` reports which
roles the supplied model can serve. All three adapters (Claude CLI, Claude API,
Codex CLI) send the images inside the request, without enabling filesystem
image tools, shell or browsing. The reviewer uses a fresh role/context with the
same model you supplied, unless you bind it to another one you also have:

```yaml
# ~/.config/cine-toaster/models.yaml  (ADR 0034)
roles:
  visual_prevalidation: claude-api:claude-opus-5-5   # adapter[:model]
models:                                              # your notes on top of the built-in catalogue
  claude-sonnet-5-5: {source: my trials on Demo 01}
```

Cine Toaster never picks a model by itself; the catalogue
(`src/cine_toaster/agents/model_catalog.yaml`) only describes what adapters
carry and what known models are good at.
Long generation jobs remain in the existing jobs runtime. When one outlives
the agent's turn, **Generation Operations** watches it: when it ends, the agent
continues by itself -- keeps the result, inspects it, asks for your review --
but never starts a new generation, which needs your consent. A failed job is
diagnosed (its error, the endpoint's workers and queue, the failures measured
for that path) and waits for you. The waits survive a restart of the server
(`$XDG_STATE_HOME/cine-toaster/agent-waits.json`); the conversation itself
does not, and the continued work is rebuilt from the film's records.

## What it sees

With each message it gets three things:

- **The screen.** The room, the scene, the selection, and what in the room
  waits for you: an open gate and its candidates, the takes being compared.
- **The whole film.** Every scene, with its shots, chosen takes, findings,
  waiting gates and active workflow runs; the sequences; the cast; and the
  budget.
- **The scene in view.** Its blocks, runs, gates and master pictures.

It also receives a shared production-work contract: use canonical sequences as
the work/human-review unit, keep scenes/shots as internal or explicitly partial
work, preserve versions, resolve agent-owned gaps, and leave creative gates to
humans. The full ordered sequence roster is kept outside the truncated scene
summary. Directing/Continuity and the independent reviewers keep this context
even when their detailed inspection is limited to one scene. This does not mean
the unfinished sequence comparison/adherence validator has run or passed.

When a question needs more, it **looks things up by itself**, up to four
times before answering. These lookups only read, never change anything:

- a scene;
- `work_structure`: canonical sequence IDs, complete ordered membership,
  unassigned scenes and the work contract; optionally focus a sequence/scene;
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

The role and the provider are separate. Select a provider explicitly with
`--agent-provider ADAPTER` for this host, or `CINE_TOASTER_MODEL=ADAPTER` in
its environment. The flag takes precedence without changing the environment.
When neither is configured, fall back to the **current CLI**, as requested by
the director: a Codex launcher signal (`CODEX_THREAD_ID`) selects `codex-cli`,
and a Claude Code signal (`CLAUDECODE=1`) selects `claude-cli`. These are
best-effort inherited launcher signals, not proof of an authenticated or
resumable session. Conflicting signals require explicit selection. The Codex
thread marker was observed in the local launcher; it is not a promised public
environment-variable interface.

There is no universal Claude default. Installing a CLI, setting `CODEX_HOME`
or providing an API key does not select it. With neither configuration nor an
unambiguous current CLI the film GUI still starts, but the assistant does not;
startup and `toast doctor` explain what is missing. An invalid explicit
configuration or failed adapter never falls back to another provider.

Currently implemented adapters:

- `codex-cli`: ephemeral `codex exec` requests using saved CLI authentication.
  The model subprocess uses a temporary working directory, ignores user config
  and rules, disables shell/plugins/apps/other agent tools, and uses a read-only
  sandbox. It does not receive repository development instructions. All film
  operations stay in the existing LangGraph role and Application API. Requires
  a CLI supporting the flags in `agents/models.py` (local help verified against
  0.162.0); authentication/inference are not proven by finding the executable.
- `claude-cli`: the Claude Code CLI (`claude -p`) with your login, so no API
  key. Run `claude` to authenticate when using this adapter.
- `claude-api`: the Claude API through the official SDK, for use beyond one
  person's machine. Credentials come from `ANTHROPIC_API_KEY` or an
  `ant auth login` profile.
  - The model is `claude-opus-5-5` at low effort (`CINE_TOASTER_MODEL_ID`
    and `CINE_TOASTER_MODEL_EFFORT` override them).
  - The API's own fallback serves a turn the model declines, and a turn
    declined by every model is said in the chat.

For example, only when you choose Claude Code:

```bash
toast serve <project> --assistant --agent-provider claude-cli
```

This selects an adapter, **not an already-open Claude session**. Claude uses
headless requests with `--no-session-persistence`, and Codex uses `--ephemeral`;
neither CLI adapter implements attachment/resume of an external provider session. The
session-binding contract is [SPEC-0001](../ai-context/specs/SPEC-0001-agent-session-binding.md),
whose thread/binding store remains planned. Current-CLI fallback reuses the CLI
provider, not the development conversation, its context or its tool authority.
Do not infer session ownership from installed programs, credentials or the
current GUI room. Codex flags and structured output follow the
[official non-interactive documentation](https://learn.chatgpt.com/docs/non-interactive-mode)
and [command reference](https://learn.chatgpt.com/docs/developer-commands?surface=cli).

A turn takes several seconds. Conversations are kept in memory, and a restart
forgets them, never the film. See ADR 0017 and ADR 0018.
