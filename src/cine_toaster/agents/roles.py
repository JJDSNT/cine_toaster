"""The production roles of the Agent Runtime, declared (ADR 0034).

A role is what the Coordinator can hand a turn to, or what another role calls
for an independent look. It declares the model capabilities it needs, its
per-turn budgets, and the scratch it keeps in the CoAgent state: fields reset
at the start of every turn, and the few kept across turns. The graph derives
its state shape and the Coordinator's reset from these declarations, so a new
role is one declaration plus its nodes, not edits in four places.

Only implemented roles are declared. The roles still to come (Sequence
Adherence, Generation Operations, ...) are in the roadmap, not here: a role
listed is a role that runs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

KINDS = ("coordinator", "author", "reviewer", "technical")


@dataclass(frozen=True)
class Role:
    id: str
    title: str
    kind: str
    #: Model capabilities (`models.CAPABILITIES`) the role cannot work without.
    needs: frozenset[str] = frozenset({"structured_output"})
    #: steps, reads, writes, reviews, generations: what one turn may spend.
    budgets: dict[str, int] = field(default_factory=dict)
    #: Per-turn scratch: field -> its value at the start of a turn.
    scratch: dict[str, Any] = field(default_factory=dict)
    #: Fields the role keeps across turns (not reset): field -> type.
    kept: dict[str, type] = field(default_factory=dict)
    #: The role whose scratch and loop it shares, for a reviewer called inside another role's turn.
    within: str = ""


ROLES: dict[str, Role] = {role.id: role for role in (
    Role("coordinator", "Production Coordinator", "coordinator", budgets={"reads": 4}),
    Role("inception", "Inception", "author",
         budgets={"steps": 8, "reads": 4, "writes": 3},
         scratch={"inception_context": {}, "inception_steps": 0, "inception_reads": 0,
                  "inception_writes": 0, "inception_receipts": [], "pending_tool": {},
                  "returned_to_coordinator": False}),
    Role("art_direction", "Art Direction", "author",
         budgets={"steps": 8, "reviews": 2, "generations": 2},
         scratch={"art_context": {}, "art_steps": 0, "art_receipts": [], "art_pending": {},
                  "art_plan": {}, "art_plan_source": {}, "art_generations": 0, "art_reviews": 0,
                  "art_waiting": False, "art_review_request": "", "art_handoff_verified": False},
         kept={"art_job": str}),
    Role("visual_prevalidation", "Visual Prevalidation", "reviewer",
         needs=frozenset({"structured_output", "vision"}), within="art_direction"),
    Role("directing", "Directing / Shot Planning", "author",
         budgets={"steps": 8, "reviews": 2},
         scratch={"planning_context": {}, "planning_creation": {}, "planning_scene": "",
                  "planning_role": "directing", "planning_steps": 0, "planning_reviews": 0,
                  "planning_receipts": [], "planning_pending": {}, "planning_review_request": "",
                  "planning_resume_verified": False}),
    Role("continuity", "Script Supervisor / Continuity", "author", within="directing"),
    Role("continuity_review", "Independent continuity review", "reviewer", within="directing"),
)}

#: Roles the Coordinator (or another role) may hand a turn to, by the action that does it.
DELEGATIONS = {"delegate_inception": "inception", "delegate_art_direction": "art_direction",
               "delegate_directing": "directing", "delegate_continuity": "continuity"}


def scratch_reset() -> dict[str, Any]:
    """Every role's scratch at the start of a turn: one place, read from the declarations."""

    reset: dict[str, Any] = {}
    for role in ROLES.values():
        for name, value in role.scratch.items():
            reset[name] = type(value)() if isinstance(value, (dict, list)) else value
    return reset


def scratch_fields() -> dict[str, type]:
    """The state fields roles declare, with their types, for the graph's state shape."""

    fields: dict[str, type] = {}
    for role in ROLES.values():
        fields.update({name: type(value) for name, value in role.scratch.items()})
        fields.update(role.kept)
    return fields


def missing(role_id: str, model: Any) -> list[str]:
    """The capabilities `role_id` needs that `model` does not have."""

    from .models import supports

    return sorted(need for need in ROLES[role_id].needs if not supports(model, need))
