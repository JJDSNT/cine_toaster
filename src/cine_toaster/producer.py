"""Where a production stands: the Producer role's first slice (docs/production-agents.md).

Deterministic, read from the records Cine Toaster already keeps -- no model
is asked. For each sequence and scene: how many shots are in the cut, how many
have a take, are waiting for one to be chosen, or have none yet; the latest
version and whether the author has judged it; what blocks (error findings,
gates waiting for a person); and the decisions that come next.

    toast status <project> [--sequence ID]

It reports, it never decides: what to do next stays the author's.
"""

from __future__ import annotations

from typing import Any

#: A scene's version waiting for the author's verdict.
UNJUDGED = ("pending", "")
#: A decision no longer open: everything else (a proposal included) waits for the author.
SETTLED = {"approved", "complete", "completed", "selected", "decided", "answered", "rejected", "closed"}
COUNTS = ("in_cut", "chosen", "one_take", "awaiting_choice", "awaiting_generation", "composed")


def scene_status(scene: dict[str, Any]) -> dict[str, Any]:
    shots = [shot for shot in scene["shots"] if not shot.get("out_of_cut")]
    counts = dict.fromkeys(COUNTS, 0)
    counts["in_cut"] = len(shots)
    waiting_generation, waiting_choice = [], []
    for shot in shots:
        status = shot.get("status")
        if status == "selected":
            counts["chosen"] += 1
        elif status == "needs_review":  # more than one take, none chosen
            counts["awaiting_choice"] += 1
            waiting_choice.append(shot["id"])
        elif status == "ready":  # its only take goes to the cut until the author says otherwise
            counts["one_take"] += 1
        elif shot.get("source") == "composed":
            counts["composed"] += 1  # a card, a black screen, a title: made at the assembly
        else:
            counts["awaiting_generation"] += 1
            waiting_generation.append(shot["id"])
    versions = sorted(scene.get("assemblies") or [], key=lambda item: str(item.get("created_at") or ""))
    latest = versions[-1] if versions else None
    approved = scene.get("approved_assembly")
    errors = [finding for finding in scene.get("findings") or [] if finding.get("severity") == "error"]
    gates = [{"id": key, **value} for key, value in (scene.get("gates") or {}).items()
             if isinstance(value, dict) and value.get("state") in ("open", "waiting", "pending")]
    questions = [item for item in scene.get("decisions") or [] if item.get("status") not in SETTLED]
    blockers = [f"{len(errors)} error finding(s): " + "; ".join(sorted({f['code'] for f in errors}))] if errors else []
    blockers += [f"gate {gate['id']} waits for a person" for gate in gates]
    blockers += [str(item) for item in scene.get("blockers") or []]
    next_decisions = []
    if latest and (latest.get("verdict") or "") in UNJUDGED:
        next_decisions.append(f"judge version {latest['id']}")
    if waiting_choice:
        next_decisions.append(f"choose the take of {', '.join(waiting_choice)}")
    if questions:
        next_decisions.append(f"answer {len(questions)} open question(s)")
    if waiting_generation:
        next_decisions.append(f"generate {', '.join(waiting_generation)}")
    return {
        "id": scene["id"], "title": scene.get("title") or "", "shots": counts,
        "awaiting_generation": waiting_generation, "awaiting_choice": waiting_choice,
        "latest_version": {"id": latest["id"], "verdict": latest.get("verdict") or "pending"} if latest else None,
        "approved_version": approved.get("id") if isinstance(approved, dict) else None,
        "blockers": blockers, "open_questions": [str(item.get("question") or "")[:160] for item in questions],
        "next": next_decisions,
    }


def production_status(production: dict[str, Any], sequence_id: str = "") -> dict[str, Any]:
    scenes = {scene["id"]: scene for scene in production["scenes"]}
    groups = [item for item in production["sequences"] if not sequence_id or item["id"] == sequence_id]
    report = []
    for group in groups:
        rows = [scene_status(scenes[scene_id]) for scene_id in group["scene_ids"] if scene_id in scenes]
        totals = {key: sum(row["shots"][key] for row in rows) for key in COUNTS}
        totals["approved_scenes"] = sum(1 for row in rows if row["approved_version"])
        report.append({"id": group["id"], "label": group.get("label") or group["id"], "totals": totals,
                       "scenes": rows})
    return {"production": production.get("title") or production["id"], "sequences": report}


def render_text(status: dict[str, Any]) -> str:
    lines = [status["production"]]
    for group in status["sequences"]:
        t = group["totals"]
        lines.append("")
        lines.append(f"{group['label']}: {t['in_cut']} shots in the cut -- {t['chosen']} chosen, "
                     f"{t['one_take']} on their only take, {t['awaiting_choice']} waiting for a choice, "
                     f"{t['awaiting_generation']} awaiting generation, {t['composed']} composed; "
                     f"{t['approved_scenes']} of {len(group['scenes'])} scenes approved.")
        for row in group["scenes"]:
            s = row["shots"]
            version = row["latest_version"]
            judged = (f"latest {version['id']} ({version['verdict']})" if version else "no version yet")
            approved = f", approved {row['approved_version']}" if row["approved_version"] else ""
            lines.append(f"  {row['id']} {row['title']}: {s['chosen'] + s['one_take']}/{s['in_cut']} with a take"
                         + (f", {s['awaiting_generation']} awaiting generation" if s["awaiting_generation"] else "")
                         + (f", {s['awaiting_choice']} waiting for a choice" if s["awaiting_choice"] else "")
                         + f"; {judged}{approved}")
            for blocker in row["blockers"]:
                lines.append(f"      blocked: {blocker}")
            for item in row["next"]:
                lines.append(f"      next: {item}")
    return "\n".join(lines)
