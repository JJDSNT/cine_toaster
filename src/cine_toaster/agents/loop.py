"""One reasoning step for every production role (ADR 0034).

A role gives its direction (system prompt, prompt, answer schema) and its
tools; what happens around the model's answer is the same for all of them
and lives here, as KDP Studio's one flow does:

- the step budget is checked before the model is asked;
- an answer that is not an object, or names an action the role may not take,
  runs nothing;
- a delegation hands the turn to the declared role (`roles.DELEGATIONS`);
- `respond` ends the turn with an honest status, and `needs_review` only when
  the role has actually saved something for a person to review;
- any other allowed action waits in the role's pending field for its tool node.

Tools stay with their role: what they write, and which records they re-read
after writing, is the role's own knowledge.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from langchain_core.messages import AIMessage

from .roles import DELEGATIONS, ROLES

#: How a turn may end. `paused` only when the person asked for a pause.
STATUSES = ("complete", "needs_direction", "needs_review", "blocked")


@dataclass(frozen=True)
class Loop:
    role: str
    #: Its step counter and the field a chosen tool action waits in.
    steps: str
    pending: str
    schema: dict[str, Any]
    #: What it says when the step budget is spent.
    limit: str
    #: Whether a `needs_review` answer is backed by a saved request, and what is said when it is not.
    review_ready: Callable[[dict[str, Any]], bool]
    not_ready: str
    statuses: tuple[str, ...] = STATUSES
    #: Actions this state may choose; by default every action of the schema.
    allowed: Callable[[dict[str, Any]], tuple[str, ...]] | None = None
    #: The role shown as working while an action runs (a reviewer called inside the role).
    shown: Callable[[dict[str, Any], str], str] = field(default=lambda state, action: "")
    #: Actions only this role knows (Inception's return to the Coordinator): action -> handler.
    special: dict[str, Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], dict[str, Any]]] = field(
        default_factory=dict)

    @property
    def budget(self) -> int:
        return ROLES[self.role].budgets["steps"]

    def stop(self, state: dict[str, Any], message: str, status: str = "blocked", **extra: Any) -> dict[str, Any]:
        """End the turn: say it, clear what was waiting, and mark the turn complete."""

        return {"messages": [AIMessage(content=message)], self.pending: {}, "pending_tool": {}, "proposal": {},
                "completed_turn": state.get("turn", ""),
                "agent_status": {"role": state.get("active_role") or self.role, "state": status},
                **extra}

    def actions(self, state: dict[str, Any]) -> tuple[str, ...]:
        return self.allowed(state) if self.allowed else tuple(self.schema["properties"]["action"]["enum"])


def delegated(action: str, answer: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    """The turn handed to the declared role; scene-scoped roles take the scene named, or the one in view."""

    role = DELEGATIONS[action]
    update: dict[str, Any] = {"active_role": role, "proposal": {},
                              "agent_status": {"role": role, "state": "working"}}
    if role in ("directing", "continuity"):
        update.update(planning_role=role, planning_scene=answer.get("scene") or state.get("planning_scene", ""))
    return update


def step(loop: Loop, state: dict[str, Any], model: Any, system: str, prompt: str) -> dict[str, Any]:
    """Ask the model once and turn its answer into the next state, the same way for every role."""

    taken = state.get(loop.steps, 0)
    if taken >= loop.budget:
        return loop.stop(state, loop.limit, "resource_limit")
    try:
        answer = model.ask(system, prompt, loop.schema)
    except Exception as error:
        return loop.stop(state, f"Não consegui avançar este trabalho: {getattr(error, 'message', error)}")
    action = answer.get("action") if isinstance(answer, dict) else None
    if action not in loop.actions(state):
        return loop.stop(state, "O modelo não apresentou uma entrega, pergunta ou impedimento válido. "
                                "Não executei a ação.")
    update: dict[str, Any] = {loop.steps: taken + 1}
    if action in loop.special:
        return {**update, loop.pending: {}, **loop.special[action](state, answer, update)}
    if action in DELEGATIONS:
        return {**update, loop.pending: {}, "pending_tool": {}, **delegated(action, answer, state)}
    if action == "respond":
        status, reply = answer.get("status"), str(answer.get("reply") or "").strip()
        if status not in loop.statuses or not reply:
            return loop.stop(state, "O modelo não apresentou uma entrega, pergunta ou impedimento válido.")
        if status == "needs_review" and not loop.review_ready(state):
            return loop.stop(state, loop.not_ready)
        return {**update, **loop.stop(state, answer["reply"], status)}
    role = loop.shown(state, action) or state.get("active_role") or loop.role
    return {**update, loop.pending: answer, "active_role": role,
            "agent_status": {"role": role, "state": "working", "detail": action}}
