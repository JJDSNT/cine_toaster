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
from .runtime_client import RuntimeClient

Assistant = TypedDict("Assistant", {
    "messages": Annotated[list, add_messages],
    "ag-ui": dict,        # what the page sends: its context, its tools
    "highlight": str,     # shared with the page: the shot the assistant points at
    "proposal": dict,     # an action waiting for the person's yes
    "navigate": dict,     # shared with the page: where to take the director's screen
    "notes": list,        # what it looked up during the current turn
    "turn": str,          # the director's message the notes belong to
})

#: Where it may take the screen. Moving the screen changes nothing in the film,
#: so it needs no confirmation; the director can always go back.
ROOMS = {
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
MAX_READS = 4

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
    "You are the directing assistant inside Cine Toaster, a film production tool. Answer in the "
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
)
SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "highlight": {"type": "string"},
        "action": {"type": "string", "enum": ["none", "read", *ACTIONS]},
        "query": {"type": "string", "enum": list(READS)},
        "scene": {"type": "string"},
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


def build(model: Model, runtime: RuntimeClient, checkpointer=None):
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
                  + f"\n\nThe film:\n{film}\n\nThe scene in view:\n{records}"
                  + f"\n\nWhat you looked up this turn ({left} read(s) left):\n{looked}"
                  + "\n\nConversation:\n" + "\n".join(turns))
        try:
            answer = model.ask(SYSTEM, prompt, SCHEMA)
        except ModelUnavailable as error:
            return {"messages": [AIMessage(content=f"Não consegui falar com o modelo: {error.message}")],
                    "proposal": {}, "notes": [], "turn": turn}
        action = answer.get("action", "none")
        if action == "read" and left > 0:
            args = {key: answer[key] for key in ("scene", "shot", "text") if answer.get(key)}
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
                                  "turn": turn}
        where = answer.get("navigate") or {}
        if where.get("room") in ROOMS:
            # A fresh id, so asking for the same place twice moves the screen twice.
            update["navigate"] = {"room": where["room"], "scene": where.get("scene") or "", "shot": where.get("shot") or "",
                                  "id": uuid.uuid4().hex[:8]}
        return update

    def route(state: Assistant) -> str:
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
            return {"messages": [AIMessage(content="Certo, não fiz nada.")], "proposal": {}}
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
                    "proposal": {}}
        # Say what actually happened, read back from the records, not what was hoped for.
        status = run_status(runtime, proposal) if proposal["action"] not in ("set_cut", "set_cuts") else ""
        return {"messages": [AIMessage(content=f"Feito: {verb.lower()} {target} (revisão {result.get('revision')}). "
                                               + status)],
                "proposal": {}}

    graph = StateGraph(Assistant)
    graph.add_node("assistant", assistant)
    graph.add_node("confirm", confirm)
    graph.add_edge(START, "assistant")
    graph.add_conditional_edges("assistant", route, {"confirm": "confirm", "assistant": "assistant", END: END})
    graph.add_edge("confirm", END)
    return graph.compile(checkpointer=checkpointer)
