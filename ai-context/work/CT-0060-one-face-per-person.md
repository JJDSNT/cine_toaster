---
id: CT-0060
title: One face per person -- a variant with another master face must say why
type: work
status: done
owner: unassigned
created_at: 2026-10-04
updated_at: 2026-10-04
tags:
  - cast
  - continuity
---

# What

The user's correction after CT-0059: "evidentemente o nosso sistema deveria
acusar a incongruência existente". SINGULAR's current material is not a
reference for correctness, so the system must flag its inconsistencies rather
than present them as possible intent. The incongruity was not a continuity
question. It was identity: Kael's `kael_genebra` master face is visibly
another man than `kael` (narrower face, different jaw), while `kael_boreal` is
the same man; the user is explicit that none of these are legitimate
variations: they are issues. The cast checks did not notice two master faces
for one person.

# Done

- `cast.py`:
  - a variant may declare `face_changes: <reason>`;
  - `_identity_splits` finds characters whose variants use a master face that
    is a different picture from the character's own (by digest, or by path
    when there is no digest);
  - every scene showing such a variant without a reason gets
    `cast_identity_split` (**error**: it reaches the attention list and the
    Producer status as a blocker). The message says how many faces there are
    and the two ways out: make the picture from the master face, or declare the
    reason.
- `CHECK_CODES` and the knowledge record `a-character-is-declared-once`
  explain the rule.
- SPEC-0003 amendment.

# Decisions

- **Picture identity, not face recognition.** "Another picture" is the
  deterministic fact. Whether two pictures show the same face would need a
  face-embedding model, which is not adopted yet. A variant derived from the
  master is still another file, so it must declare its reason too. The cost is
  one line, and it records intent.
- **The existing convention is kept.** The same person at another age or after
  stasis is allowed, and only has to be said.

# Validation

- `tests/test_cast.py`: 3 new tests (split reported; reason accepts it; same
  master is not a split).
- On the scratch SINGULAR copy:
  - three issues, all reported as errors:
    - Kael's `kael_genebra` face, in 1-02A, 1-02B, 1-02C and 1-03;
    - Kael's `kael_boreal` face, in 3-01 and 3-02;
    - Claire's `claire` face against `claire_doente`, in 3-01 and 3-02.
  - None is a legitimate variation. In the remake, each character keeps one
    face.
- Full suite before commit.

# Remains

- A face-similarity measure (an embedding distance) could tell "another
  picture of the same face" from "another face". Only when there is a real
  need, and through a doctor-reported capability.
