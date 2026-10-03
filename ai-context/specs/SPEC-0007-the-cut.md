---
id: SPEC-0007
title: The cut — how one shot becomes the next, within a scene
type: specification
status: implemented
implementation: complete
owner: project
created_at: 2026-09-29
updated_at: 2026-09-29
tags:
  - project-core
  - editing
  - continuity
  - transitions
---

# Goal

Every join between adjacent shots in a scene is a record that holds four
things:

- how the join is made: its type, an optional catalog transition, and whether
  frames chain;
- what the outgoing shot leaves: its exit state (SPEC-0005) and its last
  covered line (SPEC-0006);
- what the incoming shot finds: its entry state and its first covered line;
- what is wrong with the join.

The Cut room shows each record, and a canvas edge will later show the same
record (CT-0023).

# Placement

The cut is declared on the **incoming** shot. This follows the existing
convention: a shot's `transition` is already the join *into* that shot, and
`build` applies it between the previous shot and this one.

```yaml
shots:
  - n: 3
    cut:
      type: match          # hard (default) | match | action | j | l | smash | jump | continuation
      chain: frame         # optional: this shot's first frame is the previous last frame
      reason: The stack's light becomes Mara's eye.
    transition: {id: dissolve, duration_ms: 600, reason: "..."}   # unchanged (SPEC-0004)
```

Every field is optional. A shot with no `cut` is a hard cut. The first shot of
a scene has no cut record. **Cuts between scenes are out of scope**: time and
place legitimately change there, and that belongs to the sequence.

# The record

For each adjacent pair `(A, B)` in a scene, the runtime derives:

