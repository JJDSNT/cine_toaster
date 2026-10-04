"""Runpod's billing, read only: what the provider says was spent (FinOps step 4, CT-0061).

Verified on 2026-10-04 (docs/finops.md): serverless spend is billed per
endpoint per time bucket, with no line per job and no usage seconds. This
adapter only reads it, and turns each record into a provider-neutral cost
observation; nothing here creates, changes or stops anything on the account.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any, Callable

from .runpod import REQUEST_TIMEOUT, _api_key

BILLING_BASE = "https://api.runpod.io/v2"  # the REST API v2 (beta): not the job plane, api.runpod.ai
PROVIDER = "runpod"
USER_AGENT = "cine-toaster"

Fetch = Callable[[str, dict[str, str]], dict[str, Any]]


def _get(path: str, query: dict[str, str]) -> dict[str, Any]:
    http = urllib.request.Request(f"{BILLING_BASE}{path}?{urllib.parse.urlencode(query)}", method="GET")
    http.add_header("Authorization", f"Bearer {_api_key()}")
    # Cloudflare in front of the REST API refuses Python's default agent (error 1010, 403).
    http.add_header("User-Agent", USER_AGENT)
    with urllib.request.urlopen(http, timeout=REQUEST_TIMEOUT) as response:
        return json.loads(response.read())


def serverless_observations(start: str, end: str, bucket: str = "hour",
                            fetch: Fetch | None = None) -> dict[str, Any]:
    """Serverless spend between two RFC 3339 instants, one observation per endpoint per bucket."""

    payload = (fetch or _get)("/billing/serverless", {"startTime": start, "endTime": end, "bucketSize": bucket})
    observations = [
        {"provider": PROVIDER, "resource": str(record.get("serverlessId") or ""),
         "start": record["startTime"], "end": record["endTime"], "usd": float(record.get("totalAmount") or 0),
         "components": {key.removesuffix("Amount"): float(record.get(key) or 0)
                        for key in ("gpuAmount", "cpuAmount", "diskAmount", "feeAmount")}}
        for record in payload.get("records") or []
    ]
    query = (payload.get("metadata") or {}).get("query") or {}
    return {"provider": PROVIDER, "start": query.get("startTime", start), "end": query.get("endTime", end),
            "bucket": query.get("bucketSize", bucket), "observations": observations}
