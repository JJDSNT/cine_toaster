# Making a film with Cine Toaster

This guide is for anyone starting or working on a film, a person or an
agent such as Claude Code connected through MCP ([mcp.md](mcp.md)). It
covers the production's folder, the two phases a film goes through, the
commands for each step, and which decisions belong to the director.

## Starting

```bash
toast new ~/films/my-film --title "My Film"                                # empty
toast new ~/films/my-film --title "My Film" --screenplay draft.fountain    # or a .fdx
toast serve ~/films/my-film --host 0.0.0.0 --assistant                      # trusted-LAN GUI + copilot
```

Given a screenplay, `toast new` makes one breakdown per screenplay scene,
linked by its heading and with no shots yet. A Final Draft file is converted
to Fountain, and what the conversion loses is reported. The production lives
outside the Cine Toaster checkout, and `toast new` never writes into a
directory that already has files in it.

### Open the GUI on the local network

For this onboarding, prefer an intentional LAN-accessible launch so the director
can review on a phone on the same trusted network. Use `--host 0.0.0.0` to listen
on IPv4 interfaces, keeping the assistant behind the same GUI origin. The CLI
still defaults to loopback for callers that do not request LAN access.

At startup, a LAN bind now prints detected LAN URLs and read-only network
diagnostics. On WSL it reports the Windows LAN URL separately from VM addresses
and checks for a matching forwarding destination/listener. Missing Windows tools
produce a warning, not a startup failure. This does not verify firewall policy
or actual phone reachability and never changes OS rules automatically.

After starting, verify the computer's LAN IPv4 address and give the director
`http://<LAN_IP>:8787/app/creation.html` (or the relevant workspace). Neither
`localhost` nor `0.0.0.0` is the phone's destination: localhost refers to the
phone itself. Verify the GUI/API and assistant availability; do not claim phone
reachability from a localhost check alone. Use `--host 127.0.0.1` when access
must stay on this machine, or omit `--assistant` if it is not configured.

**Trusted network only:** the runtime has no authentication and exposes film
commands, not only previews. Do not expose it to the internet, open router WAN
ports, disable the firewall or publish the assistant's internal ports. Only the
GUI/runtime port is needed; any firewall rule should be limited to the trusted
local network and explicitly authorised.

