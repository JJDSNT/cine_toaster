#!/bin/bash
S=$(cd "$(dirname "$0")" && pwd); cd "$S"
export XDG_STATE_HOME=$S/state XDG_CACHE_HOME=$S/cache SPIKE_CLIP=$S/made.mp4 SPIKE_LOG=$S/sent.log PYTHONPATH=$S
PY=$S/venv/bin/python
graph() { $PY block_graph.py "$S/film" "$S/cp.sqlite" "$@"; }
decide() { $PY - "$@" <<'PY'
import sys, json; from pathlib import Path
from cine_toaster.commands import dispatch
from cine_toaster.project import scene_directory
from cine_toaster.state import load_scene_state
film, outcome, index = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3])
state = load_scene_state(scene_directory(film, "SC-030"), "SC-030")
gate = next(g for g in state.gates.values() if g["state"] == "waiting")
payload = {"scene_id": "SC-030", "gate_id": gate["id"], "outcome": outcome, "actor": {"id": "director", "kind": "human"},
           "reasons": [] if outcome == "approved" else ["subject_moved"]}
if outcome == "approved": payload["chosen"] = gate["candidates"][index]
dispatch(film, "decide_gate", payload); print("decided", outcome, len(gate["candidates"]), "candidates")
PY
}
