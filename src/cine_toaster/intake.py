"""Format intake: what a format needs to be known, asked by an agent, answered by a person (SPEC-0020).

A format style (`style_assets/<format>/style.toml`, kind `format`) carries an
intake sheet: the items a production of that format needs before its stages
can advance, each with why it matters and which stage it unlocks. The
Inception role compares the sheet with the production's records and asks
only what it cannot establish, a few questions at a time. Questions and
answers are records in the Creation journal; an answer is a person's, never
an agent's. Nothing here edits the production: an answer naming a format
is not a `style:` declaration, and an answered sheet is not an approval.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from .creation import _commit, load_creation
from .errors import PermissionDeniedError, ResourceNotFoundError, RevisionConflictError, ValidationError
from .events import Event, append_event
from .project import load_production
from .state import Actor, now, scene_lock

STAGES = ("inception", "screenplay", "storyboard", "masters", "clips", "assembly", "budget")
#: Open questions at once: a few, so the person is interviewed, not handed a form.
MAX_OPEN = 5
#: Asked of every film whose format is neither declared nor answered.
FORMAT_ITEM = {"id": "format", "ask": "What kind of film is this (a music video, an advertisement, a short...)?",
               "why": "The format decides what else must be known and the rules every stage follows.",
               "unlocks": "inception", "required": True}


def sheet_items(style: dict[str, Any]) -> list[dict[str, Any]]:
    """A format style's intake items, checked; an item without its reason is not an item."""

    items = []
    for raw in style.get("intake") or []:
        item = {"id": str(raw.get("id") or ""), "ask": str(raw.get("ask") or ""), "why": str(raw.get("why") or ""),
                "unlocks": str(raw.get("unlocks") or ""), "required": bool(raw.get("required", True))}
        if not item["id"] or not item["ask"] or not item["why"] or item["unlocks"] not in STAGES:
            raise ValidationError(f"The intake of {style.get('id')!r} has an item without id, ask, why or a stage",
                                  allowed=list(STAGES))
        items.append(item)
    return items


def _format(root: Path, production: dict[str, Any], answers: dict[str, dict]) -> tuple[dict | None, str]:
    """The format in force and where it comes from: the production's `style:`, else an answer naming one."""

    from .styles import list_styles, lookup, resolve

    catalog = {item["id"]: item for item in list_styles(root)}
    parts, _ = resolve(catalog, project=production.get("style"))
    declared = next((style for style, _level in parts if style["axis"] == "format"), None)
    if declared:
        return declared, "declared"
    answer = answers.get("format")
    if answer:
        named = catalog.get(answer["answer"].strip().lower()) or lookup(catalog, answer["answer"])
        if named and named["axis"] == "format":
            return named, "answered"
    return None, ""


def validate_intake(state: dict[str, Any]) -> None:
    questions = state.get("intake_questions", [])
    answers = state.get("intake_answers", [])
    if not isinstance(questions, list) or not isinstance(answers, list):
        raise ValueError("Invalid intake record lists")
    known: dict[str, dict] = {}
    for item in questions:
        if (not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"]
                or item["id"] in known
                or any(not isinstance(item.get(key), str) or not item[key].strip()
                       for key in ("item", "question", "why", "asked_at"))
                or len(item["question"]) > 1000 or len(item["why"]) > 1000
                or not isinstance(item.get("format"), str) or not isinstance(item.get("based_on"), str)
                or not isinstance(item.get("actor"), dict) or item["actor"].get("kind") != "agent"):
            raise ValueError("Invalid intake question")
        known[item["id"]] = item
    answered: set[str] = set()
    for item in answers:
        if (not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"]
                or item.get("question") not in known or item["question"] in answered
                or not isinstance(item.get("answer"), str) or not item["answer"].strip()
                or len(item["answer"]) > 4000 or not isinstance(item.get("answered_at"), str)
                or not isinstance(item.get("actor"), dict) or not _answered_by_a_person(item)):
            raise ValueError("Invalid intake answer")
        answered.add(item["question"])


