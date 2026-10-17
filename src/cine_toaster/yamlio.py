"""One YAML reader for production records: safe, and libyaml's C parser when installed.

PyYAML's pure-Python safe loader was most of a large production's load time
(Singular's location files alone took seconds). The C loader builds the same
safe types; `project.py` already read its main files with it.
"""
from __future__ import annotations

from typing import IO, Any

import yaml

SAFE_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


def safe_load(source: str | bytes | IO) -> Any:
    return yaml.load(source, Loader=SAFE_LOADER)  # noqa: S506 -- a safe loader, C or Python
