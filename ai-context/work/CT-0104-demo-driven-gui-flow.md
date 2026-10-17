---
id: CT-0104
title: Rethinking the GUI through Demo 01's actual production flow
type: work
status: review
owner: codex
created_at: 2026-10-16
updated_at: 2026-10-16
tags:
  - gui
  - ux
  - production-flow
  - demos
---

# What

First concrete design proposal following the director's request to rethink the
GUI against the actual filmmaking flow exposed by Demo 01. Builds on the
incident in CT-0103 and the existing three-workspace research in CT-0084--0095.
The proposal is for discussion and a focused prototype, not an accepted ADR or
authorization to rewrite the existing Control Room.

# Why

Demo 01 currently requires the director to reconcile screenplay, textual shot
plans, visual references, clay previews and chat explanations across separate
places. The GUI should help the director make the next creative decision and
understand what exists, what is proposed and what has actually been approved.
Feature availability does not establish a sensible production order.

# Done

- Implementation started: an additive React pre-production page using existing
  read APIs, retaining existing Control Room, editor and canvas routes. First
  slice is inspection/navigation; candidate authoring and approval stay in
  existing supported tools until their command contracts are established.
- Delivered `/app/preproduction.html`, linked from the Control Room. It reads
  existing writing, scene, board and assistant endpoints. It displays linked
  script/shot selection, scene approval state, missing visuals, discovered
  stills and a distinct start/end composition study with scene preview.
- Added URL selection with back/refresh, cancellable scene reads, explicit
  loading/error states, an always-visible assistant entry and contextual iframe
  messages using the existing `Seen` contract. No new film writes or schema.
- Added `docs/preproduction.md` and a repeatable, read-only Playwright
  walkthrough. Desktop and mobile screenshots were inspected.
- Extended the existing UI capability check in `toast doctor`: an older build
  missing `preproduction.html` is reported with the `make ui` remedy. Added a
  partial-build regression test and verified it separately after that change.
- Read CT-0084, CT-0085, CT-0087, CT-0089, CT-0090 and CT-0095 and compared
  their hypotheses with CT-0103 and current navigation/editor code.
- Defined a candidate information architecture, a first pre-production layout,
  actual Demo 01 states, implementation gaps and a small validation scope.
- Linked this proposal from the work index and active project status.

# Proposed organizing principle

**Direction updated by the director, 2026-10-16:**
[CT-0105](CT-0105-creation-inception-and-stage-inputs.md) adds Creation /
Inception before Screenplay & Storyboard, for brainstorming and reference
exploration. The three-workspace proposal below and its current pilot describe
the remaining activities; they are no longer the entire proposed navigation.
Outputs must be explicitly reusable as versioned inputs to later work. The
new module and handoff writes are not implemented by the read-only pilot.

Three workspaces express different questions about the same film. They are
freely accessible; production can contain scenes at different stages. Do not
force the entire film into a single linear progress state.

| Workspace | Main question | Primary work |
| --- | --- | --- |
| Screenplay & Storyboard | What happens, and how will the audience see it? | Write, break down, arrange visual shots, compare references, refine composition and review |
| Production | What material must be made, and which result serves the shot? | Masters, input review, generation, takes, comparisons and human choices |
| Editing & Finishing | How does the film play? | Scene/sequence assembly, sound, titles, compositing, versions and delivery |

Within pre-production, screenplay and storyboard iterate together. Blockout is
a composition/movement study reachable from a shot; it does not automatically
replace visual storytelling or become mandatory for every shot. Existing
capabilities should remain accessible while the new path is tested.

# First layout hypothesis: screenplay beside storyboard

```text
Demo 01 / The Ascent / Wake / P2       Assistant: off | Jobs | History
Screenplay & Storyboard     Production     Editing & Finishing

Scenes       Screenplay                  Storyboard
Wake         Selected action             P1    [P2 selected]    P3
Discover     and surrounding text        Visual / missing visual
Leave                                    Intent, duration, join
...                                      Reference | Composition study

             Review: visual storyboard incomplete
             Next task: develop and review Wake's proposed shots
```

This is a layout hypothesis, not a screenshot or working interface. On a small
screen, switch between screenplay and board while retaining the selected
scene/shot; do not squeeze every panel into simultaneous columns. An optional
inspector or assistant replaces secondary space when opened.

## Decisions supported by the layout

- Selecting an action reveals the shots intended to cover it; selecting a shot
  reveals its screenplay context. Uncovered or broken links stay visible.
- A board card communicates action, framing intent, duration and its join to
  the next shot. Its image is optional while drafting and explicitly missing
  until supplied; text coverage alone is not labelled a completed visual board.
- A selected visual states its purpose: concept/reference, storyboard sketch,
  computed composition, candidate master or take frame. Quality and visual
  fidelity do not imply approval.
- References, cast variants, locations and style/look decisions are available
  in context. A film-level library remains searchable; these resources need
  not each occupy a permanent top-level destination in the focused view.
- Open a composition study from the shot, compare it with the intended board
  and return to the same shot. Explain what the study cannot represent.
- Review alternatives and reasons without overwriting prior versions. Show
  source/revision evidence when available; do not invent stale relationships.
- Keep an assistant entry visible with a truthful state (available, off,
  starting or failed). The conversation opens on demand; proposals and human
  gates retain their existing authority boundaries.

# What the home screen should say for Demo 01

Use observable facts, not a fabricated completion percentage:

- Screenplay: seven authored scenes.
- Shot planning: 24 proposed shots with screenplay coverage.
- Visual storyboard: incomplete; do not infer completion from 13 references.
- References: original concept board and identity/age trials, none implicitly
  assigned as approved shot boards or a master face.
