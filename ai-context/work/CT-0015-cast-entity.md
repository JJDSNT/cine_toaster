---
id: CT-0015
title: The cast entity — sheet, executable reference, and lineage
type: work
status: ready
owner: unassigned
created_at: 2026-09-22
updated_at: 2026-09-22
tags:
  - project-core
  - continuity
  - cast
---

# What

Make a recurring character project-level state with a declared sheet, reference
images the provider layer actually uses, and a record of which reference
produced which take. Design accepted; implementation not started.

# Why

A character that appears in eight scenes is described eight times, and the
descriptions diverge. Measured on a real production: one character across eight
scenes, six different descriptions; three others with three each. Nothing in the
software can see the divergence, because there is no canonical version to
compare against.

Scene geometry already names people — `[[geometry.subjects]]`, and `subject` and
`looks_at` on shots — but those ids are scene-local and resolve to nothing. The
provider layer already accepts master images, identity LoRA and keyframes. The
missing piece sits between them: state that says which image is this character,
and evidence of which image a finished take used.

# Done

- `SPEC-0003` accepted: entity shape, executable references, lineage, five
  checks, acceptance criteria.
- `ADR 0012` accepted: recurring entities are declared at project level.
- Confirmed the attachment points in the current code: `geometry.Subject` has
  `id` and `label`; `project.py` already reads a shot's subject and looks-at;
  `providers/ltx.py` already wires identity LoRA and keyframes.

# To do

1. `cast.py` — load `cast/<id>/character.yaml`, validate `authoritative_for`
   against its closed vocabulary, resolve exactly one master per reference kind.
2. Resolution — `[[geometry.subjects]]` ids and shot `subject` values resolve to
   cast entries; unresolved becomes a finding, not a silent pass.
3. The five checks in `SPEC-0003`, each with a knowledge practice and
   `enforced_by`, following the pattern CT-0009 established.
4. Lineage in runtime state: references sent, with digests, written from what
   the provider layer was given rather than from what the breakdown intended.
5. Provider wiring — a request built for a shot carries its subject's master
   references without the caller naming a file.
6. Interface — cast in the scene view beside continuity findings; a superseded
   master is visible on the takes it produced.

# Decisions

- **Project level, not scene level.** The defect is placement, not writing
  discipline: text re-authored per use has no canonical version, so no check can
  compare and no request can attach. See ADR 0012.
- **Authority is declared.** `authoritative_for` is required and has no default,
  from a closed vocabulary. An artifact may be authoritative for one aspect and
  wrong about another; the only way that survives in software is for the
  artifact to say which.
- **References are executable.** A master image is what the provider is given
  when a shot names that character, not an attachment for a human to open. The
  caller names the character and never names a file.
- **Lineage records what was sent, not what was planned.** A record of intent
  duplicates the scene file. Only a record of what was actually passed can
  contradict it.
- **Digests, not paths alone.** A lineage entry naming only a path becomes a lie
  the first time a reference is overwritten in place.
- **Replacing a master does not migrate existing takes.** They stay valid and
  become marked as generated against a superseded reference. Drift made visible
  beats drift made automatic.
- **Locations deferred**, though they have the identical shape. One implemented
  entity is better evidence for the second than two designed at once.
- **Per-scene overrides deferred** — a costume that changes in one act is a real
  need with no clear model yet, and specifying it now would describe an imagined
  production.

# Validation

- Not run yet; no code written.
- The design's acceptance criteria are in `SPEC-0003`.
- Available real data for validating the checks once implemented: a production
  of 9 scenes, 242 shots and 230 registered takes, whose character divergence is
  already measured and can serve as the expected finding set.
