---
id: CT-0068
title: Human-centered information visibility and cognitive ergonomics research
type: work
status: proposed
owner: unassigned
created_at: 2026-10-08
updated_at: 2026-10-08
tags:
  - ux
  - research
  - cognitive-ergonomics
  - information-architecture
  - accessibility
---

# Research question

**What must a human filmmaker be able to perceive at a glance to understand the state of a production and decide what to do next, without cognitive overload?**

This is a **theoretical and empirical investigation**, not a mandate to put all project information on one screen. It follows the first three-workspace wireframe (CT-0067), whose usability and visual comfort are unvalidated.

## Theoretical foundations to examine

- **Situation awareness** (Endsley): perception of relevant elements, comprehension of their meaning, and projection of what happens next. Test its applicability to filmmaking workflows rather than treating it as a universal UI prescription.
- **Cognitive load theory** (Sweller): distinguish task complexity from avoidable interface overhead; evaluate working-memory demands during creative tasks.
- **Recognition rather than recall; visibility of system status; user control and freedom** (Nielsen heuristics): users should not need to remember hidden state or reconstruct what an agent did.
- **Progressive disclosure and information scent**: prioritize essential controls and provide discoverable paths to advanced functions.
- **Gestalt grouping and visual hierarchy**: proximity, similarity, alignment, hierarchy, contrast and whitespace should communicate relationships, not merely decorate.
- **Direct manipulation and external cognition**: spatial layouts, timelines and previews should help users reason about changes.
- **Signal detection and alert fatigue**: distinguish actionable exceptions from ordinary activity; avoid constant warnings.
- **ISO 9241-110 / 9241-210 and WCAG 2.2**: dialogue principles, human-centered design, accessibility, keyboard access, focus and contrast.

Starting references to verify and annotate:
- https://www.nngroup.com/articles/ten-usability-heuristics/
- https://www.nngroup.com/articles/progressive-disclosure/
- https://www.w3.org/TR/WCAG22/
- https://www.iso.org/standard/77520.html (verify applicability and current edition before citing as normative)
- Original scholarly work on situation awareness and cognitive load should be retrieved and distinguished from secondary summaries.

## Ask the user-facing questions first

For **Screenplay & Storyboard**:
- Where am I in the story, what is planned, what is missing and what contradicts the intention?
- Which shot has a 2D/3D reference and which is not yet approved?

For **Production**:
- What is generating, waiting, failed, ready for review or approved?
- Which take is selected, why, what did it cost, and what depends on it?
- What action can I take now without opening the full execution graph?

For **Editing & Post-production**:
- What am I watching, where is it in the film, and what source/take/version produced it?
- What has changed since the last approved cut, and which decisions or renders became stale?
- What remains before a reviewable or deliverable version can be exported?

Across all three:
- What requires my attention **now**, what can wait, and what is merely background activity?
- What is known, inferred, pending, approved or failed?
- What is the consequence of an action, and how can I undo it?

## Research method and deliverables

1. **Evidence review**: collect primary research and practical HCI guidance; distinguish evidence, interpretation and design hypothesis.
2. **Information inventory**: list all current Core states and commands that could appear in the UI, with source, update frequency and consequence.
3. **Task-based priority matrix**: for each workspace and user task, classify information as *always visible*, *contextual*, *on demand*, *notification/exception* or *hidden from normal workflow*. Record rationale and risks.
4. **Attention model**: define priority and interruption rules for jobs, failures, approval gates, agent proposals, continuity findings and costs.
5. **Low-density wireframe variants**: compare focused, balanced and expert layouts for laptop and large-monitor use, not only a single all-panels-open arrangement.
6. **Usability evaluation**: first-glance comprehension, locate-the-problem, return-to-context, approval safety, navigation time, error recovery, accessibility and subjective workload. Include realistic long-session scenarios.
7. **Decision record**: update CT-0067/CT-0066 with evidence, accepted patterns, rejected patterns and unresolved questions; create implementation tasks only after review.

## Acceptance criteria for the research

- A traceable map from **user question → information needed → UI location → Core source**.
- Explicit rules for what is persistent, contextual, progressive or interruptive.
- At least two contrasting density/layout alternatives evaluated against representative tasks.
- Clear handling of novice versus expert workflows without separate film state.
- Accessibility and attention-management risks documented.
- No assertion that a proposed layout is 'humanly pleasant' without user testing.

## Immediate next action

Begin with the **Production** workspace as the most challenging case: inventory its jobs, takes, approvals, canvas, workflows, costs and agent messages; classify what a director must know immediately versus what belongs behind a deliberate action. Use the same method on the other two workspaces afterward.

## Related

- [CT-0067](CT-0067-three-workspace-wireframe-study.md): initial wireframe and unresolved comfort/density questions.
- [CT-0066](CT-0066-three-workspace-ux-vision.md): workspace and journey design.
