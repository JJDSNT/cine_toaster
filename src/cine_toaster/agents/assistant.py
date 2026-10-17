"""The directing assistant: a LangGraph graph behind AG-UI (ADR 0017).

Each turn it is given what the page says the person is looking at (AG-UI
context), an overview of the whole film, and a digest of the scene in view,
all read from the runtime. When a question needs more, it looks things up by
itself -- reads, which change nothing (`reads.py`) -- a few times, then
answers. It may point at a shot on screen (shared state) and *propose* an action.
A proposal is put to the person as an interrupt; only on their yes is it
carried out, as a runtime command with an agent actor. Deciding a gate is not
among the actions: that stays a person's (SPEC-0009).
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import interrupt

from .models import Model, ModelUnavailable
from .reads import READS, overview, read
from .roles import DELEGATIONS, ROLES, scratch_fields, scratch_reset
from ..production_context import WORK_POLICY
from .runtime_client import RuntimeClient

#: The state shared with the page and across roles; each role's own scratch is
#: declared with the role (`roles.py`) and joined here.
SHARED = {
    "messages": Annotated[list, add_messages],
    "ag-ui": dict,        # what the page sends: its context, its tools
    "highlight": str,     # shared with the page: the shot the assistant points at
    "proposal": dict,     # an action waiting for the person's yes
    "navigate": dict,     # shared with the page: where to take the director's screen
    "notes": list,        # what it looked up during the current turn
    "turn": str,          # the director's message the notes belong to
    "project_id": str,    # fixed canonical production identity for this conversation
    "active_role": str,
    "routing_reason": str,
    "agent_status": dict,
    "production_update": dict,
    "completed_turn": str,
    "resume_decision_id": str,
}
Assistant = TypedDict("Assistant", {**SHARED, **scratch_fields()})

#: Where it may take the screen. Moving the screen changes nothing in the film,
#: so it needs no confirmation; the director can always go back.
ROOMS = {
    "creation": "Creation / Inception: concept candidates, exploratory references and explicit screenplay inputs",
    "overview": "the production's front page", "script": "the screenplay room", "storyboard": "the storyboard",
    "dialogue": "the dialogue room", "sequences": "sequences and their versions", "scenes": "the list of scenes",
    "review": "what waits for review", "cut": "the cut room (joins between shots)", "cast": "the cast room",
    "locations": "the sets: plans, cameras, set pieces, plates, and the scenes shot there",
    "transitions": "the transition catalogue", "moves": "the camera-move catalogue", "titles": "the title catalogue", "vfx": "the visual effects catalogue and stock elements", "library": "the media library", "knowledge": "measured knowledge",
    "scene": "one scene's room: shots, workflow and gates, pictures, blocks, versions (needs scene)",
    "compare": "a shot's takes side by side, to choose (needs scene and shot)",
    "canvas": "the production canvas, focused on a scene (scene optional)",
    "editor": "the screenplay editor",
}

#: Reads per turn before it must answer: enough to follow a question, not to wander.
MAX_READS = ROLES["coordinator"].budgets["reads"]

#: What the assistant may propose. Each is a runtime command; none decides a gate.
ACTIONS = {
    "start_workflow": "start a workflow: of a generation block (needs `block`), or of one shot outside any "
                      "block (needs `shot`; its result is a take)",
    "resume_workflow": "move a stopped workflow run on (needs `workflow`)",
    "set_cut": "decide the cut into a shot (needs `scene`, `shot` = the incoming shot, `cut_type`; optional "
               "`reason`, `transition` = a catalog id)",
    "set_cuts": "decide several cuts of one scene together, accepted or refused as a whole (needs `scene` and "
                "`cuts`, each with `shot` = the incoming shot, `cut_type`, optional `reason` and `transition`); "
                "use it when the cuts belong to one idea, like reworking a passage",
}

SYSTEM = (
    "You are the Production Coordinator inside Cine Toaster, a film production tool. Answer in the "
    "director's language, briefly and concretely. You know only what is listed under 'The page', 'The film', "
    "'The scene in view' and 'What you looked up'; never invent shots, takes or results. When a question needs "
    "more, set `action` to `read` with `query` one of: "
    + "; ".join(f"`{name}` ({text}; needs: {needs or 'nothing'})" for name, (text, needs, _) in READS.items())
    + ". Read only what the question needs, then answer; if the records do not say, say so. "
    "You cannot change the film yourself. You may propose one of these actions, which the director "
    "will be asked to confirm: " + "; ".join(f"`{name}`: {text}" for name, text in ACTIONS.items()) + ". "
    "Approving, refusing or choosing a picture or a take is the director's own decision: explain the "
    "candidates if asked, never propose to decide for them. To point at a shot on screen, set "
    "`highlight` to its id (like P3); otherwise leave it empty. You may also take the director's screen "
    "somewhere with `navigate` when they ask to see something or when showing it answers better than "
    "words: `room` one of " + "; ".join(f"`{name}` ({text})" for name, text in ROOMS.items()) + ". "
    "It only moves the screen, so do it without asking; say where you took them."
    " For creative discovery, concept development, reference/mood briefs or readiness assessment, "
    "use action `delegate_inception` to invoke the implemented Inception specialist in this same runtime. "
    "It can append concept/screenplay candidates and readiness assessments, never approve human gates. "
    "For developed art direction, image candidates or pixel review use `delegate_art_direction`. "
    "The Art Direction role uses a separate Visual Prevalidation call and explicit generation quota consent. "
    "For screenplay shot proposals use `delegate_directing`; for an evidence-based canonical continuity "
    "audit use `delegate_continuity`. Directing saves versioned proposals and uses a separate Continuity "
    "reviewer; neither promotes shots or approves storyboards. They reuse the existing continuity ledger. "
    "Do not merely describe its job when the director asks for that work. Other specialised stage "
    "executors are not implemented: say what is missing, never claim dispatch. Do not force existing "
    "screenplays/productions back to Inception or confuse a scene title with the film title.\n" + WORK_POLICY
    + "\nCurrent canonical production work is supplied every turn. Explain or progress relevant authorised work, "
    "but pending/not_dispatched is not a live run. Honour capability blockers; do not claim that a local art "
    "or continuity report completes sequence adherence review or ask the director to approve an unfinished task."
)
SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "highlight": {"type": "string"},
        "action": {"type": "string", "enum": ["none", "read", *DELEGATIONS, *ACTIONS]},
        "query": {"type": "string", "enum": list(READS)},
        "scene": {"type": "string"},
        "sequence": {"type": "string"},
        "shot": {"type": "string"},
        "text": {"type": "string"},
        "block": {"type": "string"},
        "workflow": {"type": "string"},
        "cut_type": {"type": "string", "enum": ["", "hard", "match", "action", "j", "l", "smash", "jump", "continuation"]},
        "reason": {"type": "string"},
        "transition": {"type": "string"},
        "cuts": {"type": "array", "items": {"type": "object", "properties": {
            "shot": {"type": "string"},
            "cut_type": {"type": "string", "enum": ["hard", "match", "action", "j", "l", "smash", "jump", "continuation"]},
            "reason": {"type": "string"}, "transition": {"type": "string"}}, "required": ["shot", "cut_type"]}},
        "navigate": {"type": "object", "properties": {
            "room": {"type": "string", "enum": ["", *ROOMS]}, "scene": {"type": "string"}, "shot": {"type": "string"}}},
    },
    "required": ["reply", "action"],
}


def page_context(state: dict[str, Any]) -> dict[str, str]:
    """What the page says the person sees: AG-UI Context objects or plain dicts."""

    found: dict[str, str] = {}
    for item in (state.get("ag-ui") or {}).get("context") or []:
        read = (lambda key: item.get(key)) if isinstance(item, dict) else (lambda key: getattr(item, key, None))
        found[str(read("description"))] = str(read("value"))
    return found


def scene_digest(scene: dict[str, Any]) -> str:
    """The scene's records, shortly: enough to answer 'what is left?', not the whole payload."""

    phase = scene.get("phase") or {}
    stage = ("in production (storyboard approved"
             + (", but the breakdown changed since" if phase.get("changed_since") else "") + ")"
             if phase.get("phase") == "production" else "fitting the storyboard (not yet approved)")
    lines = [f"Scene {scene['id']}: {scene.get('title', '')} — {len(scene['shots'])} shots, "
             f"{sum(1 for shot in scene['shots'] if shot.get('selected_take'))} with a chosen take; {stage}"
             + (f"; set in the location {scene['location']}" if scene.get("location") else "") + "."]
    for block in scene.get("blocks") or []:
        lines.append(f"Block {block['id']}: shots {', '.join(block['shots'])}; "
                     f"{len(block.get('versions') or [])} generated version(s).")
    latest: dict[str, dict[str, Any]] = {}
    for run in scene.get("runs") or []:
        latest.setdefault(str(run.get("subject", {}).get("block")), run)
    for block_id, run in latest.items():
        steps = ", ".join(f"{step['label']} ({step['state']})" for step in run["steps"])
        lines.append(f"Workflow {run['id']} for block {block_id}: {run['state']}; steps: {steps}.")
    for gate in (scene.get("gates") or {}).values():
        if gate.get("state") == "waiting":
            lines.append(f"Gate {gate['id']} waits for the director: approve the picture of {gate['subject']} "
                         f"among {len(gate.get('candidates') or [])} candidate(s).")
    derived = [shot["id"] for shot in scene["shots"] if shot.get("derive")]
    if derived:
        approved = [shot["id"] for shot in scene["shots"] if shot.get("approved_picture")]
        lines.append(f"Shots whose master picture is declared as an edit of a render (it may not be made yet): "
                     f"{', '.join(derived)}; approved so far: {', '.join(approved) or 'none'}.")
    findings = scene.get("findings") or []
    if findings:
        lines.append(f"{len(findings)} continuity finding(s), e.g. {findings[0].get('code')}.")
    return "\n".join(lines)


