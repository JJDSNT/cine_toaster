# Making a film with Cine Toaster

This guide is for anyone starting or working on a film, a person or an
agent such as Claude Code connected through MCP ([mcp.md](mcp.md)). It
covers the production's folder, the two phases a film goes through, the
commands for each step, and which decisions belong to the director.

## Starting

```bash
toast new ~/films/my-film --title "My Film"                                # empty
toast new ~/films/my-film --title "My Film" --screenplay draft.fountain    # or a .fdx
toast serve ~/films/my-film                                                # the control room
```

Given a screenplay, `toast new` makes one breakdown per screenplay scene,
linked by its heading and with no shots yet. A Final Draft file is converted
to Fountain, and what the conversion loses is reported. The production lives
outside the Cine Toaster checkout, and `toast new` never writes into a
directory that already has files in it.

`toast demo <dir>` copies a small finished example (The Last Signal), which
is useful for seeing what a production looks like once it has shots and
takes.

## The production is its folder

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

It runs through Codex's image generation on the ChatGPT subscription, so
it costs quota, not dollars (`toast doctor` says whether it is set up).

The folder is the whole film. Caches and job records can be deleted without
losing anything that was decided.

## Phase 1: the screenplay and the storyboard, fitted together

This phase is iterative and cheap: nothing costs money or waits on a model.
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
