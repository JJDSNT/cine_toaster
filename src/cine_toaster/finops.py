"""What the providers billed, set against what Cine Toaster ran (FinOps step 5, CT-0061).

Reconcile, do not duplicate (`docs/finops.md`): the spend ledger keeps what each
job measured; the provider keeps what it billed. Runpod bills an endpoint per
hour, never a job, so a job's provider-authoritative cost is an **allocation**:
the endpoint's billed hour is shared among the known jobs that finished in it
(the ledger's, and with `--project` the film's own job records, whoever ran them), in proportion to their billed seconds (queue plus execution). Idle
workers and cold starts in that hour fall on those jobs -- they are what running
them cost. An hour with no known job in it is **unattributed**: spend nothing
here can account for, never spread over the film.

Each figure says its source: `measured` (the job's own seconds at the assumed
rate), `allocated` (a share of a billed hour), `unattributed`.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def film_jobs(root: Path, rates: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """The provider jobs a film keeps beside its takes (`<take>.job.json`), whoever ran them.

    SINGULAR's own tools wrote these too, before Cine Toaster: they are the
    film's jobs, so their billed hours are the film's. The record says when it
    finished (`finished_at`, since CT-0061); an older one only has its file's
    time, and the row says so (`at_source: file_time`).
    """

    from .costs import _rate
    from .providers.runpod import job_seconds

    jobs, seen = [], set()
    # Archived takes included: they were paid for. A copy of a record (same job id) counts once.
    for path in sorted(root.rglob("*.job.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not record.get("id") or not record.get("endpoint") or record["id"] in seen:
            continue
        seen.add(record["id"])
        seconds = job_seconds(record)
        rate, _ = _rate(str(record["endpoint"]), rates or {})
        finished = record.get("finished_at")
        at = finished or datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(timespec="seconds")
        jobs.append({"remote": record["id"], "endpoint": record["endpoint"], "seconds": round(seconds, 3),
                     "usd": round(seconds * rate / 3600, 4), "at": at,
                     "at_source": "recorded" if finished else "file_time",
                     "what": path.relative_to(root).as_posix().removesuffix(".job.json")})
    return jobs


def merge(ledger: list[dict[str, Any]], film: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The ledger's entries, completed by the film's records of the same job; then the film's other jobs."""

    by_remote = {job["remote"]: job for job in film}
    out = []
    for entry in ledger:
        known = by_remote.pop(entry.get("remote"), None)
        if known and not entry.get("endpoint"):
            entry = {**entry, "endpoint": known["endpoint"], "seconds": known["seconds"]}
        out.append(entry)
    return out + list(by_remote.values())


def _instant(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def reconcile(billing: dict[str, Any], entries: list[dict[str, Any]], fetched_at: str = "") -> dict[str, Any]:
    """Allocate each billed bucket among the ledger's jobs in it; report what stays unattributed."""

    start, end = _instant(billing["start"]), _instant(billing["end"])
    jobs = []
    for entry in entries:
        if not entry.get("remote"):
            continue
        at = _instant(entry["at"])
        if start <= at < end:
            jobs.append({**entry, "_at": at})
    allocated: dict[str, float] = {}
    matched: set[str] = set()
    unattributed = []
    billed = 0.0
    for observation in billing["observations"]:
        billed += observation["usd"]
        low, high = _instant(observation["start"]), _instant(observation["end"])
        inside = [job for job in jobs if job.get("endpoint") == observation["resource"] and low <= job["_at"] < high]
        if not inside:
            if observation["usd"] > 0:
                unattributed.append({key: observation[key] for key in ("resource", "start", "end", "usd")})
            continue
        seconds = sum(float(job.get("seconds") or 0) for job in inside)
        for job in inside:
            share = (float(job.get("seconds") or 0) / seconds) if seconds else 1 / len(inside)
            allocated[job["remote"]] = allocated.get(job["remote"], 0.0) + observation["usd"] * share
            matched.add(job["remote"])
    rows = []
    for job in jobs:
        measured = float(job.get("usd") or 0)
        row = {"remote": job["remote"], "what": job.get("what", ""), "job": job.get("job", ""), "at": job["at"],
               "at_source": job.get("at_source", "recorded"),
               "endpoint": job.get("endpoint", ""), "seconds": job.get("seconds"), "measured_usd": round(measured, 4)}
        if job["remote"] in matched:
            row.update(source="allocated", allocated_usd=round(allocated[job["remote"]], 4),
                       overhead_usd=round(allocated[job["remote"]] - measured, 4))
        else:
            # No billed bucket of its endpoint holds it: the endpoint is unknown (an entry from before
            # CT-0061), or the provider has not billed that hour yet.
            row.update(source="unobserved", reason="no endpoint recorded" if not job.get("endpoint")
                       else "no billed hour of its endpoint holds it")
        rows.append(row)
    attributed = sum(allocated.values())
    unattributed_usd = sum(item["usd"] for item in unattributed)
    return {
        "provider": billing["provider"], "start": billing["start"], "end": billing["end"],
        "bucket": billing["bucket"], "fetched_at": fetched_at,
        "billed_usd": round(billed, 4), "attributed_usd": round(attributed, 4),
        "unattributed_usd": round(unattributed_usd, 4),
        "reconciled_share": round(attributed / billed, 4) if billed else None,
        "jobs": rows, "unobserved_jobs": sum(1 for row in rows if row["source"] == "unobserved"),
        "unattributed": unattributed,
    }


def render_text(report: dict[str, Any]) -> str:
    share = report["reconciled_share"]
    lines = [
        f"{report['provider']} billing {report['start']} to {report['end']} (by {report['bucket']}"
        + (f", read {report['fetched_at']}" if report["fetched_at"] else "") + ")",
        f"  billed US$ {report['billed_usd']:.2f}; known jobs US$ {report['attributed_usd']:.2f}"
        + (f" ({share:.0%})" if share is not None else "")
        + f"; unattributed US$ {report['unattributed_usd']:.2f} (hours with no known job)",
    ]
    for row in report["jobs"]:
        if row["source"] == "allocated":
            lines.append(f"  {row['at'][:16]} {row['what']}: measured US$ {row['measured_usd']:.3f}, "
                         f"billed share US$ {row['allocated_usd']:.3f} (overhead {row['overhead_usd']:+.3f})")
        else:
            lines.append(f"  {row['at'][:16]} {row['what']}: measured US$ {row['measured_usd']:.3f}, "
                         f"unobserved -- {row['reason']}")
    if report["unobserved_jobs"]:
        lines.append(f"  {report['unobserved_jobs']} job(s) not reconciled: their cost stays the measured estimate.")
    return "\n".join(lines)
