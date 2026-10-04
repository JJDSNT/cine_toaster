---
id: SPEC-0003
title: Cast entities, executable references, and generation lineage
type: specification
status: accepted
implementation: partial
owner: project
created_at: 2026-09-22
updated_at: 2026-09-22
tags:
  - project-core
  - continuity
  - cast
  - generation
---

# Goal

Give a recurring character one home in the project, make its reference images
operative rather than decorative, and record which reference produced which
take, so that identity drift across scenes becomes checkable before and after
generation.

# Context

A character that appears in eight scenes is currently described eight times.
Each scene file carries its own prose for the same person, and nothing relates
those descriptions to each other. Measured on a real production: one character
across eight scenes had six different descriptions, and three other characters
had three each.

Scene geometry already refers to people. `[[geometry.subjects]]` declares an id
and a label, shots name a `subject` and a `looks_at`, and the eyeline check
reads them. That reference is scene-local: two scenes may use the same id for
the same person and nothing verifies it, or use different ids and nothing
notices.

The generation side already accepts references. The provider layer can be given
a master image, and identity LoRA and keyframes are wired in `providers/ltx.py`.
What is missing is the state that says which image is the master for a
character, and the record of which master a finished take actually used.

The strongest available evidence that a sheet is the right model is that the
production invented one by hand before any tool asked for it, the same way it
invented scene geometry (ADR 0007). What it could not do by hand is enforce it.

# Cast entity

A cast member is project-level authored state. It is not owned by any scene,
because being the same person across scenes is the entire point.

```text
project/
  cast/
    kael/
      character.yaml          authored: the sheet and its references
      reference/              the master images themselves
        face-front.png
        full-figure.png
      state.json              runtime-owned: lineage, never authored
```

`character.yaml` declares:

- `id` — stable, and the value `[[geometry.subjects]]` and shot `subject`
  fields resolve to;
- `label` — the display name, which may change without changing identity;
- `description` — the sheet, in the film's language, for the author and for
  prompt construction;
- `authoritative_for` — the aspects this sheet decides, from a closed
  vocabulary: `face`, `hair`, `wardrobe`, `build`, `age`, `voice`;
- `references` — the executable part, specified below;
- `continuity` — free-form notes that no check reads, kept so the sheet remains
  the one place a person looks.

`authoritative_for` is required and has no default. A production learned the
hard way that an artifact can be authoritative for one thing and wrong about
another: a storyboard that decides the set while getting the character's hair
wrong is still a good storyboard. Authority that is not declared is authority
that is assumed, and assumed authority is how a wrong face reaches twenty-one
clips.

# Executable references

A reference entry makes a file usable by the provider layer without the caller
deciding how:

- `path` — relative to the cast member's directory;
- `kind` — `subject` or `face`;
- `role` — `master` or `supporting`. Exactly one master per `kind`;
- `fidelity` — optional provider hint;
- `supersedes` — optional path of the reference this one replaces, kept so a
  change of master is legible rather than silent.

A generation request for a shot whose `subject` names a cast member is
constructed with that member's master references attached. The caller names the
character; it does not name files.

Adding a reference does not migrate existing takes. Takes recorded against a
superseded master stay valid and stay marked, which is what makes drift
visible instead of automatic.

# Lineage

Lineage is runtime-owned state, written beside the authored file and never into
it (ADR 0006). For every generated take it records:

- the take it describes;
- each cast member involved;
- the reference paths actually sent, with a content digest;
- whether the reference was the master at the time of generation.

The digest is what makes the record survive a file being replaced in place. A
lineage entry that names a path alone would silently become a lie the first
time someone overwrites `face-front.png`.

Lineage is derived from what the provider layer was given, not from what the
breakdown intended. A record of intent duplicates the scene file; a record of
what was sent is the only one that can contradict it.

# Checks

Cast becomes worth having when it refuses things. Each check follows the
existing convention: a code, a severity, and a practice in the knowledge layer
that explains it (`enforced_by`, ADR 0009).

- `cast_subject_unknown` — a shot names a `subject` with no cast entry.
- `cast_reference_missing` — a cast member appears in shots that generate, and
  declares no master reference.
- `cast_reference_unused` — a take exists for a shot whose subject declares a
  master, and its lineage records no reference. This is the check the eight
  scenes and six descriptions would have failed.
- `cast_reference_superseded` — a take's recorded reference is no longer the
  master. Advisory, not an error: a scene approved under the old master is not
  retroactively wrong, it is retroactively dated.
