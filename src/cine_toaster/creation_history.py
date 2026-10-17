"""Read existing reference relationships without inventing revisions or approvals."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def reference_history(references: list[dict], drafts: list[dict], cast: dict, rounds: list[dict] | None = None,
                      storyboards: list[dict] | None = None) -> dict[str, Any]:
    nodes = {ref["id"]: {"id": ref["id"], "title": ref.get("title", ""), "parents": [],
                         "uses": [], "sources": [], "related": [], "selections": [],
                         "review": "not_recorded", "depth": 0, "rounds": [], "corrects": [], "revised_by": []} for ref in references}
    files = {f"references/{ref['id']}/{name}": (ref["id"], digest)
             for ref in references for name, digest in (ref.get("files") or {}).items()}
    for ref in references:
        node = nodes[ref["id"]]
        generation = ref.get("generation") or {}
        actual = {}
        for item in generation.get("references") or []:
            # A basename or coincidentally similar title is never evidence of reuse.
            source = files.get(item.get("file", ""))
            if source:
                actual[source[0]] = "provider_input" if source[1] and item.get("sha256") == source[1] else "provider_input_changed"
        parents = list(dict.fromkeys([*(ref.get("from") or []), *actual]))
        for parent in parents:
            evidence = actual.get(parent, "declared_lineage")
            node["parents"].append({"id": parent, "evidence": evidence})
            if parent in nodes:
                nodes[parent]["uses"].append({"kind": "reference", "id": ref["id"], "title": node["title"], "evidence": evidence})
        composed = generation.get("composed_from") or {}
        node["sources"] = [{"kind": key, "id": composed[key]} for key in ("cast", "style") if composed.get(key)]
        for source in generation.get("creation_inputs") or []:
            if source.get("kind") == "concept":
                node["sources"].append({"kind": "concept", "id": source["id"]})
    for draft in drafts:
        for item in draft["inputs"]:
            if item["kind"] == "reference" and item["id"] in nodes:
                nodes[item["id"]]["uses"].append({"kind": draft["kind"], "id": draft["id"], "title": draft["title"], "evidence": "declared_direction"})
    for board in storyboards or []:
        for item in board["inputs"]:
            if item["id"] in nodes:
                nodes[item["id"]]["uses"].append({"kind": "storyboard", "id": board["id"], "title": board["title"],
                    "scene": board["scene"], "shot": board["shot"], "evidence": "declared_direction"})
    for round_ in rounds or []:
        for item in round_["references"]:
            if item["id"] in nodes:
                nodes[item["id"]]["rounds"].append({"id": round_["id"], "title": round_["title"]})
        for pair in round_["corrections"]:
            if pair["previous"] in nodes and pair["current"] in nodes:
                nodes[pair["previous"]]["revised_by"].append({"id": pair["current"], "round": round_["id"], "reason": round_["rationale"]})
                nodes[pair["current"]]["corrects"].append({"id": pair["previous"], "round": round_["id"], "reason": round_["rationale"]})
    for member in cast.values():
        pools = [("", member.get("references") or [])] + [(name, variant.get("references") or []) for name, variant in member.get("variants", {}).items()]
        for variant, selections in pools:
            for selected in selections:
                source = files.get(selected.get("path", ""))
                if source:
                    nodes[source[0]]["selections"].append({"kind": "cast", "id": member["id"] + ("@" + variant if variant else ""),
                        "role": selected.get("role", "supporting"), "purpose": selected.get("kind", "face")})
    # Shared cast+style means related explorations, NOT successor versions or image inputs.
    for node in nodes.values():
        context = [item for item in node["sources"] if item["kind"] in ("cast", "style")]
        if len(context) == 2:
            node["related"] = [other["id"] for other in nodes.values() if other["id"] != node["id"]
                               and [item for item in other["sources"] if item["kind"] in ("cast", "style")] == context]
    def depth(ref_id: str, trail: set[str]) -> int:
        if ref_id in trail:
            return 0  # malformed old lineage must not make the screen hang
        parents = [item["id"] for item in nodes[ref_id]["parents"] if item["id"] in nodes and item["id"] not in trail]
        return max((1 + depth(parent, trail | {ref_id}) for parent in parents), default=0)
    for ref_id, node in nodes.items():
        node["depth"] = depth(ref_id, set())
    ordered = []
    visited = set()
    def visit(ref_id: str):
        if ref_id in visited:
            return
        visited.add(ref_id); ordered.append(nodes[ref_id])
        for child in nodes[ref_id]["uses"]:
            if child["kind"] == "reference":
                visit(child["id"])
    # Connected source chains first, then independent/text-driven alternatives.
    roots = [node for node in nodes.values() if not any(item["id"] in nodes for item in node["parents"])]
    for node in sorted(roots, key=lambda item: (not bool(item["uses"]), item["id"])):
        visit(node["id"])
    for ref_id in nodes:
        visit(ref_id)
    return {"nodes": ordered, "summary": {
        "retained": len(nodes), "reused": sum(bool(node["uses"]) for node in nodes.values()),
        "provider_input_links": sum(item["evidence"] == "provider_input" for node in nodes.values() for item in node["parents"]),
        "cast_selections": sum(len(node["selections"]) for node in nodes.values()),
        "review": "Reference approval is not recorded by the current reference format. Reuse, cast designation and director observations are distinct from approval.",
    }}
