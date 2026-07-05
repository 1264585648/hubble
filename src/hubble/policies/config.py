from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from hubble.policies.models import PolicyRule


def load_policy_rules_from_file(path: str | Path) -> list[PolicyRule]:
    """Load policy rules from a Hubble YAML config file.

    Expected structure:

    policies:
      rules:
        - name: payment-critical
          match:
            labels.service: payment-api
            severity: critical
          channels: [console]
    """

    config_path = Path(path)
    if not config_path.exists():
        return []

    with config_path.open("r", encoding="utf-8") as file:
        raw = yaml.safe_load(file) or {}

    rules = _get_nested(raw, ["policies", "rules"], default=[])
    if not isinstance(rules, list):
        return []

    return [PolicyRule(**item) for item in rules if isinstance(item, dict)]


def _get_nested(data: dict[str, Any], keys: list[str], *, default: Any) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return default if current is None else current
