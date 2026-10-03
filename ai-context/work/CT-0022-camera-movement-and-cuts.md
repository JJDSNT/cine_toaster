---
id: CT-0022
title: Camera movement, cuts between clips, and an Arcads-style graph
type: work
status: done
owner: development agent
created_at: 2026-09-29
updated_at: 2026-10-03
tags:
  - camera
  - editing
  - transitions
  - interface
  - evaluation
---

# What

Screen external references for the two problems that hurt generated productions
most: camera movement and cuts between clips. Propose how both become project
records. Evaluate an Arcads-style graph as a view over those records. The
outcome is a spike plan, not a schema change.

# Why

Generated clips fail at the cut more often than inside the shot. A camera move
written as prompt prose can drift between regenerations. An adjacent pair of
shots can be coherent on its own and still not cut together, because the exit
state of one shot does not meet the entry state of the next. ADR 0007 already
makes camera positions project state. Movement and the cut itself are not.

# Done

- Recorded every reference, its licence, and whether its code may be reused in
  [`references.md`](../references.md).
- Ranked the repositories against camera movement, cuts, and the graph view:
  React Flow is the graph base. SceneFlow has state chaining for cuts. AI Video
  Production Editor has blockout-rendered camera moves, but only as ideas under
  GPL. CineGen has bridge generation between clips, also only as ideas because
  it has no licence.
- Confirmed that `taruma/SceneFlow` is the SceneFlow the user follows.
  `sceneflow.camera` is an unrelated product. Read Auteur Script v0.3.0 and the
  SceneFlow v2.3.0–v2.5.0 release notes: Timeline Anatomy and the BRIEF State
  Engine.
