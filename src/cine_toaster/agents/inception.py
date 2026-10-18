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
TOOLS = ("read", "save_concept", "save_screenplay", "assess_readiness", "ask_questions", "record_answer", "withdraw_question")
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

Interview before advancing (SPEC-0020). The creation record carries the format's
intake sheet: each item, why it matters and the stage it unlocks, with what was
asked and answered. Compare it with everything the records already establish.
For what only the person can tell you, the records do not say, and the work
asked for cannot proceed without, use `ask_questions`: at most three at a
time, the most blocking first, each in the director's language with its
reason, then respond needs_direction. A concrete request the records already
support is done first; an optional or merely useful question never replaces
it. Never ask what the records answer, never answer for the person, never
repeat an open question. For a new film with no scenes, the format comes
first. An answered item is the person's word: use it, and cite it when it
shapes a candidate. When the person answers in conversation -- an open
question, or a sheet item they bring up themselves -- write it down with
`record_answer`: the question id, the answer in their words, and `quote`, the
exact words from their message. It is refused unless the quote is in what they
wrote here. Record only what they said, never your inference. An open question of yours
that the work no longer needs (the records answered it, or it should not have
been asked) is withdrawn with `withdraw_question` and the reason.

A storyboard proposal is for the director's unit of review, a canonical
sequence: set proposal.sequence to its id (from the work structure) so the
approval hands the whole sequence -- every scene and shot, in order -- to Art
Direction. A scene-only study is a partial study, never the storyboard request.

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
    "answer": {"type": "object", "properties": {"question": TEXT, "answer": TEXT, "quote": TEXT},
               "required": ["question", "answer", "quote"]},
    "withdrawal": {"type": "object", "properties": {"question": TEXT, "reason": TEXT},
                   "required": ["question", "reason"]},
    "questions": {"type": "array", "items": {"type": "object", "properties": {
        "item": TEXT, "question": TEXT, "why": TEXT, "based_on": TEXT}, "required": ["item", "question", "why"]}},
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
            "question": TEXT, "scope": TEXT, "why": TEXT, "next_step": TEXT, "sequence": TEXT},
            "required": ["destination", "question", "scope", "why", "next_step"]}},
        "required": ["title", "summary", "readiness", "proposal"]},
}, "required": ["reply", "action"]}


#: How far `bounded` shrinks, in order: the longest text kept, and the most items of a list.
_SHRINK = ((2000, 40), (800, 20), (300, 10), (120, 6), (40, 3))


def _shrink(value: Any, chars: int, items: int) -> Any:
    if isinstance(value, str):
        return value if len(value) <= chars else value[:chars] + f" … [{len(value) - chars} characters cut]"
    if isinstance(value, dict):
        return {key: _shrink(item, chars, items) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        if len(value) > items:
            # The first and the latest entries: an index starts a list, the newest work ends it.
            head, tail = items // 2, items - items // 2
            value = [*value[:head], f"… [{len(value) - items} items cut; use a focused read]", *value[-tail:]]
        return [_shrink(item, chars, items) for item in value]
    return value


def bounded(value: Any, limit: int = 9000) -> str:
    """The value as JSON within `limit` characters, cut by structure and saying where -- always valid JSON.

    Long texts keep their start, long lists their first and latest entries, each
    with a marker of what was left out, so the model can ask for a focused read
    instead of reading a string severed in the middle.
    """

    text = json.dumps(value, ensure_ascii=False, default=str)
    for chars, items in _SHRINK:
        if len(text) <= limit:
            return text
        text = json.dumps(_shrink(value, chars, items), ensure_ascii=False, default=str)
    if len(text) <= limit:
        return text
    # Still too large: share the limit among the keys, in proportion to their size, rather than
    # give nothing (an empty answer made Art Direction reread the same context until its budget ran out).
    shrunk = _shrink(value, _SHRINK[-1][0], _SHRINK[-1][1])
    for share in (1.0, 0.8, 0.6, 0.4, 0.25):
        text = json.dumps(_fit(shrunk, int(limit * share)), ensure_ascii=False, default=str)
        if len(text) <= limit:
            return text
    return json.dumps({"cut": f"too large to give here ({len(json.dumps(value, default=str))} characters)"})


def _size(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, default=str))