- `cast_label_drift` — two scenes give the same cast id different labels.
  A pose or a mark in a plan's label ("Kael (sentado)", "Líra L1") is not a
  different name, and several people of a group in one scene are not drift
  (amended 2026-10-03, CT-0054: SINGULAR's plans label poses).

Every check reads declared state. None infers who a character is from prose, in
keeping with ADR 0007: a tool that guesses will eventually accuse a correct
scene, and one false accusation costs more than ten true findings earn.

# Locations

Locations have the same defect, the same shape, and the same fix: project-level
entity, declared authority, reference images, lineage. They are deliberately
out of scope here. Cast is specified first because the failure is sharper — a
wrong face is noticed by every viewer, a drifting corridor is not — and because
one implemented entity is better evidence for the second than two designed at
once.

# Acceptance criteria

- A cast member is declared once and referenced by id from any number of scenes.
- `[[geometry.subjects]]` ids and shot `subject` values resolve to cast entries,
  and failure to resolve is a finding rather than a silent pass.
- A generation request built for a shot carries its subject's master references
  without the caller naming a file.
- Every generated take has a lineage record naming the references sent and their
  digests.
- Replacing a master reference leaves prior takes valid, marked, and findable.
- All five checks are implemented, each with a knowledge practice explaining it.
- Authored files are never rewritten by lineage.

# Amendment: variants, names and voice (2026-09-29, CT-0040)

Implemented in `cast.py`; built on evidence from SINGULAR, which had made sheets
by hand (`elenco/fichas/`), variants (`kael_genebra`, `kael_boreal`,
`lira15`, `lira35`), a per-scene choice (`fichas: {KAEL: kael_genebra}`) and
a voice recording.

- **`variants`**: the same person at another age or in another state, each
  with its own description and references. A scene picks one with
  `cast: {KAEL: boreal}`. This settles the "per-scene overrides" deferred
  below for what a production actually needed. Costume changes by act use
  the same mechanism.
- **`names`**: every other name the character goes by, such as the
  screenplay cue (`MARA VALE`) or a geometry id. Lines, shot subjects and
  geometry subjects resolve through them.
- **`voice`**: `identity` (timbre, age), `accent`, `language` and reference
  recordings. The sheet owns the identity. A scene holds only
  `voice_state`, and a line only its `delivery`.
- **Checks implemented:**
  - `cast_subject_unknown`, `cast_reference_missing` and `cast_label_drift`,
    as specified;
  - `cast_variant_unknown` (error): a scene asks for a variant the sheet
    does not have;
  - `voice_identity_restated` (advice): a scene describes a voice whose
    identity the sheet already holds.

  All of them run only when the production has a cast.
- **A master face is owed only by a sheet that is authoritative for `face`.**
  A voice heard off screen, such as a narrator or a loudspeaker, owes none.
- **The brief** adds `[[VOICES]]`: each speaker's identity from the sheet,
  and the scene's state.
- **Commands:** `toast cast list`; `toast cast propose` drafts sheets from
  the scenes' own descriptions, listing every version with its scenes, and
  writes nothing.
- A production in the legacy vocabulary declares its scene fields with
  `scene_fields: {vozes: {maps_to: voices}}`. Only `cast`, `voice_state` and
  `voices` can be targets.

**Still planned:**

- lineage records written by generation;
- `cast_reference_unused` and `cast_reference_superseded`, which need
  lineage;
- attaching master references to generation requests.

All of these arrive with the generation adapter.

# Deferred choices

- Locations, as above.
- Whether `voice` in `authoritative_for` binds to a provider voice id, which
  needs the audio tier to exist first.
- Per-scene overrides of a sheet, such as a costume that changes in one act.
  The need is real and the model is not yet clear; specifying it now would
  describe an imagined production.

# Amendment: one face per person unless the sheet says why (2026-10-04, CT-0060)

A variant changes how someone looks (wardrobe, hair, an injury, the state they
are in), not who they are. When a variant's master face is a different picture
from the character's own master (or, without one, the first variant's), the
variant must give the reason: `face_changes: years in stasis`. Until it does,
every scene showing that variant reports `cast_identity_split` (error).
SINGULAR showed why this check is needed. Its Kael has three master faces
(`kael`, `kael_genebra`, `kael_boreal`) and its Claire has two. These are
issues, not variations.

# Amendment: one voice per person, held by a recording (2026-10-04, CT-0062)

A description narrows a generated voice; it does not fix it. A video model
invents the voice again in every generation. Three errors:

- `cast_voice_reference_missing`: a character's lines are generated (in a
  generated take, or mixed from a file) with no recording on the sheet
  (`voice.references`) and no named provider voice on the line, so nothing can
  bring them back to one voice (`toast revoice`).
- `voice_identity_conflict`: a scene's `voices:` gives a character another
  voice than the sheet's. The scene's text wins in the prompt (CT-0055), so it
  is another voice, not a state; the state belongs in `voice_state`. A scene
  that only repeats the sheet stays `voice_identity_restated` (advice).
- `cast_voice_split`: one character's lines name more than one provider voice.
