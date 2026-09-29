---
id: SPEC-0005
title: Movement within a shot — camera moves, subject marks, and a shot's exit state
type: specification
status: implemented
implementation: complete
owner: project
created_at: 2026-09-29
updated_at: 2026-09-29
tags:
  - project-core
  - geometry
  - camera
  - continuity
---

# Goal

A shot can declare how its camera moves and where its subjects go. From those
declarations, the scene's geometry answers three questions:

1. What does the frame hold at the start of the shot, and at the end?
2. Does anything cross the line of action while the shot plays?
3. Does the end of one shot meet the start of the next?

The answers are checkable before anything is generated. A generation adapter
can read them instead of re-parsing prose (ADR 0007, CT-0022).

# Context

ADR 0007 made scene geometry project state. That geometry has two limits:

- **A camera is a fixed named position.** A move can only be written as prose.
- **A subject has one position for the whole scene.** Nobody can walk during a
  shot.

The SceneFlow spike (CT-0022) showed what the second limit costs. In demo scene
SC-030, shot P2 is a "two-shot" whose camera frames the point where Mara *ends*
her walk. At her declared position she is 44.7° off that camera's axis, outside
its 32.7° half field of view. Shot P3 then frames her original position. The
P2→P3 position jump is a continuity error, and `toast check` passes the scene,
because the data cannot say she moved.

The obvious vocabulary is a flat list of named moves, such as the 46 on
aicameramovements.com. A flat list mixes independent dimensions in one name:

- *Whip pan right* is a pan, rightward, very fast.
- *Crash zoom in* is a zoom, inward, very fast.
- *Drone push in* is a dolly-in from a drone.
- *Low tracking* is a track from a low height.

A flat list grows with every combination and cannot be checked against
geometry. This specification separates the dimensions. It derives what it can
from start and end poses, and it accepts a declared name only as intent.

# Model

## Marks

A mark is a named point on the plan: the theatre sense of "hit your mark".
Marks sit beside subjects and cameras in the scene geometry.

```yaml
geography:
  marks:
    - id: HALFWAY
      x: 2.6
      y: 2.3
      label: Two steps short of the stack
```

A subject's `x`/`y` in `geography.subjects` remains its position **at the start
of the scene**.

## Subject movement

A shot may move subjects:

```yaml
shots:
  - n: 2
    camera: CAM-C
    subjects_move:
      - subject: MARA
        to: HALFWAY          # a mark id, or [x, y]
```

**Positions are inherited in shot order.** A subject's position at the start of
a shot is its position at the end of the previous shot. At the start of the
scene it is the geography position. A shot that does not move a subject leaves
it where it is.

A shot that follows an elided time jump may restate positions:

```yaml
    subjects_at:
      - subject: MARA
        at: CONSOLE
```

`subjects_at` is an explicit reset. It is never inferred. Without it, a subject
cannot be anywhere other than where the last shot left it.

## Camera movement

A camera stays a named fixed position (ADR 0007). The shot's `camera` names its
**start** pose. A shot may declare a move:

```yaml
    camera: CAM-A
    move:
      to: CAM-A2            # a camera id, or an inline pose (below)
      speed: slow           # slow | steady | fast | snap
      rig: dolly            # optional; see "Rig"
      kind: dolly_in        # optional; declared intent, checked against poses
```

An inline end pose overrides only what changes:

```yaml
    move:
      to: {lens_mm: 85}                    # a zoom
      speed: snap
```

```yaml
    move:
      to: {x: 3.0, y: 1.4, target: MARA}   # a move with a new position and aim
```

A named end pose (`to: CAM-A2`) keeps every position in the geometry, so the
blockout can draw it. Inline poses exist for small adjustments that do not
deserve a name.

A move whose target is a subject id resolves the target **at that moment**.
This makes a camera that follows a walking subject a plain declaration: the
subject moves, the camera's target moves with them.

## Movement kind

The kind is **derived** from the difference between the start and end poses.
When the author also declares `kind`, it is checked against the derived one.

