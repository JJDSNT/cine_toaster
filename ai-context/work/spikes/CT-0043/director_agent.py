"""CoAgent spike: a LangGraph agent served over AG-UI for CopilotKit.

It sees what the director sees (the page's context arrives in state["ag-ui"]),
shares state with the page (which shot to highlight), and asks before acting.
It acts only through Cine Toaster's commands: here, `start_workflow`, recorded
with an agent actor after the person confirmed.

    FILM=<film> uvicorn director_agent:app --port 8123
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Any, TypedDict

from ag_ui_langgraph import LangGraphAgent, add_langgraph_fastapi_endpoint
from fastapi import FastAPI
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import interrupt

import cli_model
from cine_toaster.commands import dispatch

FILM = Path(os.environ.get("FILM", "film")).resolve()

# The workflow the agent starts runs in this process's job runtime; fake RunPod, no money.
import fakes  # noqa: E402
from cine_toaster import workflows  # noqa: E402
from cine_toaster.jobs import JobManager  # noqa: E402

fakes.install()
workflows.attach(JobManager())

Director = TypedDict("Director", {
    "messages": Annotated[list, add_messages],
    "ag-ui": dict,          # what the page tells the agent: its context, its tools
    "highlight": str,       # shared with the page: the shot the agent points at
    "proposal": dict,       # an action waiting for the person's yes
})

SYSTEM = (
    "You are the directing assistant inside Cine Toaster, a film production tool. "
    "Answer in the director's language (Portuguese), briefly. You know only what the page says the "
    "director is looking at, listed below; never invent records. You cannot change the film yourself: "
    "when the director asks to start producing a block, propose the action `start_workflow` with the "
    "block id, and the tool will ask them to confirm. To point at a shot on screen, set `highlight` "
    "to its id, or leave it empty."
)
SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "highlight": {"type": "string"},
        "action": {"type": "string", "enum": ["none", "start_workflow"]},
        "block": {"type": "string"},
    },
    "required": ["reply", "action"],
}


def _context(state: Director) -> list[tuple[str, str]]:
    """What the page says the director sees: AG-UI Context objects, or plain dicts."""

    items = (state.get("ag-ui") or {}).get("context") or []
    read = lambda item, key: getattr(item, key, None) if not isinstance(item, dict) else item.get(key)  # noqa: E731
    return [(str(read(item, "description")), str(read(item, "value"))) for item in items]


def assistant(state: Director) -> dict[str, Any]:
    seen = "\n".join(f"- {description}: {value}" for description, value in _context(state)) or "- (nothing)"
    turns = []
    for message in state["messages"][-8:]:
        who = "Director" if isinstance(message, HumanMessage) else "Assistant"
        turns.append(f"{who}: {message.content}")
    prompt = f"What the director is looking at:\n{seen}\n\nConversation:\n" + "\n".join(turns)
    answer = cli_model.ask(SYSTEM, prompt, SCHEMA)
    proposal = {"action": "start_workflow", "block": answer.get("block", "")} if answer["action"] != "none" else {}
    return {"messages": [AIMessage(content=answer["reply"])], "highlight": answer.get("highlight", ""),
            "proposal": proposal}


def route(state: Director) -> str:
    return "confirm" if state.get("proposal") else END


def confirm(state: Director) -> dict[str, Any]:
    """Ask the person; act only on their yes, and only through a command."""

    proposal = state["proposal"]
    scene = next((value for description, value in _context(state) if description == "Current scene id"), "SC-030")
    answer = interrupt({"message": f"Iniciar o workflow do bloco {proposal['block']} da cena {scene}?",
                        "action": proposal, "scene": scene})
    approved = (answer or {}).get("approved") if isinstance(answer, dict) else str(answer).lower() in ("yes", "sim", "true")
    if not approved:
        return {"messages": [AIMessage(content="Certo, não iniciei nada.")], "proposal": {}}
    result = dispatch(FILM, "start_workflow", {"scene_id": scene, "block": proposal["block"],
                                                "actor": {"id": "director-assistant", "kind": "agent"}})
    return {"messages": [AIMessage(content=f"Workflow iniciado para o bloco {proposal['block']} "
                                           f"(revisão {result.revision}). Ele vai parar no portão da imagem-mestre.")],
            "proposal": {}}


graph = StateGraph(Director)
graph.add_node("assistant", assistant)
graph.add_node("confirm", confirm)
graph.add_edge(START, "assistant")
graph.add_conditional_edges("assistant", route, {"confirm": "confirm", END: END})
graph.add_edge("confirm", END)
compiled = graph.compile(checkpointer=MemorySaver())

app = FastAPI()
add_langgraph_fastapi_endpoint(app, LangGraphAgent(name="director", graph=compiled), "/")
