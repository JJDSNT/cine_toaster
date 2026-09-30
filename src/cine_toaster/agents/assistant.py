"""The directing assistant: a LangGraph graph behind AG-UI (ADR 0017).

Each turn it is given two things: what the page says the person is looking at
(AG-UI context), and a digest of that scene read from the runtime. It answers,
may point at a shot on screen (shared state), and may *propose* an action.
A proposal is put to the person as an interrupt; only on their yes is it
carried out, as a runtime command with an agent actor. Deciding a gate is not
among the actions: that stays a person's (SPEC-0009).
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import interrupt

from .models import Model, ModelUnavailable
from .runtime_client import RuntimeClient

Assistant = TypedDict("Assistant", {
    "messages": Annotated[list, add_messages],
    "ag-ui": dict,        # what the page sends: its context, its tools
    "highlight": str,     # shared with the page: the shot the assistant points at
    "proposal": dict,     # an action waiting for the person's yes
})

#: What the assistant may propose. Each is a runtime command; none decides a gate.
ACTIONS = {
    "start_workflow": "start the workflow of a generation block (needs `block`)",
    "resume_workflow": "move a stopped workflow run on (needs `workflow`)",
}

SYSTEM = (
    "You are the directing assistant inside Cine Toaster, a film production tool. Answer in the "
    "director's language, briefly and concretely. You know only what is listed under 'The page' and "
    "'The records'; never invent shots, takes or results, and say when something is not in them. "
    "You cannot change the film yourself. You may propose one of these actions, which the director "
    "will be asked to confirm: " + "; ".join(f"`{name}`: {text}" for name, text in ACTIONS.items()) + ". "
    "Approving, refusing or choosing a picture or a take is the director's own decision: explain the "
    "candidates if asked, never propose to decide for them. To point at a shot on screen, set "
    "`highlight` to its id (like P3); otherwise leave it empty."
)
SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "highlight": {"type": "string"},
        "action": {"type": "string", "enum": ["none", *ACTIONS]},
        "block": {"type": "string"},
        "workflow": {"type": "string"},
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

    lines = [f"Scene {scene['id']}: {scene.get('title', '')} — {len(scene['shots'])} shots, "
             f"{sum(1 for shot in scene['shots'] if shot.get('selected_take'))} with a chosen take."]
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
        records = "(no scene is open)"
        if scene_id:
            try:
                records = scene_digest(runtime.scene(scene_id))
            except Exception as error:  # the answer can still use what the page said
                records = f"(the runtime could not be read: {error})"
        turns = [f"{'Director' if isinstance(message, HumanMessage) else 'Assistant'}: {message.content}"
                 for message in state["messages"][-10:]]
        prompt = ("The page:\n" + ("\n".join(f"- {key}: {value}" for key, value in seen.items()) or "- (nothing)")
                  + f"\n\nThe records:\n{records}\n\nConversation:\n" + "\n".join(turns))
        try:
            answer = model.ask(SYSTEM, prompt, SCHEMA)
        except ModelUnavailable as error:
            return {"messages": [AIMessage(content=f"Não consegui falar com o modelo: {error.message}")],
                    "proposal": {}}
        action = answer.get("action", "none")
        proposal = {}
        if action in ACTIONS:
            proposal = {"action": action, "scene": scene_id, "block": answer.get("block", ""),
                        "workflow": answer.get("workflow", "")}
        return {"messages": [AIMessage(content=answer.get("reply", ""))],
                "highlight": answer.get("highlight", ""), "proposal": proposal}

    def confirm(state: Assistant) -> dict[str, Any]:
        """Put the proposal to the person; act only on their yes, only through a command."""

        proposal = state["proposal"]
        target = (f"o workflow do bloco {proposal['block']}" if proposal["action"] == "start_workflow"
                  else f"a execução {proposal['workflow']}")
        verb = "Iniciar" if proposal["action"] == "start_workflow" else "Retomar"
        answer = interrupt({"message": f"{verb} {target} da cena {proposal['scene']}?", "proposal": proposal})
        if not (isinstance(answer, dict) and answer.get("approved")):
            return {"messages": [AIMessage(content="Certo, não fiz nada.")], "proposal": {}}
        payload = {"scene_id": proposal["scene"]}
        payload.update({"block": proposal["block"]} if proposal["action"] == "start_workflow"
                       else {"workflow_id": proposal["workflow"]})
        try:
            result = runtime.command(proposal["action"], payload)
        except Exception as error:
            return {"messages": [AIMessage(content=f"O runtime recusou: {getattr(error, 'message', error)}")],
                    "proposal": {}}
        # Say what actually happened, read back from the records, not what was hoped for.
        return {"messages": [AIMessage(content=f"Feito: {verb.lower()} {target} (revisão {result.get('revision')}). "
                                               + run_status(runtime, proposal))],
                "proposal": {}}

    graph = StateGraph(Assistant)
    graph.add_node("assistant", assistant)
    graph.add_node("confirm", confirm)
    graph.add_edge(START, "assistant")
    graph.add_conditional_edges("assistant", lambda state: "confirm" if state.get("proposal") else END,
                                {"confirm": "confirm", END: END})
    graph.add_edge("confirm", END)
    return graph.compile(checkpointer=checkpointer)
