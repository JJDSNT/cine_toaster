"""Where the film stands, phase by phase: done, happening, waiting for the director, next.

The director asked (2026-10-17, Demo 01) for a progress timeline instead of a
wall of pending items and job cards: what we did, what is happening, what comes
next, and what they should do. This is a read-only projection of records that
already exist -- the production, the Creation journal, handoffs, the decision
inbox and jobs (CT-0088: an explainable projection, not a second status
system). Every phase says the number it rests on.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

#: The production flow (production-flow.md, the work policy), in order.
PHASES = (("inception", "Inception"), ("screenplay", "Screenplay"), ("storyboard", "Storyboard"),
          ("blockout", "Blockout / 3D"), ("masters", "Master images"), ("clips", "Clips"),
          ("assembly", "Assembly"))
#: Seconds one reference picture takes, and how many run at once (measured on Demo 01's batch).
PICTURE_SECONDS, PICTURES_AT_ONCE = 90, 2


def _jobs(jobs: list[dict[str, Any]]) -> dict[str, Any]:
    pictures = [job for job in jobs if job.get("kind") == "generate_reference"]
    count = {state: sum(1 for job in pictures if job.get("state") == state)
             for state in ("queued", "running", "succeeded", "failed", "cancelled", "interrupted")}
    waiting = count["queued"] + count["running"]
    return {**count, "pictures": len(pictures), "active": waiting,
            "eta_minutes": round(waiting * PICTURE_SECONDS / PICTURES_AT_ONCE / 60) if waiting else 0}


def production_progress(root: Path, jobs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    from .creation import creation_view
    from .decision_inbox import decision_inbox
    from .project import load_production
    from .read_scope import read_scope

    with read_scope():
        production = load_production(root)
        creation = creation_view(root)
        inbox = decision_inbox(root)
    scenes = production["scenes"]
    shots = [shot for scene in scenes for shot in scene["shots"]]
    handoffs = [item for item in creation.get("handoffs", []) if not item.get("superseded")]
    handoff = handoffs[-1] if handoffs else None
    # The current work's jobs: those started since the request in hand, not the film's whole history.
    since = handoff["created_at"] if handoff else ""
    work = _jobs([job for job in jobs or [] if str(job.get("created_at") or "") >= since])
    decisions = creation.get("assessment_decisions", [])
    you = inbox["items"][0] if inbox["items"] else None

    phases: list[dict[str, Any]] = []

    def phase(identity: str, state: str, summary: str, url: str = "") -> None:
        phases.append({"id": identity, "label": dict(PHASES)[identity], "state": state, "summary": summary, "url": url})

    approved = sum(1 for item in decisions if item["outcome"] == "approved")
    phase("inception", "done" if approved else "active" if creation.get("assessments") else "next",
          f"{len(creation.get('references', []))} references, {approved} direction(s) approved",
          "/app/creation.html")
    phase("screenplay", "done" if scenes and shots else "next",
          f"{len(scenes)} scenes, {len(shots)} shots" if scenes else "no screenplay scenes yet", "/app/preproduction.html")

    storyboard_approved = sum(1 for scene in scenes if (scene.get("phase") or {}).get("phase") == "production")
    if storyboard_approved == len(scenes) and scenes:
        phase("storyboard", "done", f"{len(scenes)} of {len(scenes)} scenes approved", "/app/preproduction.html")
    elif you and you.get("kind") == "direction" and "storyboard" in (you.get("question", "") + you.get("scope", "")).lower():
        phase("storyboard", "waiting_you", "drawings ready for your review", you.get("url", ""))
    elif handoff:
        coverage = handoff.get("coverage") or {}
        drawing = f", {work['running']} drawing now, {work['queued']} queued" if work["active"] else ""
        refused = f", {work['failed']} refused by the image model" if work["failed"] else ""
        phase("storyboard", "active", f"{coverage.get('drawn', 0)} of {coverage.get('shots', 0)} drawn{drawing}{refused}",
              "/app/decisions.html#agent-work")
    else:
        phase("storyboard", "next", f"{storyboard_approved} of {len(scenes)} scenes approved", "/app/preproduction.html")

    blocked_out = sum(1 for scene in scenes if (scene.get("geometry") or {}).get("cameras"))
    pictured = [shot for shot in shots if shot.get("derive")]
    # A blockout is needed where a master is made from a 3D board or a set's plate. A film whose masters
    # are finished from its storyboard skips it, and says so rather than showing it half done (Demo 01).
    needs_3d = [shot for shot in pictured if str(shot["derive"].get("from") or "").lower().startswith(("board", "location"))]
    if pictured and not needs_3d:
        phase("blockout", "skipped", "Not needed: the master images are finished from the storyboard"
              + (f" ({blocked_out} scene(s) also have a 3D layout)" if blocked_out else ""))
    else:
        phase("blockout", "active" if 0 < blocked_out < len(scenes) else "done" if scenes and blocked_out == len(scenes)
              else "later", f"{blocked_out} of {len(scenes)} scenes laid out in 3D")
    # Title and composed shots make no picture: they are not counted against the masters.
    counted = pictured or shots
    masters = sum(1 for shot in counted if shot.get("approved_picture"))
    asking = sum(1 for scene in scenes for gate in (scene.get("gates") or {}).values()
                 if gate.get("kind") == "approve_picture" and gate.get("state") == "waiting")
    phase("masters", "done" if counted and masters == len(counted) else "waiting_you" if asking
          else "active" if masters else "later",
          f"{masters} of {len(counted)} master images approved" + (f"; {asking} waiting for you" if asking else ""),
          "/app/preproduction.html" if asking else "")
    clips = sum(1 for shot in shots if shot.get("selected_take"))
    phase("clips", "done" if shots and clips == len(shots) else "active" if clips else "later",
          f"{clips} of {len(shots)} shots with a chosen take")
    versions = sum(len(sequence.get("versions") or []) for sequence in production.get("sequences") or [])
    phase("assembly", "active" if versions else "later", f"{versions} assembled version(s)")

    current = next((item for item in phases if item["state"] in ("waiting_you", "active")), None)
    upcoming = next((item for item in phases if item["state"] in ("next", "later")), None)
    if work["active"]:
        now = (f"Drawing the storyboard: {work['running']} picture(s) in progress, {work['queued']} queued "
               f"-- about {work['eta_minutes']} min left.")
    elif inbox.get("agent_work_count"):
        now = "The AI has approved work to carry on; nothing is generating at this moment."
    else:
        now = "Nothing is running."
    if you:
        action = {"text": you.get("question", "A decision waits for you."), "url": you.get("url", ""),
                  "kind": you.get("kind", "")}
    else:
        action = {"text": "Nothing waits for you right now." + (" Come back when the drawings are done."
                  if work["active"] else ""), "url": "", "kind": ""}
    return {"project_id": production["id"], "title": production.get("title", ""), "phases": phases,
            "current": current["id"] if current else "", "now": now, "you": action,
            "next": f"{upcoming['label']}: {upcoming['summary']}" if upcoming else "",
            "jobs": work, "pending_decisions": inbox["pending_count"],
            "meaning": "Derived from the film's records and jobs; a phase's number is its evidence."}
