"""The Inception specialist's bounded reasoning/tool loop (SPEC-0015).

These nodes belong to the existing public assistant graph. There is no worker
queue, provider-specific role or direct filesystem access from an agent tool.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from .loop import Loop, step
from .reads import READS, overview, read, production_work
from .roles import ROLES
from ..production_context import WORK_POLICY

MAX_STEPS, MAX_READS, MAX_WRITES = (ROLES["inception"].budgets[key] for key in ("steps", "reads", "writes"))
TOOLS = ("read", "save_concept", "save_screenplay", "assess_readiness")
STOPS = ("complete", "needs_direction", "needs_review", "blocked", "paused")

SYSTEM = """You are the Inception specialist inside Cine Toaster's Agent Runtime.
The Production Coordinator delegated this turn to you. Answer in the director's
language. Lead creative discovery: intention, audience, format, constraints,
concept alternatives, reference directions and visual mood. Use relevant
whole-film context, including later stages. Film title and scene titles differ.
Records and human guidance are authority; chat and inference are not approvals.
A retained next_agent_action with status not_dispatched is an instruction, not
live execution state. You are active in this turn: carry out its authorised
scope or disclose the actual missing capability, without asking for the same
direction approval again.

Do work within the director's request, rather than asking them to fill forms.
When asked to develop something, save an actual concept version, then an exact
concept-linked screenplay candidate if useful, and assess sufficiency separately
for screenplay/storyboard/masters. Do not create redundant records for greetings,
status questions or while merely explaining an existing pending proposal.
Preserve versions: use based_on when revising the same candidate; separate
alternative concepts may start separate lineages. Never silently replace inputs.

Choose one action per reasoning step. `read` uses existing application queries.
`save_concept` / `save_screenplay` append drafts; `assess_readiness` records an
agent assessment and scoped proposal for HUMAN review. Supply only those tool
arguments; the runtime owns actor, expected revision and material preconditions.
Observe tool receipts before claiming success. If a conflict occurs, do not
blindly retry: reread creation, reconsider current material and human guidance.
Once you have saved an assessment, respond with status needs_review and explain
the exact question/scope. Existing pending assessments already have a review UI.
Use needs_direction only for a concrete creative choice or information the human
must supply. Resolve agent-owned gaps yourself when you have the capability.