| Kind | Derived when |
| --- | --- |
| `static` | No move is declared, or start and end poses are equal. |
| `pan` | Same position, and the target's plan bearing changes. |
| `zoom` | Same position and target, and `lens_mm` changes. |
| `dolly` | The position moves along the view direction: `in` toward the target, `out` away from it. |
| `truck` | The position moves perpendicular to the view: `left` or `right` on screen. |
| `arc` | The position moves around the target at a near-constant distance: `left` or `right`. A full circle is an orbit, which is an arc with `degrees ≥ 300`. |
| `pedestal` | Only `height` changes: `up` or `down`. |
| `crane` | `height` changes together with plan position. |
| `track` | The target is a subject who moves during the shot, and the camera position moves too. |
| `tilt` | Declared only; never derived. |

A move that combines components, such as a dolly with a pan, is reported as its
dominant component. The others are listed as secondary. Tolerances are named
constants beside the existing ones in `geometry.py`: `ON_AXIS_TOLERANCE_M` and
`CENTRED_ANGLE_TOLERANCE_DEG`.

**Vertical aim is not modelled.** Targets are 2D points, and camera height is
optional (ADR 0007). A tilt is therefore declared with `kind: tilt` and a
direction, and never derived. Pedestal and crane are derived only when both
heights are present. As in ADR 0007, a derivation invented from a default
height is worse than none.

Direction words (`left`, `right`, `in`, `out`, `up`, `down`) are computed in
**screen space** from the start pose. "Truck right" means the frame content
slides left, which is what an editor means. This uses the same convention as
`screen_side`.

## Speed

`speed` is one of `slow`, `steady` (the default), `fast`, and `snap`. `snap`
covers what the flat lists call whip, crash, and snap moves. Speed is intent
for the brief and for the provider; it is not geometry. It is still recorded,
because regenerating a shot must not lose it.

## Rig

`rig` describes how the camera is supported. It changes the texture of the
image, not where the camera goes. Values:

`tripod`, `dolly`, `slider`, `steadicam`, `handheld`, `body`, `crane`,
`drone`, `vehicle`.

A rig may be declared on the shot or inherited from the scene's look (the
SPEC-0004 cascade). The rig has one check: a `handheld` shot with `speed:
snap` is legal. There are no other rig checks, because a rig constrains a move
only loosely. A drone can do almost anything.

## Exit state

A shot's exit state is **computed**, not authored:

- the end camera pose;
- every subject's end position;
- for each subject inside the end frame, its screen side.

What geometry cannot express is authored as one optional sentence:

```yaml
    ends_on: Mara's hand still on the console switch.
```

The brief builder emits the computed exit state as SceneFlow's `[STATE OUT]`,
and the next shot's start as `[STATE IN]`. `ends_on` is appended verbatim. The
cut record (CT-0022 step 2) compares exit and entry states.

# Checks

New `toast check` findings, following `docs/continuity-checks.md`:

| Code | Severity | Meaning |
| --- | --- | --- |
| `move_crosses_axis` | error | The camera path crosses the line of action during the shot. The axis is evaluated between the axis subjects' positions at the start of the shot. |
| `subject_path_crosses_axis` | warning | A subject crosses the line of action. It is legal, often deliberate, and it redefines screen direction for every later shot. |
| `move_kind_mismatch` | warning | The declared `kind` disagrees with the kind derived from the poses. |
| `framed_subject_missing` | warning | A shot names `subject`, but that subject is outside the frame at both the start and the end of the shot. |
| `cut_screen_flip` | warning | A subject is in frame at the end of shot N and at the start of shot N+1, on opposite screen sides. This does not replace `axis_break`, which reasons about camera placement. |
| `unknown_mark` | error | A `to`, `at`, or target names a mark that the geometry does not declare. |
| `movement_subject_missing` | error | A shot moves or places a subject the geometry does not define. *Added during implementation.* |
| `move_value_unknown` | error | `speed`, `rig`, or `kind` is outside the vocabulary. A typo must not silently become a steady move. *Added during implementation.* |

What stays deliberately unchecked, in the spirit of ADR 0007:

- Positions are never inferred from prose. P2's action text says Mara walks,
  but without `subjects_move` nothing moves.
- Tilt, pedestal, and crane are skipped when the heights are not declared.
- A rig never forbids a move.

# The 46-move taxonomy against this model

This coverage table maps aicameramovements.com's names; no prompt text is
used.