def _answered_by_a_person(item: dict[str, Any]) -> bool:
    """A person typed it here, or said it in conversation and an agent recorded their exact words."""

    if item["actor"].get("kind") == "human":
        return True
    source = item.get("source")
    return (item["actor"].get("kind") == "agent" and isinstance(source, dict)
            and source.get("kind") == "conversation" and isinstance(source.get("quote"), str)
            and source["quote"].strip() != "" and len(source["quote"]) <= 2000)


def intake_view(root: Path, state: dict[str, Any] | None = None,
                production: dict[str, Any] | None = None) -> dict[str, Any]:
    """The sheet against what was asked and answered; what is missing is the agent's to ask, not the person's to fill."""

    root = Path(root).expanduser().resolve()
    production = load_production(root) if production is None else production
    state = load_creation(root, production=production) if state is None else state
    answers_by_question = {item["question"]: item for item in state.get("intake_answers", [])}
    latest: dict[str, dict] = {}
    for question in state.get("intake_questions", []):
        latest[question["item"]] = question
    answers = {item: answers_by_question[question["id"]] for item, question in latest.items()
               if question["id"] in answers_by_question}
    style, source = _format(root, production, answers)
    # Before a film has scenes the format decides everything else; once it is written and broken
    # down, not knowing the format's name is a gap to note, not a gate (Demo 01: a 24-shot film's
    # storyboard request was held up by "what kind of film is this?").
    developed = bool(production.get("scenes"))
    items = [{**FORMAT_ITEM, "required": not developed}] if source != "declared" else []
    items += sheet_items(style) if style else []
    rows = []
    for item in items:
        question = latest.get(item["id"])
        answer = answers_by_question.get(question["id"]) if question else None
        rows.append({**item, "status": "answered" if answer else "open" if question else "not_asked",
                     "question": question, "answer": answer})
    extra = [{"id": key, "ask": question["question"], "why": question["why"], "unlocks": "", "required": False,
              "status": "answered" if question["id"] in answers_by_question else "open", "question": question,
              "answer": answers_by_question.get(question["id"])}
             for key, question in latest.items() if key not in {item["id"] for item in items}]
    rows += extra
    open_questions = [row["question"] for row in rows if row["status"] == "open"]
    return {"project_id": production["id"], "revision": state["revision"],
            "format": {"id": style["id"], "name": style["name"], "source": source} if style else None,
            # The production's own words about its format (`format:` in project.yaml): evidence, not a style.
            "production_says": str(production.get("format") or ""),
            "items": rows, "open": open_questions, "open_count": len(open_questions),
            "missing_required": [row["id"] for row in rows if row["required"] and row["status"] == "not_asked"],
            "meaning": "Answers are the person's words, kept as records (typed here, or quoted from conversation). An answered sheet is not approval, "
                       "and a missing item may already be established elsewhere in the records.",
            "url": "/app/decisions.html#intake"}