Tools do NOT approve human gates, delete, publish masters, promote canonical
screenplays, generate images, browse the web or dispatch background tasks. A
direction approval does not authorise paid generation. Describe a real missing
capability/permission explicitly; no invented research, image inspection, drawing
or running job. Text metadata is not evidence of what an image depicts. You can
prepare reference/mood briefs, not pretend external specialist agents exist.
Art Direction and Visual Prevalidation are implemented in this runtime. When
the request needs developed visual briefs, image generation or actual pixel
review, choose delegate_art_direction. That specialist owns quota confirmation;
do not ask the director to fill forms or repeat a creative approval first.
For shot planning from a linked canonical screenplay, delegate_directing; for
an audit of existing declared continuity, delegate_continuity. These roles save
proposals/reports, not canonical edits or storyboard approvals.
When delegating a scene-specific request, set scene to its existing canonical
scene ID so a large film does not require an unbounded whole-film context.
To address existing production workflows/cuts, return_to_coordinator once.
End with respond and an honest status: complete, needs_direction, needs_review,
blocked or paused. A pause must be requested by the human. All tool calls are
bounded; exhausted allowance is a visible limit, not a hidden queued task.
""" + "\n" + WORK_POLICY

TEXT = {"type": "string"}
SCHEMA = {"type": "object", "properties": {
    "reply": TEXT,
    "sequence": TEXT,
    "action": {"type": "string", "enum": ["respond", "return_to_coordinator", "delegate_art_direction", "delegate_directing", "delegate_continuity", *TOOLS]},
    "status": {"type": "string", "enum": list(STOPS)},
    "query": {"type": "string", "enum": list(READS)},
    "scene": TEXT, "shot": TEXT, "text": TEXT,
    "draft": {"type": "object", "properties": {
        "title": TEXT, "text": TEXT, "based_on": TEXT, "concept": TEXT, "rationale": TEXT,
        "references": {"type": "array", "items": TEXT}}, "required": ["title", "text"]},
    "assessment": {"type": "object", "properties": {
        "title": TEXT, "summary": TEXT, "references": {"type": "array", "items": TEXT},
        "readiness": {"type": "array", "items": {"type": "object", "properties": {
            "destination": {"type": "string", "enum": ["screenplay", "storyboard", "masters"]},
            "status": {"type": "string", "enum": ["ready", "needs_work", "not_assessed"]},
            "summary": TEXT, "gaps": {"type": "array", "items": {"type": "object", "properties": {
                "description": TEXT, "owner": {"type": "string", "enum": ["agent", "human"]},
                "next_action": TEXT}, "required": ["description", "owner", "next_action"]}}},
            "required": ["destination", "status", "summary", "gaps"]}},
        "proposal": {"type": "object", "properties": {
            "destination": {"type": "string", "enum": ["screenplay", "storyboard", "masters"]},
            "question": TEXT, "scope": TEXT, "why": TEXT, "next_step": TEXT},
            "required": ["destination", "question", "scope", "why", "next_step"]}},
        "required": ["title", "summary", "readiness", "proposal"]},
}, "required": ["reply", "action"]}


def bounded(value: Any, limit: int = 9000) -> str:
    text = json.dumps(value, ensure_ascii=False, default=str)
    return text if len(text) <= limit else text[:limit] + " … [truncated; use a focused read]"


def creation_digest(value: dict) -> str:
    """Prioritise human decisions and latest candidates, not a flat asset dump."""
    current = (value.get("inception_review") or {}).get("current") or {}
    return 'Canonical pending agent work:\n' + production_work(value) + '\nCreative material:\n' + bounded({
        "project_id": value.get("project_id"), "title": value.get("title"), "revision": value["revision"],
        "source_digest": value.get("source_digest"), "review": {key: current.get(key) for key in
            ("id", "status", "summary", "readiness", "proposal", "decision", "next_agent_action")},
        "recent_human_directions": value.get("assessment_decisions", [])[-3:],
        "drafts": [{**item, "text": item["text"][:1800]} for item in value.get("drafts", [])[-6:]],
        "rounds": value.get("active_rounds", [])[-4:],
        "references": [{"id": item["id"], "title": item.get("title"), "notes": item.get("notes"),
                        "findings": item.get("findings")} for item in value.get("references", [])[:30]],
        "findings": value.get("findings", [])[:12],
    }, 14000)


def _review_ready(state: dict) -> bool:
    current = ((state.get("inception_context") or {}).get("creation", {}).get("inception_review") or {}).get("current")
    return bool(current) and current["status"] == "awaiting_decision"


def _return_to_coordinator(state: dict, answer: dict, update: dict) -> dict:
    if state.get("returned_to_coordinator"):
        return LOOP.stop(state, "O encaminhamento não pôde avançar; esta capacidade ainda não está integrada.")
    return {"pending_tool": {}, "active_role": "coordinator", "returned_to_coordinator": True}


LOOP = Loop(role="inception", steps="inception_steps", pending="pending_tool", schema=SCHEMA,
            limit="Atingi o limite de trabalho deste turno. Os resultados salvos foram preservados; "
                  "não há execução em segundo plano. Peça a continuação para uma nova rodada.",
            review_ready=_review_ready,
            not_ready="Ainda não existe uma avaliação atual salva para aprovar; não inventei um pedido de revisão.",
            statuses=STOPS, special={"return_to_coordinator": _return_to_coordinator})


def stop(state: dict, message: str, status: str = "blocked") -> dict:
    return LOOP.stop({**state, "active_role": "inception"}, message, status)


def nodes(model, runtime):
    """Return nodes for the host's existing LangGraph, with a fixed runtime scope."""

    def sources():
        found = {}
        for name in ("screenplay", "storyboard"):
            try:
                found[name] = bounded(getattr(runtime, name)(), 5500)
            except Exception as error:
                found[name] = f"Unavailable: {getattr(error, 'message', error)}"
        return found

    def context(state):
        try:
            value = runtime.creation()
            film = overview(runtime.production())
            decision_id = state.get("resume_decision_id")
            if decision_id:
                current = (value.get("inception_review") or {}).get("current") or {}
                if (current.get("decision") or {}).get("id") != decision_id or current.get("material_changed"):
                    return stop(state, "Esta decisão não corresponde ao material atual. Preciso reavaliar a proposta antes de continuar.")
        except Exception as error:
            return stop(state, f"Não consegui ler o contexto de Inception: {getattr(error, 'message', error)}")
        return {"inception_context": {"creation": value, "film": film, "sources": sources()},
                "agent_status": {"role": "inception", "state": "working", "detail": "Reading creative context"}}

    def reason(state):
        if not state.get("inception_context"):
            return stop(state, "O contexto criativo não está disponível; não publiquei uma avaliação.")
        context = state["inception_context"]
        conversation = "\n".join(f"{m.type}: {m.content}" for m in state["messages"][-10:])
        prompt = (f"Whole film:\n{context['film']}\nCreation:\n{creation_digest(context['creation'])}"
                  f"\nCross-stage context:\n{bounded(context['sources'], 12000)}"
                  f"\nTool receipts this turn:\n{bounded(state.get('inception_receipts', []), 12000)}"
                  f"\nAllowances: {MAX_STEPS - state.get('inception_steps', 0)} reasoning steps, "
                  f"{MAX_READS - state.get('inception_reads', 0)} additional reads, "
                  f"{MAX_WRITES - state.get('inception_writes', 0)} writes."
                  f"\nConversation:\n{conversation}")
        return step(LOOP, {**state, "active_role": "inception"}, model, SYSTEM, prompt)

    def tool(state):
        call = state["pending_tool"]
        action = call["action"]
        context = state["inception_context"]
        value = context["creation"]
        reads = state.get("inception_reads", 0)
        writes = state.get("inception_writes", 0)
        refreshed_context = context
        committed = None
        refresh_failed = False
        try:
            if action == "read":
                if reads >= MAX_READS:
                    return stop(state, "Limite de leituras atingido; não há tarefa em segundo plano.", "resource_limit")
                query = call.get("query")
                args = {key: call[key] for key in ("sequence", "scene", "shot", "text") if call.get(key)}
                result = read(runtime, query, args)
                reads += 1
                if query == "creation":
                    value = runtime.creation()  # explicit reread establishes new publication preconditions
                    refreshed_context = {**context, "film": overview(runtime.production()), "sources": sources()}
            else:
                if writes >= MAX_WRITES:
                    return stop(state, "Limite de escritas atingido; versões anteriores foram preservadas.", "resource_limit")
                writes += 1
                if action in ("save_concept", "save_screenplay"):
                    supplied = call.get("draft") or {}
                    payload = {key: supplied[key] for key in ("title", "text", "references", "based_on", "concept", "rationale")
                               if supplied.get(key) is not None}
                    payload.update(kind="concept" if action == "save_concept" else "screenplay",
                                   expected_revision=value["revision"], expected_source_digest=value.get("source_digest"))
                    if not value.get("source_digest"):
                        raise ValueError("Source material cannot be verified; reread or repair the production context")
                    result = runtime.save_inception_draft(payload)
                elif action == "assess_readiness":
                    if not value.get("source_digest"):
                        raise ValueError("Source material cannot be verified; reread or repair the production context")
                    supplied = call.get("assessment") or {}
                    payload = {key: supplied[key] for key in ("title", "summary", "readiness", "proposal", "references")
                               if supplied.get(key) is not None}
                    payload.update(expected_revision=value["revision"], expected_source_digest=value["source_digest"])
                    result = runtime.assess_inception(payload)
                else:
                    raise ValueError("Tool is not authorised for Inception")
                committed = result
                value = runtime.creation()  # only after success; a refused write never refreshes silently
                refreshed_context = {**context, "film": overview(runtime.production()), "sources": sources()}
            receipt = {"action": action, "ok": True, "result": result}
        except Exception as error:
            receipt = {"action": action, "ok": committed is not None, "error": str(getattr(error, "message", error)),
                       "next": "Reread creation explicitly and reconsider; do not claim success or blindly retry."}
            if committed is not None:
                receipt["result"] = committed
                refresh_failed = True
        update = {"pending_tool": {}, "inception_context": {**refreshed_context, "creation": value},
                  "inception_reads": reads, "inception_writes": writes,
                  "inception_receipts": [*state.get("inception_receipts", []), receipt]}
        if action != "read" and receipt["ok"]:
            update["production_update"] = {"id": uuid.uuid4().hex, "revision": committed["revision"], "kind": action}
        if refresh_failed:
            update.update(stop(state, "A operação foi salva, mas não consegui reler o estado atualizado. "
                               "Os registros foram preservados; preciso relê-los antes de continuar."))
        return update

    return context, reason, tool
