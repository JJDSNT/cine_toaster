"""Plan step 11 spike: the built-in `block` workflow, written as a LangGraph StateGraph.

Same jobs, same records, same gate record in the scene's state.json. LangGraph
owns only the position in the flow (its checkpoint). Run as:

    python block_graph.py <film> <checkpoint.sqlite> start|resume|decide ...
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Any, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from cine_toaster.jobs import JobManager, JobStore
from cine_toaster.pictures import picture_stem, picture_versions, relative
from cine_toaster.project import load_production, scene_directory
from cine_toaster.state import load_scene_state, now, with_progress, write_scene_state
from cine_toaster.takes import work_directory_for
from cine_toaster.workflows import _masters

MANAGER: JobManager | None = None


class Flow(TypedDict, total=False):
    root: str
    scene: str
    block: str
    masters: list[str]
    index: int
    seed: int
    gate: str
    decision: dict[str, Any]
    clip: str
    takes: list[str]


def _scene(state: Flow):
    production = load_production(Path(state["root"]))
    return next(item for item in production["scenes"] if item["id"] == state["scene"])


def _run(kind: str, root: str, params: dict[str, Any]) -> dict[str, Any]:
    """Submit a job and block this node until it ends -- the LangGraph way: a node is a call."""

    job = MANAGER.wait(MANAGER.submit(kind, Path(root), params)["id"], timeout=600)
    if job["state"] != "succeeded":
        raise RuntimeError(f"{kind}: {job.get('error') or job['state']}")
    return MANAGER.adopt(job["id"])["result"]["summary"]


# --- nodes ---------------------------------------------------------------------------


def plan(state: Flow) -> Flow:
    scene = _scene(state)
    block = next(item for item in scene["blocks"] if item["id"] == state["block"])
    return {"masters": [shot["id"] for shot in _masters(scene, block["shots"])], "index": 0, "seed": 1}


def picture(state: Flow) -> Flow:
    scene = _scene(state)
    shot = next(item for item in scene["shots"] if item["id"] == state["masters"][state["index"]])
    work = work_directory_for(Path(state["root"]) / scene["file"])
    asked_again = (state.get("decision") or {}).get("outcome") == "changes_requested"
    if picture_versions(work, picture_stem(work, str(shot["number"]))) and not asked_again:
        return {}  # idempotent: a picture that exists is not made again
    _run("derive_picture", state["root"], {"scene": state["scene"], "shot": shot["id"], "seed": state["seed"]})
    return {}


def open_gate(state: Flow) -> Flow:
    """Open the gate as a production record; its id goes into the graph's state.

    A separate node, because LangGraph re-runs an interrupted node from its
    start on resume and keeps none of its local values: opening and waiting in
    one node opened a second gate on every resume (found in this spike).
    """

    root = Path(state["root"])
    scene = _scene(state)
    shot_id = state["masters"][state["index"]]
    directory = scene_directory(root, state["scene"])
    records = load_scene_state(directory, state["scene"])
    if records.approved_pictures().get(shot_id) and (state.get("decision") or {}).get("outcome") != "changes_requested":
        return {"gate": "", "decision": {"outcome": "approved", "chosen": records.approved_pictures()[shot_id]}}
    shot = next(item for item in scene["shots"] if item["id"] == shot_id)
    work = work_directory_for(root / scene["file"])
    candidates = [relative(root, p) for p in picture_versions(work, picture_stem(work, str(shot["number"])))]
    gate_id = "gate_" + uuid.uuid4().hex[:12]
    record = {"id": gate_id, "kind": "approve_picture", "subject": shot_id, "workflow": None, "step": "langgraph",
              "state": "waiting", "candidates": candidates, "chosen": "", "requested_at": now(),
              "requested_by": {"id": "langgraph", "kind": "system"}}
    write_scene_state(directory, with_progress(records, gates={**records.gates, gate_id: record},
                                                workflows=records.workflows))
    return {"gate": gate_id, "decision": {}}


def gate(state: Flow) -> Flow:
    """Wait for the person; then read the decision from the production record."""

    if not state.get("gate"):
        return {}
    interrupt({"gate": state["gate"], "shot": state["masters"][state["index"]]})
    directory = scene_directory(Path(state["root"]), state["scene"])
    decided = load_scene_state(directory, state["scene"]).gates[state["gate"]]
    if decided["state"] == "waiting":
        # Resumed without a decision: wait again rather than guess.
        interrupt({"gate": state["gate"], "still_waiting": True})
    return {"decision": {"outcome": decided["state"], "chosen": decided.get("chosen", "")}}


def after_gate(state: Flow) -> str:
    outcome = state["decision"]["outcome"]
    if outcome == "changes_requested":
        return "again"
    if outcome == "rejected":
        return "stop"
    return "next" if state["index"] + 1 < len(state["masters"]) else "generate"


def again(state: Flow) -> Flow:
    return {"seed": state["seed"] + 1}


def next_master(state: Flow) -> Flow:
    return {"index": state["index"] + 1, "decision": {}, "gate": ""}


def generate(state: Flow) -> Flow:
    summary = _run("generate_block", state["root"], {"scene": state["scene"], "block": state["block"]})
    return {"clip": summary["clip"]}


def slice_(state: Flow) -> Flow:
    summary = _run("slice_block", state["root"], {"scene": state["scene"], "block": state["block"],
                                                 "clip": state["clip"].rsplit("/", 1)[-1]})
    return {"takes": [f"{item['shot']}:{item['take']}" for item in summary["slices"]]}


def build(checkpointer):
    graph = StateGraph(Flow)
    for name, node in (("plan", plan), ("picture", picture), ("open_gate", open_gate), ("gate", gate),
                       ("again", again), ("next", next_master), ("generate", generate), ("slice", slice_)):
        graph.add_node(name, node)
    graph.add_edge(START, "plan")
    graph.add_edge("plan", "picture")
    graph.add_edge("picture", "open_gate")
    graph.add_edge("open_gate", "gate")
    graph.add_conditional_edges("gate", after_gate, {"again": "again", "stop": END, "next": "next", "generate": "generate"})
    graph.add_edge("again", "picture")
    graph.add_edge("next", "picture")
    graph.add_edge("generate", "slice")
    graph.add_edge("slice", END)
    return graph.compile(checkpointer=checkpointer)


def main() -> None:
    global MANAGER
    film, store, action, thread = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    import fakes  # the same fake RunPod as the tests: no money

    fakes.install()
    MANAGER = JobManager(store=JobStore(Path(store).with_suffix(".jobs.sqlite")))
    config = {"configurable": {"thread_id": thread}}
    with SqliteSaver.from_conn_string(store) as saver:
        graph = build(saver)
        if action == "start":
            result = graph.invoke({"root": film, "scene": "SC-030", "block": "A"}, config)
        else:
            result = graph.invoke(Command(resume="decided"), config)
        snapshot = graph.get_state(config)
        print(json.dumps({"next": list(snapshot.next), "interrupts": [i.value for i in result.get("__interrupt__", [])],
                          "takes": result.get("takes"), "checkpoints": len(list(graph.get_state_history(config)))}))
    MANAGER.shutdown()


if __name__ == "__main__":
    main()
