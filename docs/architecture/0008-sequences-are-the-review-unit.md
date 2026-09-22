# ADR 0008: Sequences are the unit a production reviews

Status: accepted

## Context

`scene.toml` already had a `sequence` field, but it was a display string:
`"Sequence 02 · The Reply"`. Nothing grouped scenes, so the interface could only
show a flat list and a whole-project percentage.

That does not match how the work happens. Singular assembles consecutive scenes into one video and reviews it as a unit —
`sequences/geneva-1-01-to-1-04-v1.mp4` covers scenes 1-01 through 1-04 and is
watched in one sitting. The verdict "this part works now" is given at that
level, never at the level of the whole film and rarely at the level of one
scene.

This is a sequence in the ordinary film sense: a run of scenes forming one
dramatic movement. It is not an act — the same production's arc spans far more
than these scenes — and it is not a shooting block, because the grouping is
narrative rather than logistical.

## Decision

A sequence is declared in `project.toml`:

```toml
[[sequences]]
id = "genebra"
label = "Genebra"
act = "Arco I"
scenes = ["1-01", "1-02", "1-03", "1-04"]
render = "sequences/geneva-1-01-to-1-04-v1.mp4"
```

It owns an ordered list of scenes, an optional act label, and an optional
reference to its assembled render. Progress, open decisions, and continuity
notes are aggregated from its scenes rather than stored on it.

Scenes not claimed by any sequence are grouped under `unassigned` so nothing
disappears from the interface.

## Consequences

The interface can finally answer "is this part done?" at the level someone
actually asks it, and play the assembly beside the count of undecided shots.

Sequences are a projection over scenes, not a second source of truth: removing a
sequence loses grouping, never work.

Acts are only a label for now. If the production needs act-level state, that is
a later decision made from a real need.
