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
| `script_scene_missing` | error | A scene is linked to a screenplay heading the screenplay does not contain. |
| `script_anchor_missing` | error | A shot covers a quote that is not in its screenplay scene — usually a rewrite. |
| `script_anchor_ambiguous` | error | A shot's quote matches more than one place; lengthen it. |
| `dialogue_uncovered` | warning | A line in the screenplay that no shot covers: a line nobody films. |
| `line_drift` | warning | A shot's line in the breakdown differs from the screenplay. The screenplay's words are used. |
| `line_unscripted` | advice | A shot's line the screenplay does not contain there. Possibly a deliberate ad-lib. |
| `cut_type_unknown` | error | A shot's `cut.type` or `cut.chain` is outside the vocabulary. |
| `jump_cut_undeclared` | warning | Two adjacent shots see the same subject from under 30° apart, at nearly the same size and screen place. It reads as a jump; declare `type: jump` if meant. |
| `chain_pose_mismatch` | warning | A shot chains the previous last frame, but its camera or a subject starts somewhere else. |
| `split_edit_without_sound` | warning | An L-cut whose outgoing shot ends on no dialogue, or a J-cut whose incoming shot starts on none. Judged only when the scene is linked to a screenplay. |
| `transition_reason_missing` | advice | A catalog transition without a `reason`. |

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

The same numbers draw the **blocking frame**: what the shot's camera sees at
its start and end, with subjects as silhouettes, the room, the axis and the
marks. Select a shot in the scene's blockout to see it, or run
`toast frame <project> <scene> <shot> [--at end] [--output f.svg]`. It is
computed on demand and never stored, and whoever the checks call framed is
inside it, on the same side (CT-0025).

A shot that moves also plays as a **light previs**: the same frame sampled
over the shot's duration, with the camera and subjects interpolated between
their declared positions. Use `toast frame … --at 0.5` for one moment, or
`toast previs <project> <scene> <shot> --output p.mp4` for the animatic
(CT-0029).

## Which screenplay each shot holds

A scene names the screenplay scene it films, and each shot quotes the start of
the part it covers (SPEC-0006). The words live only in the screenplay; a
shot's `lines` add how they are delivered, voiced and mixed.

```yaml
script:
  heading: INT. LISTENING STATION - NIGHT
  occurrence: 2                       # the same heading appears twice
shots:
  - n: 3
    covers:
      from: "SPEAKER STACK: That's it"  # CHARACTER: restricts to their speech
      to: The stack repeats it
```

`toast script show <project>` prints what each shot covers, in screenplay
order. `toast script link <project>` proposes `script` and `covers` for shots
that already carry lines — it writes nothing. The storyboard shows each frame's
lines, and the Script room shows the screenplay with its shots in the margin.

## How each shot becomes the next

A shot's `cut` says how it is entered, as its `transition` already does
(SPEC-0007). Every field is optional; no `cut` is a hard cut. Cuts between
scenes belong to the sequence and are not checked here.

```yaml
shots:
  - n: 3
    cut:
      type: j               # hard | match | action | j | l | smash | jump
      chain: frame          # this shot starts on the previous last frame
      reason: We hear the stack speak before we see her hear it.
```

The Cut room shows every join: the two shots, the cut, what the outgoing shot
leaves framed and what the incoming one finds, the line on each side, and what
is wrong with it.

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
