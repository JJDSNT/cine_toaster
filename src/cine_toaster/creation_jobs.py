"""Exploratory reference generation staged by the existing job runtime."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

import yaml

from .yamlio import safe_load
from .creation import content_digest, load_creation, reference_snapshot
from .errors import ValidationError
from .references import generate_reference, image_providers, load_references, reference_images


def plan_reference(root: Path, params: dict[str, Any]) -> dict[str, Any]:
    title, request = params.get("title"), params.get("request")
    if not isinstance(title, str) or not title.strip() or len(title) > 240:
        raise ValidationError("A reference needs a title of at most 240 characters")
    if not isinstance(request, str) or not request.strip() or len(request) > 20000:
        raise ValidationError("A reference needs a description of at most 20000 characters")
    parents = params.get("parents", [])
    selected = reference_snapshot(root, parents)
    # Retain ancestors so the staging project's reference records remain valid.
    known = {item["id"]: item for item in load_references(root)}
    pending = list(parents)
    closure = []
    while pending:
        ref_id = pending.pop(0)
        if ref_id in closure:
            continue
        closure.append(ref_id)
        pending.extend(known[ref_id].get("from") or [])
        if any(item not in known for item in pending):
            raise ValidationError("A reference ancestor is missing")
    snapshots = reference_snapshot(root, closure)
    concept_id = params.get("concept", "")
    if not isinstance(concept_id, str):
        raise ValidationError("concept must be a saved concept id")
    concept = next((item for item in load_creation(root)["drafts"] if item["id"] == concept_id and item["kind"] == "concept"), None)
    if concept_id and concept is None:
        raise ValidationError("No saved concept with that id")
    inputs = ([{"kind": "concept", "id": concept_id, "sha256": content_digest(concept)}] if concept else []) + selected
    art_id = params.get("art_brief", "")
    art = next((item for item in load_creation(root).get("art_briefs", []) if item["id"] == art_id), None)
    if art_id and not art:
        raise ValidationError("No saved art brief with that id")
    if art:
        inputs.append({"kind": "art_brief", "id": art_id, "sha256": content_digest(art)})
    if "inputs" in params and (params["inputs"] != inputs or params.get("snapshots") != snapshots):
        raise ValidationError("Generation inputs changed; inspect a new plan before retrying")
    prompt = " ".join(((f"Creative concept: {concept['text']}\n\nVisual request: " if concept else "") + request.strip()).split())
    if art:
        prompt = f"Art direction: {art['text']}\nCriteria: {'; '.join(art['criteria'])}\n{prompt}"
    from .providers.codex_image import instruction
    provider_instruction = instruction(prompt, len(reference_images(root, parents)))
    maker = image_providers()["codex-image"]()
    return {"title": title.strip(), "request": request.strip(), "prompt": prompt, "instruction": provider_instruction, "parents": parents,
            "concept": concept_id, "art_brief": art_id, "inputs": inputs, "snapshots": snapshots,
            "provider": "codex-image", "cost": {"kind": "subscription quota", "usd": None},
            "available": bool(getattr(maker, "binary", "")),
            "remedy": "Install Codex and log in; toast doctor reports setup details."}


def validate_reference(root: Path, params: dict[str, Any]) -> dict[str, Any]:
    if params.get("accept_quota") is not True:
        raise ValidationError("Confirm subscription quota use before starting exploratory generation")
    if "inputs" not in params or "snapshots" not in params:
        raise ValidationError("Preview a reference generation plan with pinned inputs before starting")
    plan = plan_reference(root, params)
    if not plan["available"]:
        raise ValidationError(plan["remedy"])
    return {**plan, "accept_quota": True}


def run_reference(context) -> dict[str, Any]:
    params = context.params
    context.progress(0.02, "Checking and staging the selected reference versions")
    current = plan_reference(context.project_root, params)
    if current["inputs"] != params["inputs"]:
        raise ValidationError("Selected inputs changed before the job started")
    sandbox = context.staging / "reference-work"
    sandbox.mkdir()
    for snapshot in params["snapshots"]:
        original = context.project_root / "references" / snapshot["id"]
        target = sandbox / "references" / snapshot["id"]
        target.mkdir(parents=True)
        shutil.copy2(original / "reference.yaml", target / "reference.yaml")
        for name in snapshot["files"]:
            (target / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original / name, target / name)
    if reference_snapshot(sandbox, [item["id"] for item in params["snapshots"]]) != params["snapshots"]:
        raise ValidationError("Reference contents changed during staging")

    def runner(argv: list[str], cwd: Path, timeout: int) -> tuple[int, str, str]:
        # Include the owned staging directory in the command for orphan reconciliation.
        if len(argv) > 1 and argv[1] == "exec":
            argv = [*argv[:2], "--cd", str(context.staging), *argv[2:]]
        log = context.staging / f"codex-{uuid.uuid4().hex}"
        with log.with_suffix(".out").open("w+") as out, log.with_suffix(".err").open("w+") as err:
            process = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL, stdout=out, stderr=err, start_new_session=True)
            context._manager.store.update(context.job_id, process_pid=process.pid)
            deadline = time.monotonic() + timeout
            try:
                while process.poll() is None:
                    context.check()
                    if time.monotonic() > deadline:
                        raise ValidationError(f"Image generation exceeded {timeout} seconds")
                    time.sleep(0.2)
            finally:
                if process.poll() is None:
                    import signal
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                context._manager.store.update(context.job_id, process_pid=None)
            out.seek(0); err.seek(0)
            return process.returncode, out.read(), err.read()

    context.progress(0.1, "Generating one exploratory image; consumes subscription quota")
    made = generate_reference(sandbox, title=params["title"], prompt=params["prompt"], parents=params["parents"],
                              name="exploration-" + context.job_id, requested_by="Creation / Inception", runner=runner)
    context.check()
    record_path = made / "reference.yaml"
    record = safe_load(record_path.read_text(encoding="utf-8"))
    record["generation"]["creation_inputs"] = params["inputs"]
    record_path.write_text(yaml.safe_dump(record, allow_unicode=True, sort_keys=False), encoding="utf-8")
    context.progress(0.98, "Reference ready to inspect and adopt; earlier images are preserved")
    return {"files": [{"staged": str(path.relative_to(context.staging)),
                        "destination": f"references/{made.name}/{path.name}"} for path in sorted(made.iterdir()) if path.is_file()],
            "summary": {"reference": made.name, "title": params["title"], "inputs": params["inputs"], "cost": params["cost"]}}
