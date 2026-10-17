# ADR 0028: Inception assesses readiness for a destination, not completion of a form

Status: accepted for CT-0107's director-authorised first slice.

Extend the existing production-owned Creation journal with retained
`assessments` and `assessment_decisions` lists. Existing schema-1 journals read
missing lists as empty. Shared operations append an agent-authored assessment
or a human direction decision under the existing root lock, expected revision
and atomic replacement; no new database or workflow engine is introduced.

An assessment names destination-specific judgments, evidence, gaps with owners
and next actions, and one concrete recommendation/question. It pins the
screenplay, references, retained storyboard drawings and creative context used.
Judgments are authored analysis, not an automatic score derived from image count.
Changed material invalidates an outstanding approval; earlier judgments and
decisions remain readable. Requesting changes requires human guidance.

The GUI presents the assessment and two decision actions, not an authoring form
for the agent. Only human actors decide. MCP agents may author assessments but
cannot approve. CLI/HTTP/MCP/GUI use the same application operations.

Approval adopts the named direction; it does not approve the whole storyboard,
select cast masters, promote a screenplay, authorise paid generation or claim
that background execution started. Show the recorded next agent action and its
actual dispatch status. Full autonomous execution/continuation remains a
separate part of CT-0107; do not invent a running worker to hide that boundary.
The director explicitly requires reusing/extending the existing LangGraph
Agent Runtime/CoAgents and built-in production workflows (ADR 0017), not a
parallel executor, queue, scheduler or orchestration engine.