- `from`, `to`, `type`, `chain`, `reason`, and `transition` (B's);
- `exit`: A's end camera pose, framed subjects with screen sides, `ends_on`,
  and A's last covered unit;
- `entry`: B's start camera pose, framed subjects with sides, and B's first
  covered unit;
- `findings`: the checks below that concern this pair.

The record is derived and read-only. Only `cut` is authored.

# Checks

| Code | Severity | Meaning |
| --- | --- | --- |
| `cut_type_unknown` | error | `cut.type` is outside the vocabulary. |
| `jump_cut_undeclared` | warning | A and B frame the same subject from nearly the same place: less than 30° apart around the subject, with less than 1.4× change in framing width. It reads as a jump; declare `type: jump` if that is the intent. |
| `chain_pose_mismatch` | warning | `chain: frame` asks B to start on A's last frame, but B's start camera or a framed subject differs from A's end. The generator would receive a first frame from another camera. |
| `split_edit_without_sound` | warning | An `l` cut, where A's sound runs over B, while A ends on no dialogue; or a `j` cut, where B's sound leads, while B starts on no dialogue. Uses SPEC-0006 coverage. It is skipped when the scene is not linked to a screenplay. |
| `continuation_unchained` | advice | A `continuation` that does not declare `chain: frame`. The second part of a split shot must open on the first part's last frame, or the seam shows. |
| `transition_reason_missing` | advice | A transition has no `reason`. SPEC-0004 requires one, because a choice without a reason cannot be reviewed. |

`cut_screen_flip` (SPEC-0005) remains the screen-side check across a cut, and
the record lists it with the others.

# Acceptance

- `cut` parsed and validated; records derived per scene and exposed as
  `scene.cuts`.
- Every check passes and fails in a test.
- The Cut room shows each scene's cuts. A card shows the two shots, the type,
  chain, and transition, exit versus entry framing, and the line across the
  cut, with its findings.
- The demo declares at least one non-hard cut. Both demos still pass
  `toast check`.

# Amendment: continuation (2026-09-29, CT-0035)

`type: continuation` joins two parts of **one** shot that was split across
generations, because a model renders a few seconds at a time. Found on
SINGULAR 3-01 P3a→P3b ("exact continuation … from its last frame").

- It is not an editorial cut. The jump check is skipped: the same setup on
  both sides is intended.
- It expects `chain: frame`. Without it, `continuation_unchained` (advice)
  is reported. With it, `chain_pose_mismatch` still catches a continuation
  from another setup.
- This is the first real-data form of the generation-unit question
  (CT-0022 step 4): continuations are how one shot spans several
  generations.

**Trim is not a cut.** SINGULAR's legacy `corte` means a trim: handles
`{antes, depois}` and in/out points `{inicio, fim}`. It must never be read as
this spec's `cut`. A `trim` field is decided as a separate record, and will be
specified when the assembly of generated takes exists, since that is the
first thing that would read it.

# Implementation notes

- `src/cine_toaster/cuts.py` derives the records; `project.py` exposes them as
  `scene.cuts` and adds the findings to the scene's.
- The jump check measures framing width **at the subject's distance**, and
  also requires the subject to hold nearly the same place across the frame
  (less than half the half-width). Without the second guard, SC-030 P1→P2 (two
  wide shots of the stack from different places) was a false positive.
- A card in the Cut room reads each record; the demo declares an L-cut
  (SC-010 P2) and a J-cut (SC-030 P3), and both demos check clean.
- Tests: `tests/test_cuts.py`.

# Open questions

- Bridge generation between two shots (CineGen's "fill gap") as a cut option.
  Deferred until generation exists.
- Cuts between scenes, at the sequence level.

# Amendment: cuts decided in the runtime (2026-09-30, CT-0046)

A cut may also be **decided** through `set_cut` (canvas, CLI, assistant with
a yes). The decision is kept in the scene's `state.json` and stands over the
breakdown's `cut`/`transition` without rewriting it (ADR 0006); `clear_cut`
returns to the breakdown. The record and every check read the decided cut.

Several cuts of one scene may be decided together through `set_cuts`: every
cut is checked first, one refusal refuses the set, and an accepted set is
one revision with one `cuts.set` entry in the history. It is how an agent's
proposal of several cuts is accepted or refused as a whole.

# Amendment: the assembly renders the joins (2026-10-03, CT-0050)

A version of a scene now renders what its cuts say, instead of a straight
cut and a note:

- `cut.split` (seconds, `j` and `l` only, at most 5; 0.8 by default) says
  how far a split edit's sound crosses the picture cut. A **J-cut** takes
  the incoming take's sound from before its cut point (its handle); an
  **L-cut** takes the outgoing take's from after it. The other side's sound
  fades across the split; the borrowed sound has a 0.15 s edge. A take with
  less handle shortens the split, and the version says by how much.
- A **transition** replaces the outgoing shot's last frames and the
  incoming one's first, as `toast build` does: its GLSL shader through GL
  when a context can be made, otherwise its `[render].ffmpeg` stand-in; one
  that can do neither is a straight cut, said in the version. It is at most
  half the shorter shot. The sound crossfades over it; a J/L-cut with a
  transition crossfades instead of splitting.

A version is shorter than the sum of its shots by its transitions. Picture
and sound are made apart (normalised picture pieces; one levelled sound
clip per shot with its handles), then joined, then the sound catalog's
cues (CT-0048) are laid over them on the same timeline.

# Amendment: cuts between scenes (2026-10-03, CT-0051)

The join between two scenes of a sequence is declared on the **incoming
scene**, as a shot's cut is:

```yaml
enter:
  type: hard               # the SPEC's vocabulary
  transition: {id: dip-to-black, duration_ms: 1000, reason: Night falls between them.}
  reason: A new day.
```

The sequence's assembly renders it with the scene assembly's joins: the
transition takes from the end of one scene's version and the start of the
next, the sound crossfades. A version has no sound beyond its ends, so a J
or L join between scenes is a straight cut, said in the sequence version.
`enter` on a sequence's first scene is said and not rendered. Checks:
`cut_type_unknown`, `transition_unknown`, `transition_reason_missing`, as
for shots. The Sequences room shows how each scene is entered.

SINGULAR fades each scene to black at its own end; here that is a
`dip-to-black` into the next scene, a decision on the join rather than a
property of the scene.