On WSL 2, the Linux VM's address may not be reachable from the phone. Report the
Windows LAN address separately and check the WSL networking mode. NAT may need
explicit Windows port forwarding and firewall rules; mirrored networking has
its own firewall policy. Do not apply system network changes silently or report
success until verified. See [Microsoft's WSL networking guide](https://learn.microsoft.com/en-us/windows/wsl/networking).

Authorised Windows forwarding is host-specific: DHCP or a WSL restart can change
its destination. Recheck the startup diagnostic after either change. Rules are
persistent until explicitly removed; stopping the server does not remove them.

`toast demo <dir>` copies a small regression fixture (The Last Signal), which
is useful for seeing scenes at several workflow stages and exercising shots
and takes. It is not a completed end-to-end demo or a creative template.

## The sequence is the work and review unit

Use the film's canonical sequences and their exact ordered scene membership.
For example, Singular's Genebra includes 1-01, 1-02, 1-02A, 1-02B, 1-02C,
1-03 and 1-04; another film may group its scenes differently. Never reconstruct
the grouping from numeric endpoints or copy this example into another film.
Scenes and shots are useful internal subtasks or explicitly partial studies,
not substitutes for a sequence delivery. Focusing a scene in the GUI does not
change the director's review unit. Unassigned scenes remain an explicit gap.

The iterative flow is Inception -> screenplay <-> storyboard -> blockouts/3D
storyboard -> master images -> clips -> assembled sequences. An imported film
can start from its existing material; do not invent earlier Inception records.
For a sequence transition, compare exact original intention/reference versions
with screenplay beats and ordered drawings, identifying deviations, continuity
and gaps. An independent check of an artist's brief alone is insufficient.
Do agent-fixable work before asking the director for a concrete creative choice
or a complete review. Preserve every version; only humans decide creative gates,
and those decisions do not authorise paid generation.

Implemented CoAgent roles receive this work contract and canonical roster;
Coordinator/Inception can explicitly read `work_structure` by sequence/scene ID;
external MCP agents use the read-only `read_work_structure` tool.
The full sequence comparison package and independent adherence validator remain
in progress. Do not claim that context availability has executed that review,
or that an isolated scene-direction gate approves the sequence transition.

## The production is its folder

The built-in assistant's existing Production Coordinator can delegate discovery
to Inception, visual development to Art Direction/Visual Prevalidation and
linked-screenplay shot proposals to Directing/Continuity. In **Screenplay &
Storyboard**, ask it to develop a named scene's decoupage and review continuity.
Its retained proposals/reports appear in **Directing & continuity**. Humans
approve or request changes at the scoped direction gate, not through manual
authoring forms. These proposal decisions do not promote canonical shots,
approve storyboard images or authorise generation; the full downstream handoff
is still incomplete. See [the assistant](assistant.md) and
[preproduction](preproduction.md) for implemented limits.

```text
project.yaml                      identity, paths, sequences, the frame, the look
story/screenplay.fountain         the screenplay
scenes/<scene>/scene.yaml         a breakdown: direction, geography, shots
scenes/<scene>/state.json         decisions: chosen takes, cuts, gates, versions
scenes/<scene>/work/              the takes, as files
cast/<id>/character.yaml          who someone is: pictures, variants, voice
locations/<id>/location.yaml      a place, shared across scenes
references/<id>/reference.yaml    what the film looks at: a draft board, a probe, a painting
```

- **Authored files** (the screenplay, `project.yaml`, breakdowns, cast and
  locations) belong to the person, and Cine Toaster never rewrites them.
- **Decisions** go in `state.json`, through commands that record who made
  them and why. Every decision can be revised, and its history is kept.
- **Takes are files.** They are found by reading `work/`, so nothing
  declares them and nothing can drift from them.

## References

What the production looks at but does not use as material -- a first draft
board, a model probe, a painting, a still from another film -- is kept in
`references/`, each with who or what made it, its prompt, the references it
came from, its licence and each file's digest:

```bash
toast references add <film> board.png --title "First board" --kind generated \
    --made-by "an image model" --prompt "..." --note "her face drifts in panel 4"
toast references list <film>     # and what is wrong: a file changed, missing or unlisted
```

`--kind` is `generated`, `found` (someone else's: give `--licence`) or
`made` (by the team). `--from` names a reference this one was made from.
A reference is never written over.

A reference can also be generated from a description and earlier
references, kept with its lineage:

```bash
toast references generate <film> --title "1930s trial" --from <reference> \
    --prompt "keep her face; redraw her in early-1930s technique ..." [--dry-run]
```

`--cast MEMBER@variant` and `--style <id>` compose who she is (the cast
sheet) and how it is drawn (the style) from their records, so `--prompt`
says only what happens.

It runs through Codex's image generation on the ChatGPT subscription, so
it costs quota, not dollars (`toast doctor` says whether it is set up).

The folder is the whole film. Caches and job records can be deleted without
losing anything that was decided.

## Creation / Inception: before the screenplay

A film can begin with an idea, a discussion, alternative directions and rough
visual references. Keep the useful explorations and their origins in the film;
the references commands above already support pictures and their lineage.

A [Creation / Inception workspace](creation.md) is available at
`/app/creation.html`. Save concept versions, compare reference alternatives
and develop a screenplay candidate from an explicit saved concept/reference
set. Earlier versions remain; the film's current screenplay is not replaced. A
reference may inspire later work without becoming a shot's approved image.
Record actual provider inputs separately from images that were only consulted.

Exploratory generation may consume quota or money; show and authorise its cost.
Writing and shot planning need not wait for any generated reference. A film
that already has a screenplay can start directly with it. Revising an earlier
exploration must not silently replace the inputs of work already produced.

The assistant can delegate visual development to Art Direction, which saves a
brief with specific criteria and pinned inputs. Visual Prevalidation inspects
actual images separately and retains evidence and corrections in this workspace.
Ask for the desired visual outcome in the copilot; no authoring forms are needed.
A precheck never approves the art for you. Exploratory generation uses the
existing jobs and asks for explicit quota consent on each plan; failed candidates
remain available. If a job outlasts the bounded assistant wait, ask it to continue
when the job finishes. `toast doctor` reports whether the selected agent adapter
supports visual input (currently Codex CLI); metadata is not pixel inspection.

## Phase 1: the screenplay and the storyboard, fitted together

The [Screenplay & Storyboard pilot](preproduction.md), at
`/app/preproduction.html`, shows linked screenplay passages beside proposed
shots, retained story drawings and separate composition studies. Import drawings
with `toast storyboard add` (or the shared HTTP/MCP operation), keep earlier
versions and trace exact reference inputs back to Inception. The latest preview
is not an approval or a selected master. Missing visuals are shown explicitly;
the pilot does not yet implement the full handoff to shot masters.

This phase is iterative and cheap: writing, planning and computed previews need
no model call. Optional AI-generated sketches can consume quota or money and
need their own disclosure and authorisation, just like exploratory references.
The screenplay and the shots are adjusted against each other until what will
be shot is defined.

| Step | How |
| --- | --- |
| Write the screenplay | the screenplay room (`/app/script.html`), or any Fountain editor; `toast script import-fdx` / `export-fdx` |
| Break it into shots | the shots in each `scene.yaml`: what each covers (`covers: from/to`), its duration and how it is entered (`cut`) |
| Check the coverage | `toast check <film>` lists every line that no shot films, and anchors that broke; `toast script show` and `toast script link` |
| Cast and places | `toast cast propose` drafts cast sheets from the scenes and writes nothing; `cast/` and `locations/` ([locations.md](locations.md)) |
| Blocking | scene geometry, cameras and the line of action, checked before anything is generated ([continuity-checks.md](continuity-checks.md)); `toast previs`, `toast moves` ([camera-moves.md](camera-moves.md)) |
| The brief | `toast brief <film> <scene>`, built from the records ([brief.md](brief.md)) |

`toast knowledge <film>` lists the filmmaking practices the checks enforce,
such as every line being filmed, eyelines meeting, or one voice per person.
`toast knowledge --show <id>` prints one practice in full.

## The gate: the storyboard approved

Moving a scene into phase 2 is a decision: its storyboard is approved as
what will be produced. It is recorded with who decided, when, why, and the
breakdown as it stood at that moment, so a later change shows as "changed
since the approval".

```bash
toast storyboard approve <film> <scene> --why "..."     # or "Approve the storyboard" in the scene room
toast storyboard reopen  <film> <scene>
```

**Only a person approves a storyboard.** The approval blocks nothing, but
it states where the scene stands.

## Phase 2: producing what was defined

This phase is costly and versioned. Every result is kept, and the person
chooses between the versions.

| Step | How |
| --- | --- |
| Budget | `toast budget set <usd>` sets a ceiling that no paid command can pass; `--dry-run` on any paid command shows its estimate |
| Master pictures | `toast picture <film> <scene> <shot>` edits a source picture with the cast's faces ([generation.md](generation.md)) |
| Clips | `toast workflow start <film> <scene> <block-or-shot>`: picture, a person approves it, generate, slice into takes ([workflows.md](workflows.md)); `toast generate` on its own |
| Brought-in material | `toast take add`, `toast footage fetch`, each with its source, licence and credit |
| Choose takes | compare in the control room; `toast take select` |
| Scene assembly | `toast assemble <film> <scene>` builds a kept version from the chosen takes, with transitions and J-/L-cuts |
| Sequences | declared in `project.yaml`; `toast assemble-sequence` |
| Sound, titles, effects | [sound.md](sound.md), [titles.md](titles.md), [vfx.md](vfx.md), [styles.md](styles.md) |
| Where it stands | `toast status <film>`, sequence by sequence; `toast finops` for what was spent |

`toast doctor` lists what this machine can do and the exact command that
installs anything missing.

## What is the director's

An agent may read everything, explain the candidates, propose, and run
authorised work within the budget. Only a person:

- approves a storyboard;
- approves or refuses a master picture at a workflow's gate;
- chooses a take;
- changes an authored file, either directly or by accepting a proposed diff.

Gates and decisions are records in the production, not chat. A refusal from
a command means nothing was changed.

## Working with an agent

Connect Claude Code to a film with `toast mcp <film>` ([mcp.md](mcp.md)). It
then works through the same commands as a person, and everything it decides
appears in the control room's history, where it can be undone.

The Cine Toaster repository's own development notes (`AGENTS.md`,
`ai-context/`) are for changing the software. They are not context for
making a film.
