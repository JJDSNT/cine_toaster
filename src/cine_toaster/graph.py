"""The production canvas: records projected as nodes and edges (plan step 7).

The canvas is a **view** of project records, never a file of its own
(CT-0022, CT-0023). This module builds that view: scenes, shots and takes as
nodes, and cuts, take membership and scene order as edges. It carries no
positions. Where a card sits on screen is a presentation choice, made by the
interface's automatic layout.

Being in the core rather than in the interface, the same projection serves
the canvas, the CLI and, later, agents.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .project import load_production
from .takes import shot_key

#: What a shot shows on its card, most finished first.
PICTURE_LEVELS = ("still", "take", "blocking", "none")


def _picture(scene: dict[str, Any], shot: dict[str, Any], root: Path | None = None) -> dict[str, Any]:
    """The best picture a shot has, and which storyboard level it is (CT-0025)."""

    # A master picture a person approved (SPEC-0009), else the master's own.
    if shot.get("approved_picture"):
        return {"level": "still", "image": f"/media/{shot['approved_picture']}"}
    if root is not None and shot.get("derive"):
        from .pictures import picture_stem, picture_versions, relative
        from .takes import work_directory_for

        work = work_directory_for(root / scene["file"])
        versions = picture_versions(work, picture_stem(work, str(shot.get("number"))))
        if versions:
            return {"level": "still", "image": f"/media/{relative(root, versions[0])}"}
    if shot.get("still"):
        return {"level": "still", "image": f"/media/{shot['still']}"}
    takes = shot.get("takes") or []
    chosen = next((take for take in takes if take.get("selected")), None)
    if chosen and chosen.get("poster"):
        return {"level": "take", "image": f"/media/{chosen['poster']}"}
    if chosen and chosen.get("media"):
        return {"level": "take", "video": f"/media/{chosen['media']}"}
    if ((shot.get("motion") or {}).get("start") or {}).get("camera"):
        return {"level": "blocking",
                "image": f"/api/blocking-frame?scene={scene['id']}&shot={shot['id']}&at=start"}
    if root is not None:
        # A render of the 3D set that only points to its file is a blocking frame too.
        from .pictures import _file, relative

        for item in shot.get("from") or []:
            path = _file(root / scene["file"], str(item.get("ref") or ""))
            if path is not None and path.is_relative_to(root.resolve()):
                return {"level": "blocking", "image": f"/media/{relative(root, path)}"}
    return {"level": "none"}


def _severity(findings: list[dict[str, Any]]) -> str:
    severities = {finding.get("severity") for finding in findings}
    for level in ("error", "warning", "advice"):
        if level in severities:
            return level
    return ""


def production_graph(production: dict[str, Any], root: Path | None = None) -> dict[str, Any]:
    """Nodes and edges for a loaded production (`load_production`'s dict).

    With the project `root`, master pictures are looked up on disk too.
    """

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    previous_last: str | None = None
    previous_scene: str | None = None

    locations = production.get("locations") or {}
    for scene_index, scene in enumerate(production["scenes"]):
        scene_node = f"scene:{scene['id']}"
        # The empty set, by camera: what a shot's picture may be made from (SPEC-0010).
        plates = [{"camera": ref["camera"], "path": ref["path"]}
                  for ref in (locations.get(scene.get("location") or "") or {}).get("references") or []
                  if ref.get("kind") == "plate" and ref.get("camera") and ref.get("exists")]
        nodes.append({
            "id": scene_node,
            "type": "scene",
            "scene": scene["id"],
            "data": {
                "scene": scene["id"], "title": scene["title"], "order": scene_index,
                "sequence": scene.get("sequence") or "", "status": scene.get("status") or "",
                # The revision a canvas edit is made against: a stale edit is refused.
                "revision": scene.get("revision", 0),
                "location": scene.get("location") or "",
                "plates": plates,
                "findings": len(scene.get("findings") or []),
                "severity": _severity(scene.get("findings") or []),
            },
        })
        shot_findings: dict[str, list[dict[str, Any]]] = {}
        for finding in scene.get("findings") or []:
            for shot_id in finding.get("shots") or []:
                shot_findings.setdefault(shot_id, []).append(finding)

        shot_nodes: list[str] = []
        for shot_index, shot in enumerate(scene["shots"]):
            node_id = f"shot:{scene['id']}/{shot['id']}"
            shot_nodes.append(node_id)
            script = shot.get("script") or {}
            motion = shot.get("motion") or {}
            found = shot_findings.get(shot["id"], [])
            nodes.append({
                "id": node_id,
                "type": "shot",
                "scene": scene["id"],
                "data": {
                    "scene": scene["id"], "shot": shot["id"], "order": shot_index,
                    "label": shot.get("label") or "", "camera": shot.get("camera") or "",
                    "duration_seconds": shot.get("duration_seconds") or 0,
                    "status": shot.get("status") or "", "source": shot.get("source") or "",
                    "selected_take": shot.get("selected_take") or "",
                    "takes": len(shot.get("takes") or []),
                    "speakers": sorted({line["who"] for line in script.get("dialogue") or []}),
                    "move": motion.get("kind") or "",
                    "walks": bool(motion.get("moved_subjects")),
                    "picture": _picture(scene, shot, root),
                    "block": shot.get("block") or "",
                    "findings": len(found), "severity": _severity(found),
                    # What the picture is made from, and whose faces a derived one takes (CT-0046).
                    "number": str(shot.get("number") or ""),
                    "from": list(dict.fromkeys(str(item.get("ref") or "") for item in shot.get("from") or []
                                               if isinstance(item, dict))),
                    "derived": bool(shot.get("derive")),
                    "with": list((shot.get("derive") or {}).get("with") or []),
                    "reference_decided": bool(shot.get("reference_decision")),
                    "authored_from": list(dict.fromkeys(str(item.get("ref") or "") for item in shot.get("authored_from") or []
                                                        if isinstance(item, dict))),
                    "authored_with": list(shot.get("authored_with") or []),
                },
            })
            for take in shot.get("takes") or []:
                take_id = f"take:{scene['id']}/{shot['id']}/{take['id']}"
                nodes.append({
                    "id": take_id,
                    "type": "take",
                    "scene": scene["id"],
                    "data": {
                        "scene": scene["id"], "shot": shot["id"], "take": take["id"],
                        "label": take.get("label") or take["id"], "status": take.get("status") or "",
                        "selected": bool(take.get("selected")),
                        "media": f"/media/{take['media']}" if take.get("media") else "",
                        "poster": f"/media/{take['poster']}" if take.get("poster") else "",
                    },
                })
                edges.append({"id": f"of:{take_id}", "type": "take", "source": node_id, "target": take_id,
                              "data": {"selected": bool(take.get("selected"))}})

        # The latest workflow run of each block (SPEC-0009), linked to its first shot.
        latest: dict[str, dict[str, Any]] = {}
        for run in scene.get("runs") or []:  # newest first
            subject = run.get("subject", {})
            key = f"shot:{subject['shot']}" if subject.get("shot") else f"block:{subject.get('block', '')}"
            latest.setdefault(key, run)
        blocks = {block["id"]: block for block in scene.get("blocks") or []}
        for run in latest.values():
            block_id = str(run.get("subject", {}).get("block", ""))
            single = str(run.get("subject", {}).get("shot", ""))
            run_node = f"run:{scene['id']}/{run['id']}"
            waiting = next((step for step in run["steps"] if step["state"] == "waiting"), None)
            nodes.append({
                "id": run_node, "type": "run", "scene": scene["id"],
                "data": {
                    "scene": scene["id"], "run": run["id"], "block": block_id, "shot": single, "state": run["state"],
                    "steps": [{"label": step["label"], "state": step["state"], "kind": step["kind"]}
                              for step in run["steps"]],
                    "waiting": waiting["label"] if waiting else "",
                },
            })
            shots = [single] if single else (blocks.get(block_id) or {}).get("shots") or []
            if shots:
                edges.append({"id": f"runs:{run_node}", "type": "run", "source": run_node,
                              "target": f"shot:{scene['id']}/{shots[0]}", "data": {"state": run["state"]}})

        # Lineage: a shot made from another shot of the scene (CT-0046).
        by_number = {shot_key(shot.get("number")): shot for shot in scene["shots"]}
        drawn: set[str] = set()
        for shot in scene["shots"]:
            for item in shot.get("from") or []:
                ref = str(item.get("ref") or "") if isinstance(item, dict) else ""
                source = by_number.get(shot_key(ref)) if ref else None
                edge_id = f"from:{scene['id']}/{source['id']}-{shot['id']}" if source else ""
                if source is None or source["id"] == shot["id"] or edge_id in drawn:
                    continue
                drawn.add(edge_id)
                edges.append({"id": f"from:{scene['id']}/{source['id']}-{shot['id']}", "type": "lineage",
                              "source": f"shot:{scene['id']}/{source['id']}", "target": f"shot:{scene['id']}/{shot['id']}",
                              "data": {"relation": str(item.get("relation") or ""), "decided": bool(item.get("decided"))}})

        # Within a scene every join is a cut record (SPEC-0007).
        by_pair = {(cut["from"], cut["to"]): cut for cut in scene.get("cuts") or []}
        for (before, after) in zip(scene["shots"], scene["shots"][1:]):
            cut = by_pair.get((before["id"], after["id"]), {"type": "hard", "findings": []})
            transition = cut.get("transition") or {}
            edges.append({
                "id": f"cut:{scene['id']}/{before['id']}-{after['id']}",
                "type": "cut",
                "source": f"shot:{scene['id']}/{before['id']}",
                "target": f"shot:{scene['id']}/{after['id']}",
                "data": {
                    "cut": cut.get("type", "hard"), "chain": cut.get("chain") or "",
                    "reason": cut.get("reason") or "", "transition": transition.get("id") or "",
                    "findings": [finding["code"] for finding in cut.get("findings") or []],
                    "severity": _severity(cut.get("findings") or []),
                    # Plan step 13: a cut decided here, over what the breakdown says.
                    "decided": bool(after.get("cut_decision")),
                    "authored": (after.get("authored_cut") or {}).get("type", "hard") if after.get("cut_decision") else "",
                    "transition_ms": transition.get("duration_ms") or 0,
                    # A J/L-cut's sound across the picture cut, in seconds (0: the assembly's default).
                    "split": cut.get("split") or 0,
                    "transition_reason": transition.get("reason") or "",
                    "revision": scene.get("revision", 0),
                },
            })
        # Between scenes the join belongs to the sequence and is not checked yet.
        if previous_last and shot_nodes:
            edges.append({
                "id": f"next:{previous_scene}-{scene['id']}",
                "type": "scene-order", "source": previous_last, "target": shot_nodes[0], "data": {},
            })
        if shot_nodes:
            previous_last, previous_scene = shot_nodes[-1], scene["id"]

    active = production.get("active_scene") or {}
    return {
        "production": {
            "id": production["id"],
            "title": production["title"],
            "active_scene": active.get("id") if isinstance(active, dict) else "",
            "cast": [{"id": member["id"], "label": member.get("label") or member["id"]}
                     for member in (production.get("cast") or {}).values()],
            "sequences": [
                {"id": item["id"], "label": item.get("label") or item["id"], "scenes": list(item.get("scene_ids") or [])}
                for item in production.get("sequences") or []
                if item["id"] != "unassigned" and item.get("scene_ids")
            ],
        },
        "nodes": nodes,
        "edges": edges,
    }


def load_graph(root) -> dict[str, Any]:
    return production_graph(load_production(root), Path(root))
