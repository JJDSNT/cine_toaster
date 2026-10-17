"""The model catalogue and role bindings (ADR 0034).

The catalogue describes what adapters carry and what known models are good
at; `toast doctor` shows it beside the roles. It never picks a model: the
production uses the model the person supplied, and a role uses another only
when the person bound it to one in their own file:

    # $XDG_CONFIG_HOME/cine-toaster/models.yaml
    models:
      my-model: {strengths: [visual_critique], source: my own trials}
    roles:
      visual_prevalidation: claude-api:claude-opus-5-5   # adapter[:model]

A binding names an adapter the person chose; nothing scans for installed
executables or credentials.
"""

from __future__ import annotations

import os
from importlib import resources
from pathlib import Path
from typing import Any, Callable

import yaml

from ..errors import ValidationError
from .models import ADAPTERS, Model, ModelUnavailable
from .roles import ROLES


def user_file() -> Path:
    configured = os.environ.get("XDG_CONFIG_HOME")
    base = Path(configured).expanduser() if configured else Path.home() / ".config"
    return base / "cine-toaster" / "models.yaml"


def _read(text: str, where: str) -> dict[str, Any]:
    try:
        value = yaml.safe_load(text) or {}
    except yaml.YAMLError as error:
        raise ValidationError(f"{where} is not valid YAML: {error}") from error
    if not isinstance(value, dict):
        raise ValidationError(f"{where} must be a mapping")
    return value


def load(path: Path | None = None) -> dict[str, Any]:
    """The built-in catalogue with the person's file read on top of it, entry by entry."""

    catalogue = _read(resources.files(__package__).joinpath("model_catalog.yaml").read_text("utf-8"),
                      "the built-in model catalogue")
    own = path if path is not None else user_file()
    mine = _read(own.read_text("utf-8"), str(own)) if own.is_file() else {}
    for section in ("vocabulary", "adapters", "models"):
        merged = dict(catalogue.get(section) or {})
        for key, entry in (mine.get(section) or {}).items():
            merged[key] = {**merged.get(key, {}), **entry} if isinstance(entry, dict) else entry
        catalogue[section] = merged
    catalogue["roles"] = dict(mine.get("roles") or {})
    unknown = sorted(set(catalogue["roles"]) - set(ROLES))
    if unknown:
        raise ValidationError(f"{own} binds unknown roles: {', '.join(unknown)}", allowed=sorted(ROLES))
    return catalogue


def adapter_for(binding: str) -> Model:
    """`adapter` or `adapter:model`, as the person wrote it."""

    kind, _, model = binding.strip().partition(":")
    if kind not in ADAPTERS:
        raise ModelUnavailable(f"Unknown model adapter {kind!r} in a role binding; available: {', '.join(ADAPTERS)}")
    return ADAPTERS[kind](model=model) if model else ADAPTERS[kind]()


def role_models(default: Model, catalogue: dict[str, Any] | None = None) -> Callable[[str], Model]:
    """Which model serves each role: the person's binding, else the one model they supplied."""

    bindings = (catalogue if catalogue is not None else load())["roles"]
    bound = {role: adapter_for(binding) for role, binding in bindings.items()}
    return lambda role: bound.get(role, default)


def describe(model: Any, catalogue: dict[str, Any]) -> dict[str, Any]:
    """What the catalogue says of a configured model: its adapter entry and, when named, its model entry."""

    name = getattr(model, "name", "")
    model_id = getattr(model, "model", "") or ""
    return {"adapter": name, "model": model_id or None,
            "adapter_entry": catalogue["adapters"].get(name),
            "model_entry": catalogue["models"].get(model_id) if model_id else None}
