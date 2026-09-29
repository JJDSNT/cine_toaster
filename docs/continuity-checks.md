# Continuity checks

`toast check <project>` reads the scene geometry and reports the mistakes that
survive shot-by-shot review and only appear once the scene is cut.

The checks are static. Nothing is generated, nothing is watched, no model is
called. They run in milliseconds against the authored scene file, which is the
point: this is the cheapest moment to find these problems.

Exit code is `1` if any finding has severity `error`, otherwise `0`, so the
command can gate a generation run.

## What is checked

| Code | Severity | What it means |
|---|---|---|
| `axis_break` | error | Cameras used in the scene sit on both sides of the declared line of action. Cut together, the two characters appear to swap places and stop looking at each other. |
| `axis_subject_missing` | error | The line of action names a subject the geometry does not define. |
| `eyeline_mismatch` | error | Two characters in conversation both look toward the same side of frame. Cut together they will not appear to look at each other. |
| `eyeline_subject_missing` | error | A shot declares a subject or interlocutor the geometry does not define. |
| `unknown_camera` | error | A shot references a camera id that the scene geometry does not declare. |
| `eyeline_height_flip` | warning | One subject is filmed from above by one camera and from below by another. Unless deliberate, this breaks the sense of one place. |
| `camera_outside_room` | warning | A camera position falls outside the declared room. Usually a typo in the measurements. |
| `subjects_overlap` | warning | Two subjects are closer than 25 cm and will read as one body. |
| `move_crosses_axis` | error | A camera move (dolly, truck, arc…) crosses the line of action during the shot. |
| `subject_path_crosses_axis` | warning | A character crosses the line. Legal and often deliberate; it redraws the line for every later shot. |
| `cut_screen_flip` | warning | A character leaves one shot on one side of frame and enters the next on the other. |
| `framed_subject_missing` | warning | A shot names who it is on, but its camera frames them neither where the shot starts nor where it ends. |
| `move_kind_mismatch` | warning | The move a shot names disagrees with the move its start and end positions describe. |
| `move_value_unknown` | error | A move's `speed`, `rig` or `kind` is outside the vocabulary. |
| `unknown_mark` | error | A shot sends a character or camera to a mark the geometry does not declare. |
| `movement_subject_missing` | error | A shot moves a character the geometry does not define. |

## Movement within a shot

A character's position in the geometry is where they stand when the scene
begins. A shot can send them to a named mark (`subjects_move`), and the next shot
finds them there; a time jump restates positions with `subjects_at`. A shot's
`camera` is where it starts; `move.to` is where it ends, and the kind of move is
derived from the two, not taken from its name. See
[`SPEC-0005`](../ai-context/specs/SPEC-0005-movement-within-a-shot.md).

```yaml
geography:
  marks:
    - {id: HALFWAY, x: 2.6, y: 2.3, label: Two steps short of the stack}
shots:
  - n: 2
    subjects_move: [{subject: MARA, to: HALFWAY}]
    ends_on: Mara stopped, facing the stack.
  - n: 3
    move: {to: CAM-A2, speed: slow, rig: dolly, kind: dolly_in}
```

Nothing is read from prose: an action line that says she walks moves nobody.

## What is deliberately not checked

**The axis is never inferred.** It is only checked when the author declares
`[geometry.axis]`. Two characters in a room do not always define the line, and a
checker that guesses will eventually accuse a correct scene. One false
accusation costs more trust than several true findings earn.

**Heights are only checked when declared.** A camera with no height is skipped
rather than assumed, because a finding derived from a default is noise wearing
the costume of a fact.

**Eyelines are only checked between shots that declare them.** A shot states
`subject` (who it is on) and `looks_at` (who they are addressing). Two people in
a room do not always define a conversation, and a crowd never does.

**Cameras that no shot uses are ignored.** A position parked in the geometry for
later is not coverage.

## Reading a finding

Findings name the measured distance from the line, not just a verdict:

```
ERROR  SC-030  axis_break
  Camera(s) CAM-C (1.50 m) cross the line of action between Mara Vale and
  Speaker stack; CAM-A (0.51 m), CAM-B (0.31 m) stay on the other side.
  shots: SH-030-02
```

Reproduce it with `toast demo`, then move `CAM-C` to the far side of the room
in `scenes/030-echo-chamber/scene.toml` and run `toast check`.

A camera 8 cm off the line is a different conversation from one 1.5 m off, and
the author is the one who can tell them apart. The check reports geometry and
names the affected shots; it does not overrule the director.

## Why, not just what

Every check has a recorded practice behind it explaining the rule, what it costs
when missed, and the evidence:

```bash
toast why eyeline_mismatch
```

The interface shows the same text under the finding. A check nobody can explain
is a check nobody will trust. See
[`ADR 0009`](architecture/0009-knowledge-is-evidence-linked-data.md).

## Checking against the plan, not the footage

These checks read the staging plan. A generated shot can disagree with it — the
gaze in a clip follows the starting image more than the plan does. A finding
therefore says the plan implies a problem, which is the cheap half of the work.
The frames still have to be looked at.