STEP_WORDS = {"done": "feito", "skipped": "pulado", "running": "rodando", "waiting": "esperando você",
              "failed": "falhou", "pending": "a fazer"}


def run_status(runtime: RuntimeClient, proposal: dict[str, Any]) -> str:
    """The run's state right after the command, in words, from the records."""

    try:
        scene = runtime.scene(proposal["scene"])
    except Exception:
        return ""
    runs = scene.get("runs") or []  # newest first
    run = next((item for item in runs if item["id"] == proposal.get("workflow")), None) or next(
        (item for item in runs if str(item.get("subject", {}).get("block")) == proposal.get("block")), None)
    if run is None:
        return ""
    current = next((step for step in run["steps"] if step["state"] not in ("done", "skipped")), None)
    if run["state"] == "failed" and current:
        return f"Mas a execução parou: {current['label']} falhou — {current.get('note', '')}"
    if current:
        return f"Agora: {current['label']} ({STEP_WORDS.get(current['state'], current['state'])})."
    return f"A execução está {run['state']}."


def build(model: Model, runtime: RuntimeClient, checkpointer=None, models=None):
    """`models(role)` gives the model that serves a role (`catalog.role_models`); by default `model` serves all."""

    from .inception import nodes as inception_nodes
    from .art import nodes as art_nodes
    from .directing import nodes as directing_nodes

    pick = models or (lambda role: model)
    model = pick("coordinator")

    def coordinator(state: Assistant) -> dict[str, Any]:
        seen = page_context(state)
        human = next((m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None)
        turn = str(getattr(human, "id", "") or len(state["messages"]))
        if state.get("completed_turn") == turn:
            return {"active_role": "done"}  # replay of a completed turn must not append versions twice
        try:
            production = runtime.production()
        except Exception:
            production = {}  # the existing coordinator reports its read failure
        project_id = production.get("id") or ""
        if state.get("project_id") and project_id and state["project_id"] != project_id:
            return {"active_role": "done", "proposal": {}, "pending_tool": {},
                    "messages": [AIMessage(content="Esta conversa pertence a outro filme. Abra uma nova conversa para este projeto.")],
                    "agent_status": {"role": "coordinator", "state": "blocked", "detail": "Project identity mismatch"}}
        blank = bool(production) and not production.get("scenes") and not production.get("script_files")
        if production and not production.get("scenes") and production.get("script_files"):
            try:
                files = runtime.screenplay().get("files") or []
                # `toast new` creates a title-only Fountain file, not a developed script.
                blank = bool(files) and all((item.get("text") or "").strip() in
                    ("", "Title: " + production.get("title", "")) for item in files)
            except Exception:
                blank = False  # an unreadable imported screenplay is not proof of a blank film
        decision_id = seen.get("Inception decision id", "")
        attempt = seen.get('Direction continuation attempt', '')
        suffix = '-' + attempt if attempt and len(attempt) <= 80 and all(c.isalnum() or c == '-' for c in attempt) else ''
        decision_id = decision_id if decision_id and getattr(human, "id", "") == "decision-" + decision_id + suffix else ""
        role = "inception" if seen.get("Current room") == "creation" or blank or decision_id else "coordinator"
        if decision_id:
            try:
                creative = runtime.creation()
                current = (creative.get("inception_review") or {}).get("current") or {}
                handoff = next((item for item in creative.get('handoffs', []) if item['decision'] == decision_id), None)
                if ((current.get("decision") or {}).get("id") == decision_id
                        and (current.get("proposal") or {}).get("direction_plan")):
                    role = "directing"
                if ((current.get('decision') or {}).get('id') == decision_id and handoff
                        and not handoff['stale'] and handoff['destination'] == 'storyboard'):
                    role = 'art_direction'
            except Exception:
                pass  # the specialist validates the exact canonical decision before acting
        why = "Creation workspace" if seen.get("Current room") == "creation" else "New film without screenplay" if blank else "Production request and whole-film context"
        return {**scratch_reset(), "project_id": project_id or state.get("project_id", ""), "turn": turn,
                "active_role": role, "routing_reason": why, "proposal": {}, "notes": [],
                "planning_scene": seen.get("Current scene id", ""),
                "resume_decision_id": decision_id,
                "agent_status": {"role": role, "state": "working", "detail": why}}

    def assistant(state: Assistant) -> dict[str, Any]:
        seen = page_context(state)
        scene_id = seen.get("Current scene id", "")
        human = next((message for message in reversed(state["messages"]) if isinstance(message, HumanMessage)), None)
        turn = str(getattr(human, "id", "") or len(state["messages"]))
        notes = list(state.get("notes") or []) if state.get("turn") == turn else []
        try:
            film = overview(runtime.production(), runtime.budget())
        except Exception as error:
            film = f"(the runtime could not be read: {getattr(error, 'message', error)})"
        records = "(no scene is in view)"
        if scene_id:
            try:
                records = scene_digest(runtime.scene(scene_id))
            except Exception as error:  # the answer can still use what the page said
                records = f"(the runtime could not be read: {getattr(error, 'message', error)})"
        turns = [f"{'Director' if isinstance(message, HumanMessage) else 'Assistant'}: {message.content}"
                 for message in state["messages"][-10:]]
        looked = "\n\n".join(f"[{note['query']} {note['args']}]\n{note['result']}" for note in notes) or "(nothing yet)"
        left = MAX_READS - len(notes)
        prompt = ("The page:\n" + ("\n".join(f"- {key}: {value}" for key, value in seen.items()) or "- (nothing)")
                  + "\n\nCanonical pending agent work:\n" + read(runtime, 'production_work', {})
                  + f"\n\nThe film:\n{film}\n\nThe scene in view:\n{records}"
                  + f"\n\nWhat you looked up this turn ({left} read(s) left):\n{looked}"
                  + "\n\nConversation:\n" + "\n".join(turns))
        try:
            answer = model.ask(SYSTEM, prompt, SCHEMA)
        except ModelUnavailable as error:
            return {"messages": [AIMessage(content=f"Não consegui falar com o modelo: {error.message}")],
                    "proposal": {}, "notes": [], "turn": turn, "completed_turn": turn,
                    "agent_status": {"role": "coordinator", "state": "blocked"}}
        action = answer.get("action", "none")
        if action in ("delegate_directing", "delegate_continuity"):
            role = action.removeprefix("delegate_")
            return {"active_role": role, "planning_role": role, "planning_scene": answer.get("scene") or scene_id,
                    "proposal": {}, "turn": turn, "agent_status": {"role": role, "state": "working"}}
        if action == "delegate_art_direction":
            return {"active_role": "art_direction", "proposal": {}, "turn": turn,
                    "agent_status": {"role": "art_direction", "state": "working"}}
        if action == "delegate_inception":
            if state.get("returned_to_coordinator"):
                return {"messages": [AIMessage(content="O encaminhamento não avançou: a capacidade solicitada ainda não está integrada.")],
                        "completed_turn": turn, "agent_status": {"role": "coordinator", "state": "blocked"}}
            return {"active_role": "inception", "proposal": {}, "turn": turn,
                    "routing_reason": "Coordinator delegated creative development",
                    "agent_status": {"role": "inception", "state": "working", "detail": "Creative development"}}
        if action == "read" and left > 0:
            args = {key: answer[key] for key in ("sequence", "scene", "shot", "text") if answer.get(key)}
            name = str(answer.get("query", ""))
            return {"notes": notes + [{"query": name, "args": args, "result": read(runtime, name, args)}],
                    "turn": turn, "proposal": {}}
        proposal = {}
        if action in ACTIONS:
            proposal = {"action": action, "scene": answer.get("scene") or scene_id, "block": answer.get("block", ""),
                        "workflow": answer.get("workflow", ""), "shot": answer.get("shot", "")}
            if action == "set_cut":
                proposal.update(shot=answer.get("shot", ""), cut_type=answer.get("cut_type") or "hard",
                                reason=answer.get("reason", ""), transition=answer.get("transition", ""))
            if action == "set_cuts":
                proposal["cuts"] = [{"shot": str(item.get("shot", "")), "cut_type": item.get("cut_type") or "hard",
                                     "reason": item.get("reason", ""), "transition": item.get("transition", "")}
                                    for item in answer.get("cuts") or [] if isinstance(item, dict) and item.get("shot")]
                proposal["reason"] = answer.get("reason", "")
                if not proposal["cuts"]:
                    proposal = {}
        update: dict[str, Any] = {"messages": [AIMessage(content=answer.get("reply", ""))],
                                  "highlight": answer.get("highlight", ""), "proposal": proposal, "notes": notes,
                                  "turn": turn, "completed_turn": "" if proposal else turn,
                                  "agent_status": {"role": "coordinator", "state": "awaiting_confirmation" if proposal else "complete"}}
        where = answer.get("navigate") or {}
        if where.get("room") in ROOMS:
            # A fresh id, so asking for the same place twice moves the screen twice.
            update["navigate"] = {"room": where["room"], "scene": where.get("scene") or "", "shot": where.get("shot") or "",
                                  "id": uuid.uuid4().hex[:8]}
        return update

    def route(state: Assistant) -> str:
        if state.get("active_role") in ("directing", "continuity"):
            return "planning_context"
        if state.get("active_role") == "art_direction":
            return "art_context"
        if state.get("active_role") == "inception":
            return "inception_context"
        if state.get("proposal"):
            return "confirm"
        last = state["messages"][-1] if state["messages"] else None
        # A read leaves the director's message last: look again before answering.
        return "assistant" if isinstance(last, HumanMessage) else END

    def confirm(state: Assistant) -> dict[str, Any]:
        """Put the proposal to the person; act only on their yes, only through a command."""

        proposal = state["proposal"]

        def described(item: dict[str, Any]) -> str:
            return (f"o corte para {item['shot']} para {item['cut_type']}"
                    + (f" com a transição {item['transition']}" if item.get("transition") else "")
                    + (f" ({item['reason']})" if item.get("reason") else ""))

        if proposal["action"] == "set_cuts":
            verb = "Aplicar juntos"
            target = f"{len(proposal['cuts'])} cortes"
            question = (f"Aplicar juntos estes {len(proposal['cuts'])} cortes na cena {proposal['scene']}? "
                        "Ou todos, ou nenhum.\n" + "\n".join(f"- {described(item)}" for item in proposal["cuts"]))
        elif proposal["action"] == "set_cut":
            verb = "Mudar"
            target = described(proposal)
        else:
            verb = "Iniciar" if proposal["action"] == "start_workflow" else "Retomar"
            if proposal["action"] != "start_workflow":
                target = f"a execução {proposal['workflow']}"
            elif proposal.get("block"):
                target = f"o workflow do bloco {proposal['block']}"
            else:
                target = f"o workflow do plano {proposal['shot']}"
        if proposal["action"] != "set_cuts":
            question = f"{verb} {target} na cena {proposal['scene']}?"
        answer = interrupt({"message": question, "proposal": proposal})
        if not (isinstance(answer, dict) and answer.get("approved")):
            return {"messages": [AIMessage(content="Certo, não fiz nada.")], "proposal": {},
                    "completed_turn": state.get("turn"), "agent_status": {"role": "coordinator", "state": "complete"}}
        payload = {"scene_id": proposal["scene"]}
        if proposal["action"] == "set_cuts":
            payload.update(rationale=proposal.get("reason", ""), cuts=[
                {"shot": item["shot"], "cut": {"type": item["cut_type"], "reason": item.get("reason", ""),
                                               "transition": {"id": item["transition"]} if item.get("transition") else None}}
                for item in proposal["cuts"]])
        elif proposal["action"] == "set_cut":
            payload.update(shot_id=proposal["shot"], cut={
                "type": proposal["cut_type"], "reason": proposal.get("reason", ""),
                "transition": {"id": proposal["transition"]} if proposal.get("transition") else None})
        elif proposal["action"] == "start_workflow":
            payload.update({"block": proposal["block"]} if proposal.get("block") else {"shot": proposal["shot"]})
        else:
            payload["workflow_id"] = proposal["workflow"]
        try:
            result = runtime.command(proposal["action"], payload)
        except Exception as error:
            return {"messages": [AIMessage(content=f"O runtime recusou: {getattr(error, 'message', error)}")],
                    "proposal": {}, "completed_turn": state.get("turn"),
                    "agent_status": {"role": "coordinator", "state": "blocked"}}
        # Say what actually happened, read back from the records, not what was hoped for.
        status = run_status(runtime, proposal) if proposal["action"] not in ("set_cut", "set_cuts") else ""
        return {"messages": [AIMessage(content=f"Feito: {verb.lower()} {target} (revisão {result.get('revision')}). "
                                               + status)],
                "proposal": {}, "completed_turn": state.get("turn"),
                "agent_status": {"role": "coordinator", "state": "complete"}}

    graph = StateGraph(Assistant)
    context, inception, tool = inception_nodes(pick("inception"), runtime)
    graph.add_node("coordinator", coordinator)
    graph.add_node("assistant", assistant)
    graph.add_node("inception_context", context)
    graph.add_node("inception", inception)
    graph.add_node("inception_tool", tool)
    art_context, art_reason, art_tool, art_generate, art_wait = art_nodes(
        pick("art_direction"), runtime, reviewer=pick("visual_prevalidation"))
    planning_context, planning_reason, planning_tool = directing_nodes(
        pick("directing"), runtime, auditor=pick("continuity"), reviewer=pick("continuity_review"))
    for name, node in (("planning_context", planning_context), ("directing", planning_reason),
                       ("directing_tool", planning_tool), ("continuity", planning_tool)):
        graph.add_node(name, node)
    for name, node in (("art_context", art_context), ("art_reason", art_reason), ("art_tool", art_tool),
                       ("visual_prevalidation", art_tool),
                       ("art_generate", art_generate), ("art_wait", art_wait)):
        graph.add_node(name, node)
    graph.add_node("confirm", confirm)
    graph.add_edge(START, "coordinator")
    graph.add_conditional_edges("coordinator", lambda s: s["active_role"],
                                {"coordinator": "assistant", "inception": "inception_context", "directing": "planning_context", "art_direction": "art_context", "done": END})
    graph.add_conditional_edges("inception_context", lambda s: "inception" if s.get("inception_context") else END,
                                {"inception": "inception", END: END})
    graph.add_conditional_edges("assistant", route, {"confirm": "confirm", "assistant": "assistant",
                                "inception_context": "inception_context", "art_context": "art_context", "planning_context": "planning_context", END: END})
    graph.add_conditional_edges("inception", lambda s: "inception_tool" if s.get("pending_tool") else
                                "art_context" if s.get("active_role") == "art_direction" else
                                "planning_context" if s.get("active_role") in ("directing", "continuity") else
                                "assistant" if s.get("active_role") == "coordinator" else END,
                                {"inception_tool": "inception_tool", "art_context": "art_context", "planning_context": "planning_context", "assistant": "assistant", END: END})
    graph.add_conditional_edges("inception_tool", lambda s: END if s.get("completed_turn") == s.get("turn") else "inception",
                                {"inception": "inception", END: END})
    graph.add_edge("confirm", END)
    graph.add_conditional_edges("planning_context", lambda s: END if s.get("completed_turn") == s.get("turn") else "directing")
    graph.add_conditional_edges("directing", lambda s: END if s.get("completed_turn") == s.get("turn") else
                                "art_context" if s.get("active_role") == "art_direction" else
                                "continuity" if s.get("planning_pending", {}).get("action") == "review_continuity" else "directing_tool")
    for name in ("directing_tool", "continuity"):
        graph.add_conditional_edges(name, lambda s: END if s.get("completed_turn") == s.get("turn") else "directing")
    graph.add_conditional_edges("art_context", lambda s: "art_reason" if s.get("art_context") else END)
    graph.add_conditional_edges("art_reason", lambda s: END if s.get("completed_turn") == s.get("turn") else
                                "art_generate" if s.get("art_pending", {}).get("action") == "generate" else
                                "visual_prevalidation" if s.get("art_pending", {}).get("action") == "inspect" else "art_tool")
    for name in ("art_tool", "art_generate", "art_wait", "visual_prevalidation"):
        graph.add_conditional_edges(name, lambda s: END if s.get("completed_turn") == s.get("turn") else
                                    "art_wait" if s.get("art_waiting") else "art_reason")
    # Each role has tighter model/tool budgets; this accommodates cross-role handoffs.
    return graph.compile(checkpointer=checkpointer).with_config({"recursion_limit": 80})