| Their category | Count | Here |
| --- | --- | --- |
| Pan/Tilt | 7 | `static`; `pan` ±, `speed: snap` for a whip; `tilt` (declared). |
| Zoom/Lens | 6 | `zoom` in/out × `slow`/`fast`/`snap`. |
| Dolly/Track | 9 | `dolly`, `track`, or `truck`. *Follow*, *reverse tracking*, *side*, *low*, *vehicle*, and *chase* differ only by the start pose, the rig, or the subject's move. |
| Physical moves | 11 | `truck` ±, `pedestal` ±, `truck` with `rig: slider`, `arc` ±, orbit (`arc`, degrees ≥ 300). *Push past* is a `dolly` whose path passes a subject; the derived path makes it visible. |
| Human camera | 2 | `rig: handheld` or `rig: body`, with any kind. |
| Drone/Crane | 5 | `crane` ±, `dolly` with `rig: drone`, `rig: vehicle` for a helicopter shot. |
| Specials | 6 | **Out of scope.** First-person view is a point of view, not a move; tilt-shift and time-lapse are image treatments (`ops` or a look); infinite zoom, earth zoom, and pass-through are effects. |

The 40 in-scope names reduce to 10 kinds × direction × 4 speeds × 9 rigs. None
of the 40 needs a new kind.

# Worked example: SC-030 corrected

```yaml
geography:
  marks:
    - {id: HALFWAY, x: 2.6, y: 2.3, label: Two steps short of the stack}
shots:
  - n: 2
    camera: CAM-C
    subjects_move: [{subject: MARA, to: HALFWAY}]
    ends_on: Mara stopped, facing the stack.
  - n: 3
    camera: CAM-A          # target MARA resolves to HALFWAY now
    subject: MARA
    looks_at: SPEAKER
```

With this, P2 ends with Mara centred in CAM-C's frame (0.0°). P3 aims CAM-A at
her new position: 1.61 m from the camera instead of 1.48 m, and the framing is
derived again. The speaker stack is at −26.0° and stays outside CAM-A's 19.8°
half field of view. All values were measured with `screen_side` on the demo
geometry. `cut_screen_flip` evaluates P2→P3 on real positions. If the author
instead meant her to walk back, P3 must say so with `subjects_move`, and the
brief says so too.

# Compatibility

- Every field is optional. A scene without them behaves exactly as today.
- `camera` keeps its meaning: the pose at the start of the shot. For a static
  shot, that is the whole shot.
- Existing geometry keys and legacy names are unchanged. New keys have no
  legacy names (`vocabulary.py`: "nothing new is added here").

# Acceptance

- Parsing marks, `subjects_move`, `subjects_at`, `move`, and `ends_on` from
  scene YAML, with validation errors naming the scene and shot.
- A function returning each shot's start and end state, with inherited
  positions, that the checks, the brief builder, and the blockout share.
- Movement-kind derivation, with a test for every row of the kind table and a
  test for a combined move.
- Every check in the table above, with a passing and a failing test.
- SC-030 updated as in the worked example, and `toast check` still passing on
  both demos.
- The blockout draws marks, subject paths, and camera paths.
- A `toast why` practice for each new check (ADR 0009).

# Implementation notes

- The code is in `src/cine_toaster/movement.py`. It provides `shot_motions`,
  `derive_kind`, and `check_movement`. Marks are in `geometry.py`, and loading
  is in `project.py`.
- Each shot exposes `motion`: its start and end state, its kind, and the
  subjects framed at each end. The blockout and a future brief builder read it.
- The existing eyeline-direction check now uses where the subjects stand when
  each shot begins, not where the scene began.
- A camera aimed at a subject id follows that subject when the subject moves.
  With no `move`, that shows up as a pan.
- Validated with 30 tests in `tests/test_movement.py`, and with headless
  screenshots of the SC-030 blockout: all shots; P2, where Mara walks to her
  mark; P3; and a scratch dolly-in on P1.

# Open questions

- Should a shot be able to hold several successive moves (move, then pan)? The
  proposal is no: split it into shots or accept the dominant-kind description.
  Revisit if real productions disagree.
- Easing (`ease_in`/`ease_out`) is omitted until a provider can be shown to
  honour it.
- Whether a move's intermediate path is a straight segment or a declared curve.
  The proposal is straight, except for `arc`, which is circular about the
  target.