def _fit(value: Any, budget: int) -> Any:
    """Shrink `value` towards `budget` characters of JSON by dividing it among its parts."""

    if _size(value) <= budget:
        return value
    if isinstance(value, str):
        keep = max(budget - 40, 0)
        return value[:keep] + f" … [{len(value) - keep} characters cut]"
    if isinstance(value, dict):
        sizes = {key: _size(item) for key, item in value.items()}
        total = sum(sizes.values()) or 1
        room = max(budget - 8 * len(value), 0)
        # Small parts (ids, states, the instruction) stay whole; large ones share what is left.
        small = {key for key, size in sizes.items() if size <= room / max(len(value), 1)}
        left = room - sum(sizes[key] for key in small)
        large = total - sum(sizes[key] for key in small) or 1
        fitted = {key: item if key in small else _fit(item, max(int(left * sizes[key] / large), 24))
                  for key, item in value.items()}
        # Many small keys can outweigh the budget on their own: leave out the largest, and say which.
        omitted = []
        while _size(fitted) > budget and len(fitted) > 1:
            largest = max((key for key in fitted if key != "_omitted"), key=lambda key: _size(fitted[key]))
            omitted.append(largest)
            fitted = {key: item for key, item in fitted.items() if key != largest}
            fitted["_omitted"] = omitted
        return fitted
    if isinstance(value, list):
        if not value:
            return value
        each = max(budget // len(value), 24)
        return [_fit(item, each) for item in value]
    return value


def creation_digest(value: dict) -> str:
    """Prioritise human decisions and latest candidates, not a flat asset dump."""
    current = (value.get("inception_review") or {}).get("current") or {}
    return 'Canonical pending agent work:\n' + production_work(value) + '\nCreative material:\n' + bounded({
        "project_id": value.get("project_id"), "title": value.get("title"), "revision": value["revision"],
        "source_digest": value.get("source_digest"), "review": {key: current.get(key) for key in
            ("id", "status", "summary", "readiness", "proposal", "decision", "next_agent_action")},
        "recent_human_directions": value.get("assessment_decisions", [])[-3:],
        "drafts": [{**item, "text": _shrink(item["text"], 1800, 0)} for item in value.get("drafts", [])[-6:]],
        "rounds": value.get("active_rounds", [])[-4:],
        # Every reference by id and title: the newest are the ones the work just made (Demo 01: a
        # first-30 cut hid the batch's last drawings from Art Direction).
        "references": [{"id": item["id"], "title": item.get("title"), "notes": item.get("notes"),
                        "findings": item.get("findings")} for item in value.get("references", [])],
        "findings": value.get("findings", [])[:12],
        "intake": _intake_digest(value.get("intake")),
    }, 14000)


def _intake_digest(intake: dict | None) -> dict:
    """The format's sheet against what was asked and answered, shortly."""
    if not intake:
        return {"unavailable": True}
    return {"format": intake.get("format"), "production_says": intake.get("production_says", ""),
            "open_count": intake.get("open_count", 0),
            "missing_required": intake.get("missing_required", []),
            "items": [{"id": row["id"], "ask": row["ask"], "why": row["why"], "unlocks": row["unlocks"],
                       "status": row["status"], "question_id": (row.get("question") or {}).get("id"),
                       "answer": (row.get("answer") or {}).get("answer"),
                       "answer_id": (row.get("answer") or {}).get("id")} for row in intake.get("items", [])]}


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
                elif action == "record_answer":
                    supplied = call.get("answer") or {}
                    quote = str(supplied.get("quote") or "").strip()
                    spoken = [str(m.content) for m in state["messages"] if getattr(m, "type", "") == "human"]
                    # The person's words, or nothing: the runtime never takes the agent's paraphrase as theirs.
                    if not quote or not any(quote in text for text in spoken):
                        raise ValueError("The quote is not in the person's messages in this conversation; "
                                         "record only what they wrote")
                    result = runtime.record_intake_answer({"question": supplied.get("question"),
                                                           "answer": supplied.get("answer"), "quote": quote,
                                                           "expected_revision": value["revision"]})
                elif action == "withdraw_question":
                    supplied = call.get("withdrawal") or {}
                    result = runtime.withdraw_intake({"question": supplied.get("question"),
                                                      "reason": supplied.get("reason"),
                                                      "expected_revision": value["revision"]})
                elif action == "ask_questions":
                    result = runtime.ask_intake({"questions": call.get("questions") or [],
                                                 "expected_revision": value["revision"]})
                elif action == "assess_readiness":
                    if not value.get("source_digest"):
                        raise ValueError("Source material cannot be verified; reread or repair the production context")
                    supplied = call.get("assessment") or {}
                    payload = {key: supplied[key] for key in ("title", "summary", "readiness", "proposal", "references")
                               if supplied.get(key) is not None}
                    if isinstance(payload.get("proposal"), dict):  # strict-schema adapters send unused fields as null
                        payload["proposal"] = {key: value for key, value in payload["proposal"].items() if value is not None}
                    payload.update(expected_revision=value["revision"], expected_source_digest=value["source_digest"])
                    result = runtime.assess_inception(payload)
                else:
                    raise ValueError("Tool is not authorised for Inception")
                committed = result
                value = runtime.creation()  # only after success; a refused write never refreshes silently
                refreshed_context = {**context, "film": overview(runtime.production()), "sources": sources()}
            receipt = {"action": action, "ok": True, "result": result}
        except Exception as error:
            receipt = {"action": action, "ok": committed is not None, "error": str(getattr(error, "message", "") or error) or type(error).__name__,
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