def ask_intake(root: Path, *, questions: list[dict[str, Any]], expected_revision: int, actor: Actor) -> dict[str, Any]:
    """An agent asks a few questions of a person, each with the reason; it never answers them."""

    if actor.kind != "agent":
        raise PermissionDeniedError("Intake questions are asked by a production agent")
    if not isinstance(questions, list) or not questions:
        raise ValidationError("Ask at least one question")
    if type(expected_revision) is not int or expected_revision < 0:
        raise ValidationError("expected_revision must be a non-negative integer")
    root = Path(root).expanduser().resolve()
    with scene_lock(root):
        production = load_production(root)
        state = load_creation(root, production=production)
        if state["revision"] != expected_revision:
            raise RevisionConflictError(expected_revision, state["revision"])
        view = intake_view(root, state, production)
        rows = {row["id"]: row for row in view["items"]}
        if view["open_count"] + len(questions) > MAX_OPEN:
            raise ValidationError(f"At most {MAX_OPEN} questions may wait for the person at once; "
                                  f"{view['open_count']} already do")
        asked, seen = [], set()
        for raw in questions:
            if not isinstance(raw, dict):
                raise ValidationError("Each question is an object with item, question and why")
            key, text, why = (str(raw.get(name) or "").strip() for name in ("item", "question", "why"))
            if not key or not text or not why or len(text) > 1000 or len(why) > 1000:
                raise ValidationError("A question needs its sheet item (or a new id), its words and why it matters")
            row = rows.get(key)
            if key in seen or (row and row["status"] == "open"):
                raise ValidationError(f"The item {key!r} already has an open question")
            based_on = str(raw.get("based_on") or "")
            if row and row["status"] == "answered" and based_on != row["answer"]["id"]:
                raise ValidationError(f"The item {key!r} was answered; asking again names that answer in based_on")
            seen.add(key)
            asked.append({"id": "intake_q_" + uuid.uuid4().hex[:16], "item": key, "question": text, "why": why,
                          "format": (view["format"] or {}).get("id", ""), "based_on": based_on,
                          "actor": actor.public_dict(), "asked_at": now()})
        committed = {**state, "revision": state["revision"] + 1,
                     "intake_questions": [*state.get("intake_questions", []), *asked]}
        validate_intake(committed)
        _commit(root, committed)
        append_event(root, Event.create("creation.intake_asked", state["project_id"], revision=committed["revision"],
                                        questions=[item["id"] for item in asked], actor=actor.public_dict()))
        return {"revision": committed["revision"], "questions": asked}


def answer_intake(root: Path, *, question: str, answer: str, expected_revision: int, actor: Actor,
                  quote: str = "") -> dict[str, Any]:
    """A person's answer, kept in their words. One answer per question; asking again is a new question.

    A person may also answer in conversation: an agent then records it with `quote`, the person's
    exact words (the Agent Runtime checks they are in the person's messages before calling). The
    answer is still theirs; the agent is only who wrote it down.
    """

    if actor.kind == "agent":
        if not isinstance(quote, str) or not quote.strip() or len(quote) > 2000:
            raise PermissionDeniedError("An agent records an answer only with the person's exact words (quote)")
    elif actor.kind != "human":
        raise PermissionDeniedError("An intake question is answered by a person")
    if not isinstance(answer, str) or not answer.strip() or len(answer) > 4000:
        raise ValidationError("An answer is non-empty text of at most 4000 characters")
    if type(expected_revision) is not int or expected_revision < 0:
        raise ValidationError("expected_revision must be a non-negative integer")
    root = Path(root).expanduser().resolve()
    with scene_lock(root):
        state = load_creation(root)
        if state["revision"] != expected_revision:
            raise RevisionConflictError(expected_revision, state["revision"])
        if not any(item["id"] == question for item in state.get("intake_questions", [])):
            raise ResourceNotFoundError(f"No intake question {question!r}")
        if any(item["question"] == question for item in state.get("intake_answers", [])):
            raise ValidationError("This question was already answered; the agent asks again if it needs more")
        item = {"id": "intake_a_" + uuid.uuid4().hex[:16], "question": question, "answer": answer.strip(),
                "actor": actor.public_dict(), "answered_at": now()}
        if actor.kind == "agent":
            item["source"] = {"kind": "conversation", "quote": quote.strip()}
        committed = {**state, "revision": state["revision"] + 1,
                     "intake_answers": [*state.get("intake_answers", []), item]}
        validate_intake(committed)
        _commit(root, committed)
        append_event(root, Event.create("creation.intake_answered", state["project_id"], revision=committed["revision"],
                                        question=question, actor=actor.public_dict()))
        return {"revision": committed["revision"], "answer": item}


def inbox_items(view: dict[str, Any]) -> list[dict[str, Any]]:
    """Open questions as requests to the person, with the reason each matters."""

    return [{"id": question["id"], "kind": "question", "title": "Interview: " + question["item"],
             "question": question["question"], "scope": (view["format"] or {}).get("name") or "Format not known yet",
             "why": question["why"], "next_step": "The Inception agent continues with your answer.",
             "url": "/app/decisions.html?" + urlencode({"question": question["id"]}) + "#intake",
             "actions": ["answer"]} for question in view["open"]]
