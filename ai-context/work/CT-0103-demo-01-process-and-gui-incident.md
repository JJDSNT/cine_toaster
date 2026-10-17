---
id: CT-0103
title: Demo 01 incident -- storyboard skipped and the GUI failed to expose the intended process
type: work
status: review
owner: codex
created_at: 2026-10-16
updated_at: 2026-10-16
tags:
  - incident
  - demos
  - production-flow
  - gui
  - onboarding
  - validation
---

# What

Incident report and a repeatable validation scenario for Demo 01,
`~/films/demo-01` (CT-0099). The director opened the GUI and found neither the
expected AI assistant nor a visual storyboard preceding the blockout. The
director then asked whether the failure belonged to the agent, the product or
onboarding, and requested this document to guide work on the GUI and process.

This record documents observed behavior, responsibility and evidence needed to
validate a correction. It does not implement or select a new UI or schema.

# Why

Demo 01 is the first demo intended to become a complete film. Testing whether
the proposed filmmaking method actually works is one of its purposes. A CLI
that renders successfully and a directory containing valid records are
insufficient evidence that a filmmaker can follow and review that method.

The intended order, stated in `production-flow.md`, is:

`screenplay -> storyboard -> blockouts -> master images -> clips -> sequences`

Screenplay and storyboard are iterative. Blockouts refine spatial decisions;
their availability does not establish that the visual storytelling was reviewed.

# Incident sequence

1. The agent read the production flow and the demo's work record.
2. It reviewed visual identity trials, wrote a seven-scene screenplay and
   authored a 24-shot breakdown, planned at 103 seconds.
3. It described this textual breakdown as an initial storyboard and moved to
   measured geography, cameras and paths before completing a shot-by-shot
   visual storyboard that the director could review.
4. It rendered six clay frames and a 12-second opening animatic. These establish
   some camera geometry; the mannequin cannot show the scripted waking poses,
   and the butterfly is placed on the ground.
5. Asked to launch the GUI, it ran `toast serve ... --host 127.0.0.1 --port 8765`
   without `--assistant` and linked `/app/`, the canvas.
6. The agent verified HTTP 200, but did not verify that the director could find
   the screenplay, storyboard and assistant in the launched experience.
7. The director identified the missing assistant and storyboard and questioned
   the order. The agent acknowledged the premature advance and investigated.

# Expected and observed

| Area | Expected for this demo | Observed |
| --- | --- | --- |
| Production stage | Screenplay and a reviewable storyboard before spatial refinement | Screenplay and textual shot coverage existed; a complete visual storyboard did not |
| Storyboard | Ordered visual intent linked to screenplay and cuts | The room uses shot stills; current references and clay boards were not presented there as a complete storyboard |
| Blockout | A refinement of storytelling decisions whose limits are visible | A three-shot clay opening was rendered before the missing visual stage was resolved |
| Assistant | The expected directing assistant is available, or its status is explained | Server launched without its optional assistant; the UI hides the button when its info endpoint is unavailable |
| Entry point | The director can locate the current phase and its work | Canvas URL supplied without explaining the Control Room and screenplay routes |
| Completion claim | Evidence identifies what was authored, rendered, reviewed and approved | "Storyboard" was used for a textual breakdown; HTTP success was treated as enough GUI validation |

# Responsibility and contributing causes

## Agent execution -- primary responsibility

The ordering was available and had been read. The agent conflated a shot list
with a reviewable visual storyboard, advanced without resolving the difference,
and used language that overstated completion. It also omitted `--assistant`
from the launch command. These are execution errors, not evidence that the
product or onboarding forced that behavior.

The status message from `toast status` emphasized shots awaiting generation;
the agent should have interpreted that against the actual pre-production stage
rather than treating an available downstream operation as the next task.

## Product and GUI -- demonstrated gaps

- `renderStoryboard()` in `web_assets/app.js` displays `frame.still`; its empty
  state directs users toward assembly, `toast still` or take imagery. That does
  not explain how to develop a storyboard before production.
- `writing_room()` in `project.py` exposes the shot's discovered still.
  `discover_stills()` reads `stills/<scene>/<shot>.<image extension>`.
  `board.py` writes clay boards to `renders/boards/<scene>/`. The storyboard
  room does not use that board listing, nor assign the film's references to
  individual shot cards.
- This is a discovery and workflow gap. The earlier conversational claim that
  storyboard images necessarily depend on takes was too broad: a still can
  exist independently. The implementation's path conventions alone do not
  provide a visible author/revise/review workflow.
- `assistant-drawer.js` returns without a control if `/api/copilotkit/info`
  fails. The React canvas likewise renders the button only when enabled.
  Off, unavailable and failed are not explained through that control.
- `/app/` and the Control Room offer different entry points. Successful HTTP
  delivery did not establish discoverability of the intended workflow.

These observations do not prove every relevant capability is absent. A focused
GUI investigation must separate a missing feature from an undiscoverable one.

## Onboarding -- conflicting vocabulary and incomplete task guidance

- `production-flow.md` states storyboard before blockout, while its storyboard
  row names shots, cuts, canvas and brief. These are necessary records, but the
  row does not establish when a visual storyboard is sufficiently reviewable.
