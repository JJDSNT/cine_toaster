# CT-0071 — Cognitive ergonomics across the three workspaces

Status: research proposal (2026-10-08). Complements CT-0066 through CT-0070. This is not a validated UX design.

## Cognitive needs

| Workspace | Mental task | Primary information | Contextual information |
| --- | --- | --- | --- |
| Screenplay & Storyboard | Narrative intention, coverage, composition | Scene, script, active shot/board | Coverage gaps, linked references, camera/blocking details |
| Production | Operational awareness and comparing alternatives | Current shot, preview, selected take, blocking decisions | Jobs, provenance, provider parameters, cost |
| Editing & Post | Temporal and audiovisual judgment | Program monitor, timeline, playhead, selected clip | VFX/color/audio tools, versions, export checks |
| Cross-workspace | Preserve understanding when switching tasks | Project/scene/shot identity, return path | Script intent, selected take, actual assembly references, history |

## Human factors research lenses

- Situation awareness (Endsley): perceive state, comprehend consequences, anticipate outcomes.
- Ecological interface design (Vicente/Rasmussen): show relationships and constraints, not isolated counters.
- Distributed cognition (Hutchins): screenplay, boards, agents and timeline are external representations supporting shared reasoning.
- Cognitive load (Sweller): minimize avoidable switching and extraneous information.
- Progressive disclosure and recognition over recall (Nielsen): expose essential status and keep advanced detail discoverable.
- Human–AI interaction (Amershi et al.): show agent intent, uncertainty, scope and human approval.
- WCAG 2.2: accessible navigation, contrast, focus and status feedback.

These references guide hypotheses; the original papers were not critically reviewed and no user tests were performed in this iteration.

## Repository evidence checked

- `docs/screenplay-editor.md` and `frontend/src/ScriptApp.tsx`: authoritative Fountain text, outline, scene links, save-impact findings for broken/recovered quotations and uncovered dialogue.
- `docs/storyboard-3d.md`: static composition boards, animatic for checking, and indications when a board predates plan changes; Blender animation does not control generative movement.
- `ai-context/work/CT-0057-producer-status.md`: deterministic statuses, pending choices, blockers and next decisions without creative priority ranking.
- `ai-context/work/CT-0059-continuity-ledger.md`: declared facts distinguished from unconfirmed inference.
- `frontend/src/CutEditor.tsx` and `frontend/src/ReferenceEditor.tsx`: revision-checked commands avoid silently overwriting stale decisions.
- `frontend/src/Assistant.tsx`: contextual agent and approval interrupts.
- `ai-context/work/CT-0061-finops-observation.md`: measured and allocated costs are distinguished.

Not yet verified: actual full timeline UX, persistence of selection across every room, complete downstream impact graph, and whether creative intent needs a new schema field.

## Cross-workspace scenario

1. Writer changes a dramatic beat; show actual screenplay coverage findings, not guessed downstream effects.
2. Director examines the related 2D/3D storyboard; only flag stale boards when a real plan revision warrants it.
3. Production compares reference and generated takes; show which take is selected and why when rationale is recorded.
4. Editor examines which take an actual cut version references; do not assume a new selected take automatically invalidates an assembly.
5. A confirmed mismatch may be explained and offered for human-controlled reconform; never silently rewrite the cut.
6. Navigate back to narrative context while preserving the selected scene/shot and a return path.

## Testable hypotheses

H1: Task-focused default views reduce visual search compared with all-panels-open.
H2: A contextual state + consequence + action explanation improves first-glance comprehension.
H3: Persistent scene/shot context and return links reduce wrong-target actions across spaces.
H4: Playback-first editing views support audiovisual judgment better than permanent diagnostics.
H5: Clearly labeled declared/computed/inferred/unknown evidence reduces false certainty.

## Next actions

- [ ] Audit the actual editing UI and routes, not just the conceptual wireframe.
- [ ] Inventory canonical links between script passage, scene, shot, board, take and cut/assembly version.
- [ ] Determine whether existing author-entered rationale and script context already capture creative intent.
- [ ] Produce information-priority matrices for Screenplay/Storyboard and Editing/Post, matching CT-0069's Production matrix.
- [ ] Prototype focused versus detailed layouts and context-preserving transitions.
- [ ] Evaluate comprehension, time-to-find, errors, interruption recovery, workload and accessibility with representative users.
- [ ] Update CT-0066 through CT-0070 and record accepted decisions only after validation.

No fourth workspace or new source of truth is proposed.