- **SceneFlow spike (step 3), 2026-09-29.** Cloned `taruma/SceneFlow` at
  `b1c8c10` (MIT) outside the repository. No code was copied. See
  [SceneFlow spike findings](#sceneflow-spike-findings).

# SceneFlow spike findings

**What SceneFlow actually computes.** Very little. `briefAnalysis.ts` splits
`[<BRIEF>]` lines on `->` and counts macro-states and sub-states per section.
Tags such as `[CAM]`, `[STATE OUT]`, and `[[LOGIC]]` are only highlighted; they
are never parsed into data. The Timeline Anatomy cues are
`{selectedText, startTime, endTime, type, speaker}` spans. They are anchored to
script text, not to states. They are produced by hand-pasting a prompt and JSON
schema into Gemini with the video, then pasting the answer back; the app makes
no model call. "Adherence analysis" is therefore a human reading an LLM's
annotation. It is not a measurement. The value is the **format and the review
loop**, not the code.

**How the Vector Field example handles the cut between generations.** It is
61 s long in 4 parts. Each part is one generation containing about 8 `[CAM]`
setups, so the model makes the cuts *inside* a part. Parts 2–4 add two staging
blocks. `[[CONTINUITY PROTOCOL]]` inherits wardrobe, grade, and physical state
from `@videoN`. `[[VISUAL BLOCKING]]` opens "matching the final frame of
@videoN" and restates the screen sides. So the cut *between* generations is
strategy (a) from step 4: the previous clip is passed as a reference, and the
new opening is written as the previous exit. Strategy (b) is used within each
part. The two strategies are complementary, not alternatives. Step 4 is
reframed below.

**Deriving the brief from our records.** A throwaway script ran on SC-030 of
the demo production, through the real `load_scene` and `parse_geometry`. It
filled the STAGING/EXECUTION scaffold and marked each slot as authored,
derived, or missing:

| Slot | Result |
| --- | --- |
| `[[INTENT]]` | Authored: scene `summary`. |
| `[[LOGIC]]` | **Derived.** The line of action and each subject's screen side per camera come from `screen_side`. This is stronger than SceneFlow, where the author writes the rule as prose and it is never checked. Scene `direction` is appended as authored prose. |
| `[[OPENING]]` | Derived from the first shot's camera, including shot size. Shot size is estimated from the frame width at the target distance, using lens and position (35 mm at 1.7 m → MS). |
| `[CAM]` | Derived: size, lens, and distance. Always "static", because a camera is a fixed position. |
| `[BLOCK]` | Derived: who is in frame and on which side. |
| `[ACT]` | Authored: shot `action`. |
| `[AUDIO]` | Authored `sound`/`lines` when present; none in SC-030. |
| `[[AESTHETIC]]` | Missing: the scene has no look, and wardrobe and props are not records. |
| `[STATE OUT]` | **Missing.** No field says how a shot ends. |

The script also derived a check for each adjacent cut: whether a subject flips
screen side between shots.

**A real defect the derivation exposed.** SC-030's shot 2 is labelled
"Two-shot" on CAM-C. At Mara's declared position she is 44.7° off CAM-C's axis,
and its half field of view is 32.7°, so she is out of frame. The camera frames
where Mara *ends* her walk ("stops two steps short of the stack"), not where
the geometry puts her. Then shot 3 locks CAM-A on her *original* position.
`toast check` passes the scene because geometry holds one position per subject
per scene. **A move within a shot cannot be expressed, so the continuity error
across the P2→P3 cut is invisible.** This is the same gap as camera movement,
on the subject side.

- **SceneFlow versus SPEC-0006 (2026-09-29).** They are complementary:
  coverage is planning ("which lines"), and cues are review ("when").
  Recorded tensions: the source of truth, answered by a derived brief with an
  optional explicit override and an export to SceneFlow's JSON; and multi-shot
  generations, which need a generation unit before plan step 9. See
  SPEC-0006 § Relation to SceneFlow.

# To do

1. ~~Draft and implement SPEC-0005~~ done. The original step read: draft a
   camera-move vocabulary, informed by the 46 moves in
   aicameramovements.com's taxonomy but written here. Attach a move to
   `[[geometry.cameras]]` as start pose → end pose, speed, and end state. Add a
   `toast check` rule that flags a move crossing the line of action.
   **Extend the same idea to subjects.** A shot may declare a subject's end
   position, and the next shot inherits it. Then SC-030's P2→P3 position jump
   becomes a check finding. Fix the SC-030 fixture once the field exists; until
   then the fixture documents the gap.
2. ~~Draft and implement SPEC-0007~~ done: the cut record, five checks, and
   the Cut room's join cards. Bridge generation stays open until generation
   exists. The original step read: draft a `cut` record between adjacent shots with these fields: exit state,
   entry state, cut type (hard, match, action, J/L), frame chaining
   (last→first), optional bridge generation, and an optional catalog transition
   with a required `reason` (SPEC-0004). Decide whether it belongs in
   SPEC-0004 or a new specification.
3. ~~Spike SceneFlow~~ done. ~~Brief builder~~ done (plan step 4,
   2026-09-29): `brief.py`, `toast brief`, `/api/brief`, and the Brief panel.
   Every slot is badged authored, screenplay, derived, or missing. The review
   runs on **local** take video in Cine Toaster, at the user's request; the
   export keeps SceneFlow's JSON shape plus `video`, with an empty
   `youtubeId`. Still open:
   - recording a review's re-timed cues and adherence verdicts as production
     records, through a command;
   - an explicit per-shot brief override;
   - `[STATE OUT]` from wardrobe and props, which are not records;
   - a local-video patch to SceneFlow, if we want to open exports there.

   The original follow-up read: when a generation adapter exists,
   promote the derivation into a provider-neutral brief builder: authored
   fields plus geometry, emitted in Auteur Script form. Add `state_out` and
   `look`-provided wardrobe as the two missing inputs.
4. Measure the granularity trade-off on one real sequence. Vector Field shows
   that the strategies nest: model-made cuts inside a generation, and
   reference-chained cuts between generations. The open question is **how many
   shots belong in one generation**. Test 1, 3, and 8 setups per generation.
   Record continuity, screen direction, control over individual shots, and the
   cost of regenerating one shot. This needs a generation adapter, so it
   follows Phase 2.
5. Spike: build a React Flow prototype on a real sequence. Nodes are shots with
   the selected take, and edges are cuts. Edge edits call the shared commands.
   Compare it with the Cut and Transitions rooms (`CT-0020`).
6. Later, when a generation adapter exists, pass the declared move and chained
   frames to the provider. Measure drift against the declared move.

# Decisions

- The graph interaction model is **Arcads-style**: cards are production objects
  such as shots, takes, cast, and cuts. Users do not wire model parameters
  ComfyUI-style. This replaces the ComfyUI analogy recorded in `CT-0020`.
- The graph is a projection of project records. It is never its own file
  format.
- Copyleft and unlicensed references are studied and reimplemented, never
  copied (ADR 0011).
- SceneFlow is adopted as a **format and review-loop reference**, not as a
  dependency. Its code contributes nothing we lack, and its tags are not
  parsed.
- Briefs are **derived from records, never authored as the source of truth**.
  Screen sides and the axis come from geometry, so the brief cannot contradict
  what `toast check` verifies. SceneFlow cannot give that guarantee.

# Validation

- Screening: repositories inspected through GitHub metadata and READMEs on
  2026-09-29.
- SceneFlow spike: cloned at `b1c8c10` into a session scratch directory. Read
  `briefAnalysis.ts`, `scriptProcessor.ts`, `cues.prompt.ts`, `RawCuesModal.tsx`,
  and `public/examples/scenes/scene_vector_field.json` (4 parts, 164 cues,
  61 s).
- Derivation prototype: a throwaway script (not committed) run with
  `PYTHONPATH=src .venv/bin/python` on `examples/demo-project` SC-030. Per-camera
  subject angles were verified independently: CAM-C half-FOV 32.7°, Mara at
  44.7°. No repository code changed, so no test run was needed.
- Brief: `tests/test_brief.py` (14 tests); a headless screenshot of the
  Brief panel with a local take playing.
- SPEC-0007: `tests/test_cuts.py` (14 tests), the full suite, `toast check` on
  both demos, and a headless screenshot of the Cut room with a scratch-only
  `chain: frame` finding.

# Closed (2026-10-03, close-out pass)

Movement (SPEC-0005), the cut record (SPEC-0007), the brief and SceneFlow export are delivered; the joins render in versions (CT-0050, CT-0051).

What remains moved to the backlog (`development/roadmap.md` § Backlog): Review records (re-timed cues, adherence verdicts) through a command; a per-shot brief override; `[STATE OUT]` from wardrobe and props; the shots-per-generation granularity measured on a real sequence.