- CT-0025 describes blocking frame -> optional sketch -> master -> video and
  permits moving from blocking directly to a master. That concerns fidelity,
  but can be misread as the complete production order.
- `docs/assistant.md` documents `--assistant` correctly. The failure to use it
  is not missing documentation. Discoverable launch/readiness feedback is a
  separate product question.
- Runtime guidance must be sufficient without development memory. A recovery
  based only on extra instructions in `AGENTS.md` would leave the filmmaking
  workflow problem unresolved.

# Impact and preserved evidence

- The director could not inspect the expected pre-production process from the
  provided entry point. Work advanced before the process itself was validated.
- Camera/render experiments were useful, but did not validate the proposed
  method or complete the storyboard stage. They must remain labelled as such.
- The production has seven scenes, 24 proposed shots, 13 visual references and
  opening blockout outputs. No storyboard approval was committed.
- All generated images remain preserved. Correcting this incident must keep
  the original board, every identity trial, prompts, lineage, breakdown and
  initial clay render pass. Revised candidates are additional versions.
- There is no evidence of production-state loss from this incident. The
  assistant was not started in the launched session.

# Done

- Follow-up implementation: CT-0104 delivers a first read-only GUI pilot with
  script/shot navigation and distinct composition studies. It addresses part
  of the discovery problem; candidate authoring and complete process validation
  remain open. The incident is still under review.
- Captured the incident, its observed sequence and the distinct contributing
  causes; corrected the overly broad diagnosis about takes.
- Defined the GUI validation scenario below and linked it from the demo work
  record, work index and project status.
- Corrected the active next action: validate screenplay/storyboard navigation
  and review before expanding the remaining blockouts.

# To do

1. Walk the current GUI with the director's actual production state and record
   where screenplay, storyboard, references, blockout and assistant are found.
2. Agree on the storyboard review contract: what each shot must communicate,
   which visual fidelities suffice, and how draft, reviewed and approved differ.
3. Reconcile the vocabulary across the flow, guide, fidelity documentation and
   UI. Identify needed capabilities before choosing UI or persistence changes.
4. Propose and implement focused changes in their own work/spec records as
   needed; rerun the scenario below with preserved before/after evidence.
5. Resume Demo 01 from the incomplete storyboard stage. Reuse the opening
   blockout experiment when it helps validate the storytelling.

# Decisions

- This report is ready for review; the incident is not resolved by documenting
  it. No UI redesign, automatic stage blocking or new gate is approved here.
- Existing storyboard approval remains a human decision. The current gate is
  advisory and blocks nothing; this report does not change that contract.
- Creative iteration may revisit earlier steps. Exploratory blockouts may be
  useful, provided their purpose and the unfinished upstream work are explicit.
- Successful artifacts, correct CLI output and green tests do not substitute
  for observing the filmmaker complete the intended GUI task.

# Validation

## Evidence inspected

Conversation and CT-0099; `production-flow.md`; CT-0025; `docs/assistant.md`;
`cli.py` (`command_serve`); `web_assets/app.js` (`renderStoryboard`);
`project.py` (`writing_room`, `discover_stills`); `board.py`;
`web_assets/assistant-drawer.js`; `frontend/src/App.tsx`.

This was a source/record inspection, not a browser usability test. Full GUI
behavior and assistant conversation remain to be exercised.

## Repeatable GUI acceptance scenario -- pending

Use Demo 01 with no chosen takes and no storyboard approval. Keep all existing
artifacts. Record the entry URL, startup mode and capability state. Capture
screenshots and any CLI/manual file work required at each step.

| ID | Filmmaker task | Evidence required to pass |
| --- | --- | --- |
| V1 | Open the production | Recognize Demo 01, its actual phase, unfinished storyboard and next review task without terminal or development notes |
| V2 | Read the screenplay | Reach the seven scenes and navigate from text to its covering proposed shots and back |
| V3 | Review the storyboard before clips exist | See ordered shot cards, duration, narrative/action intent, cuts and visual candidates or explicit missing visuals; a shot list alone is not claimed as a completed visual review |
| V4 | Develop one shot's visual intent | Reach a supported sketch/reference/board path and relate the result to that shot; a concept board is identifiable as reference, not silently treated as its approved storyboard |
| V5 | Revise and compare | Preserve earlier imagery and rationale; identify which candidate is being reviewed and whether it reflects the current screenplay/shot plan |
| V6 | Consult the assistant | With `--assistant`, find the control and ask about the visible scene; it recognizes actual stage and pending decisions. Without it or on failure, understand the state and recovery path |
| V7 | Refine through blockout | Navigate from a storyboard shot to its measured layout and back; understand that mannequins do not validate poses, acting, flight or vertical climbing unless represented |
| V8 | Make the human decision | Review the storyboard before approving it; verify the recorded approval, actor and revision, and visibility of later changes |
| V9 | Reopen the application | Recover authored work, candidates, decisions and phase from production records; no dependency on this chat |

For each task record pass/fail, observed route, unexpected steps, missing
information and workaround. A task completed by shell/file editing does not
pass its GUI criterion; keep the workaround as evidence. Use the first scene
as the initial test, then review the seven-scene sequence for coherence.

Closure requires the director to review evidence that the process can be
followed, with remaining limitations explicitly accepted. It does not require
every hypothesis about the film or every future GUI feature to be solved.
