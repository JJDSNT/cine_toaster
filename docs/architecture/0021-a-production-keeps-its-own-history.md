# ADR 0021: A production keeps its own history, beside what it is the history of

Status: accepted (2026-10-03, CT-0054, decided in evaluating Cine Toaster and
SINGULAR for SINGULAR's migration; the user asked for a structure that runs
the film's production and keeps the history of its evolution).

## Context

SINGULAR, made without Cine Toaster, kept its history by hand and kept it
well: each scene's `versoes/` held every cut, **the breakdown that made
it** (`decupagem-vN.yaml`), and a `VERSOES.md` table of date, length, what
changed, the author's notes and approval. It has no git: those folders,
`.orig` files and the screenplay's numbered versions are its only history.

Cine Toaster recorded versions with their takes and verdicts, but:

- versions went to a global `renders/assemblies/<scene>/`, away from the
  scene;
- a version did not keep the breakdown that made it, so "what did v7 look
  like on paper" could not be answered;
- `state.json` keeps the latest 200 decisions; older ones were dropped;
- the event log is a disposable cache by design (ADR 0006).

## Decision

1. **A version lives with what it is a version of.** A scene's versions go
   to `<scene folder>/versions/`: `vN.mp4`, its renditions, its speech
   sidecar, and **`vN.scene.yaml`, the breakdown as it was**. A sequence's
   go to `sequences/<id>/versions/`.
2. **`VERSIONS.md`** in each versions folder is regenerated from the records
   whenever a version is recorded or judged: SINGULAR's table, kept by the
   runtime. It is derived; editing it changes nothing.
3. **`history.jsonl`** beside each scene's `state.json` receives every
   committed decision, append-only, never truncated. `state.json` stays the
   current state with its recent tail; the journal is the history and
   belongs to the film, not to the cache.
4. **A production's text is versioned with git** when the production
   chooses it (the migration of SINGULAR does): breakdowns, screenplay,
   sheets, docs. Media is ignored; its history is the versions folders.
   Cine Toaster does not commit on its own.

Versions recorded before this decision keep their paths; nothing is moved.

## Consequences

- A director opening a scene's folder sees its cuts and the table of what
  changed and what was approved, without opening the application.
- Any version can be reproduced or compared on paper: its takes (the
  record), its breakdown (the snapshot), its decisions (the journal).
- The journal grows with the film; it is text, a few hundred bytes a
  decision.
