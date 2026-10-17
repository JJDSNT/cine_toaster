# 0032 — Approved stage inputs and a derived decision inbox

Status: accepted · 2026-10-16 · CT-0112 / SPEC-0018

The human decision command can atomically retain an approved development
handoff in the Creation journal. The GUI displays exact canonical scene/shot
targets and sends their preview fingerprint with approval. Legacy prose is a
suggestion only until this explicit confirmation. Ambiguous scope cannot be
promoted automatically. Plain approvals from old clients remain compatible.

The handoff pins source records/media, the assessment and human decision.
Consumption checks those sources while allowing additive downstream artifacts;
otherwise a new brief or first drawing would invalidate its own authorisation.
Promotion means adopting inputs, not rewriting shot manifests or approving
the final storyboard. The existing CoAgent routes this development to Art
Direction; no additional scheduler or role is introduced.

Art Direction can publish a registered reference image as a retained storyboard
candidate through the existing Core import operation. The shared wrapper enforces
approved scope, source freshness, journal revisions, path boundaries and replay
deduplication, linking source hashes and the handoff/decision. Earlier images
remain. It does not invent generation provenance. New generation still uses
the existing jobs and exact quota consent. A review request for the whole scope
requires outputs for all targets and visual inspection of their current sources.

`/api/decisions` derives current human direction requests and real waiting scene
gates from production records. It also exposes retained outputs and unfinished
handoffs, not fictitious live execution. Main React workspaces and the control
room link to one inbox. A read error is not a zero count. Informal creative
questions without a saved request remain a documented coverage gap.

The existing CoAgent continuation waits until the actual agent is connected,
not a provisional client. Each explicit continuation attempt has its own human
intent ID; replay of the same attempt remains guarded. No persistent worker,
automatic retry or automatic recovery after restart is implied.
