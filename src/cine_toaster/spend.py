"""What paid generation may spend, and what it has spent.

Generation costs money on someone else's account. Nothing is generated unless a
limit has been set, and nothing is started whose estimate would take the total
past it. The ledger is application operational state, beside the jobs
(`$XDG_STATE_HOME/cine-toaster/spend.json`): deleting it forgets history, and
refuses generation until a limit is set again.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .errors import CineToasterError
from .jobs import state_root

_LOCK = threading.Lock()


class BudgetExceeded(CineToasterError):
    code = "budget_exceeded"
    http_status = 402


def ledger_path() -> Path:
    return state_root() / "spend.json"


def load() -> dict[str, Any]:
    path = ledger_path()
    if not path.is_file():
        return {"limit_usd": 0.0, "entries": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _write(data: dict[str, Any]) -> None:
    path = ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def spent(data: dict[str, Any] | None = None) -> float:
    data = data or load()
    return round(sum(float(entry.get("usd") or 0) for entry in data["entries"]), 4)


def set_limit(usd: float) -> dict[str, Any]:
    with _LOCK:
        data = load()
        data["limit_usd"] = round(float(usd), 2)
        _write(data)
        return data


def check(estimate_usd: float, what: str) -> None:
    """Refuse a generation the budget cannot pay for, before anything is sent."""

    data = load()
    limit = float(data.get("limit_usd") or 0)
    if limit <= 0:
        raise BudgetExceeded(f"No generation budget is set, so {what} was not started. "
                             f"Set one with: toast budget set <usd>")
    if spent(data) + estimate_usd > limit + 1e-9:
        raise BudgetExceeded(
            f"{what} is estimated at US$ {estimate_usd:.2f}; US$ {spent(data):.2f} of US$ {limit:.2f} is spent.",
            estimate_usd=estimate_usd, spent_usd=spent(data), limit_usd=limit,
        )


def record(usd: float, what: str, **details: Any) -> None:
    with _LOCK:
        data = load()
        data["entries"].append({"at": datetime.now(UTC).isoformat(), "usd": round(float(usd), 4), "what": what, **details})
        _write(data)