- Composition study: six clay frames and a 12-second preview for Wake only.
- Human review: zero of seven storyboards approved; master-face choice open.
- Suggested next task: open Wake's screenplay and proposed shots to develop
  and review visual intent. Explain the basis of this suggestion.

The director may choose another task. A compact activity summary should keep
background work visible without taking over the creative workspace.

# Current implementation versus required investigation

| Need | Existing evidence | What remains |
| --- | --- | --- |
| Screenplay editing and source protection | CodeMirror, revision-checked save in `ScriptApp.tsx` | Integrated shot/board navigation and preservation of editing context |
| Shot coverage and ordered cards | `writing_room`, screenplay links, Storyboard room | Visual drafting and review path before takes exist |
| Board imagery with purpose and versions | References, shot stills, clay boards and master versions exist separately | Inventory authoritative relations and select a supported association/version strategy; do not silently copy files to fake integration |
| Spatial composition study | Geometry, frames, USD boards and animatic | Contextual entry/return, fidelity labels and visible pose/elevation limits |
| Assistant | Existing optional host, drawer and canvas component | Visible off/failure state and verified context in the proposed workspace |
| Approval and history | Existing human storyboard gate and decisions | Place review beside its evidence; distinguish missing visuals, no approval and changed-since-approval |
| Production and finishing | Existing workflows, comparisons, assemblies and versions | Preserve access; test cross-workspace identity before redesigning these surfaces |

Some gaps are navigation/presentation; some may need application commands or
production records. A visual mock-up cannot settle that distinction. No new
storyboard schema, visual-baseline approval or automatic gate is selected here.

# To do

1. Walk CT-0103 V1--V7 against the current UI and record the baseline, including
   any actions that currently require shell commands or file editing.
2. Inventory how a shot can acquire, associate, revise and compare a visual
   candidate through existing commands. Identify missing write boundaries.
3. First read-only React prototype delivered and exercised with Demo 01. The
   write-path inventory and visual-candidate authoring remain next; no save,
   candidate association or approval was simulated.
4. Test Wake end to end: screenplay -> proposed visual shots -> compare a
   composition study -> revise -> review. Test a second scene without geometry
   to ensure blockout is not an accidental prerequisite.
5. Test a screenplay edit and candidate revision: verify context, conflicts,
   previous versions and truthful change indicators. Use a disposable copy for
   mutating usability trials rather than silently changing the director's film.
6. Review findings with the director, then scope implementation records and any
   necessary specifications. Broaden to Production/Finishing after the first
   path works.

# Decisions

- Reuse the three-workspace hypothesis; its usability remains unproven. This
  record adds production evidence and a concrete first slice, not a wholesale
  redesign or a fourth workspace.
- The first implementation is a read-only navigation/inspection pilot.
  Runtime, provider, persistence and production files remain unchanged.
- Keep film/scene/shot identity and a return path across views. Files remain
  authoritative; every implemented mutation must use shared application
  commands and preserve authored/runtime boundaries.
- Assistant availability is independent of the ability to write, inspect and
  review manually. Human creative choices remain human decisions.

# Validation

Source inspection: `web_assets/index.html`, `frontend/src/ScriptApp.tsx`,
`frontend/src/navigation.ts`, and the implementation evidence in CT-0103.
Existing research is treated as hypotheses, not validated UX. The initial
proposal had no prototype; the first implementation has now been exercised in
a browser against the actual running Demo 01.

- `npm test`: all three frontend test files passed, including deep links,
  invalid/empty selection recovery and literal media URL encoding.
- `npm run build`: TypeScript and both Vite builds passed. Existing large
  assistant chunks and the runtime build's deprecated option produce warnings.
- `scripts/check_preproduction.py http://127.0.0.1:8765`: passed navigation,
  selected passage/shot, composition view, reload/back, a second scene without
  geometry, assistant-off feedback and 390-pixel viewport overflow checks.
  Initial screenshots inspected at 1440 and 390 pixels; outputs are disposable
  at `/tmp/cine-toaster-preproduction-review` and reproducible by the script.
- The strengthened walkthrough passed on the server at port 8787 launched with
  `--assistant`: the actual chat composer rendered and received selected
  scene/shot context, with `Seen.details` as text. No model message was sent.
  Mocked off and upstream failure states also passed. A live-chat screenshot
  was inspected. No production files or image versions were changed by this
  implementation or walkthrough.
- Full Python suite: `.venv/bin/python tests/run.py -j 4`, 1,044 tests passed
  in 608.270 seconds, including heavy tests. The doctor build check was amended
  during this run; its final version and new regression were verified with
  `python -m unittest discover -s tests -p test_doctor.py`: nine tests passed.
- `git diff --check` passed. Review server is running on `127.0.0.1:8787` with
  the assistant enabled; the earlier server on 8765 was left available.

CT-0103 coverage is partial: V1/V2/V3/V7 have a working inspection path, not
complete authoring/review acceptance. V4/V5 remain open for visual candidates;
V6 has live chat rendering/context delivery but no model conversation tested;
V8 retains existing scene tools and human gates. V9 selection refresh is
tested, not application restart with every kind of production record. No human
usability verdict or incident closure is claimed.

Use CT-0103's task matrix as the acceptance record. Record task success,
navigation detours, wrong-shot actions, missing information and external
workarounds. The director must be able to explain the current scene's state,
review its visual intention and reach its composition study without relying
on this development document. A more attractive sidebar alone is insufficient.
