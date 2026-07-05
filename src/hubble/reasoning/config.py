from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from hubble.reasoning.service import OpenAICompatibleReasoningService, ReasoningService


def load_reasoning_service_from_file(path: str | Path) -> ReasoningService | OpenAICompatibleReasoningService:
    """Load the configured reasoning service.

    If OpenAI-compatible provider is disabled or required environment variables are missing,
    return the Echo fallback service.
    """

    config_path = Path(path)
    if not config_path.exists():
        return ReasoningService()

    with config_path.open("r", encoding="utf-8") as file:
        raw = yaml.safe_load(file) or {}

    providers = _get_nested(raw, ["model", "providers"], default=[])
    if not isinstance(providers, list):
        return ReasoningService()

    for provider in providers:
        if not isinstance(provider, dict):
            continue
        if provider.get("type") != "openai_compatible" or not provider.get("enabled"):
            continue

        base_url = os.getenv(str(provider.get("base_url_env") or ""))
        api_key = os.getenv(str(provider.get("api_key_env") or ""))
        model = os.getenv(str(provider.get("model_env") or ""))
        timeout_seconds = float(provider.get("timeout_seconds") or 20.0)

        if not base_url or not api_key or not model:
            return ReasoningService()

        return OpenAICompatibleReasoningService(
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout_seconds=timeout_seconds,
            fallback=ReasoningService(),
        )

    return ReasoningService()


def _get_nested(data: dict[str, Any], keys: list[str], *, default: Any) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return default if current is None else current
