"""What a production's generations cost, estimated from the providers' own job records.

A take made by a RunPod endpoint carries the platform's record beside it
(`<take>.job.json`), and a slice of a block carries its block's, shared between
the shots of the block. The time is the platform's; the price per hour is not
in the record, so it comes from the production (`generation_rates:
{<endpoint>: <usd per hour>}`) or, failing that, from the provider's own
assumed rate, and the report says which.
"""

from __future__ import annotations

from typing import Any

from .providers.ltx import HOURLY_RATE_USD as LTX_ASSUMED_RATE
from .providers.runpod import job_seconds


def _rate(endpoint: str, rates: dict[str, Any]) -> tuple[float, str]:
    if endpoint in rates:
        return float(rates[endpoint]), "declared"
    return LTX_ASSUMED_RATE, "assumed"


def production_costs(production: dict[str, Any], rates: dict[str, Any] | None = None) -> dict[str, Any]:
    """Generation time and estimated cost, per scene and in total."""

    rates = rates or {}
    scenes, seen_jobs = [], set()
    total_seconds = total_cost = 0.0
    assumed = False
    for scene in production["scenes"]:
        seconds = cost = 0.0
        takes = 0
        for shot in scene["shots"]:
            for take in shot.get("takes") or []:
                provenance = take.get("provenance") or {}
                record = provenance.get("job") or provenance.get("generation") or {}
                job_id = record.get("id")
                if not job_id or job_id in seen_jobs:
                    continue  # a block's generation is counted once, not per slice
                seen_jobs.add(job_id)
                used = job_seconds(record)
                rate, source = _rate(str(record.get("endpoint") or ""), rates)
                assumed = assumed or source == "assumed"
                seconds += used
                cost += used * rate / 3600
                takes += 1
        scenes.append({"scene": scene["id"], "jobs": takes, "seconds": round(seconds, 1), "usd": round(cost, 2)})
        total_seconds += seconds
        total_cost += cost
    return {
        "scenes": scenes,
        "seconds": round(total_seconds, 1),
        "usd": round(total_cost, 2),
        "rate": "assumed" if assumed else "declared",
        "assumed_rate_usd_per_hour": LTX_ASSUMED_RATE,
    }
