from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from hubble.channels.base import ChannelRegistry, ConsoleChannelAdapter
from hubble.channels.feishu import FeishuChannelAdapter


def load_channel_registry_from_file(path: str | Path) -> ChannelRegistry:
    registry = ChannelRegistry()
    registry.register(ConsoleChannelAdapter())

    config_path = Path(path)
    if not config_path.exists():
        return registry

    with config_path.open("r", encoding="utf-8") as file:
        raw = yaml.safe_load(file) or {}

    channels = _get_nested(raw, ["notifiers", "channels"], default=[])
    if not isinstance(channels, list):
        return registry

    for channel in channels:
        if not isinstance(channel, dict) or not channel.get("enabled"):
            continue
        if channel.get("type") == "feishu":
            adapter = _build_feishu_channel(channel)
            if adapter:
                _safe_register(registry, adapter)

    return registry


def _build_feishu_channel(config: dict[str, Any]) -> FeishuChannelAdapter | None:
    webhook_url = os.getenv(str(config.get("webhook_url_env") or ""))
    if not webhook_url:
        return None

    secret_env = config.get("secret_env")
    secret = os.getenv(str(secret_env)) if secret_env else None

    return FeishuChannelAdapter(
        name=str(config.get("name") or "feishu"),
        webhook_url=webhook_url,
        secret=secret,
        timeout_seconds=float(config.get("timeout_seconds") or 10.0),
    )


def _safe_register(registry: ChannelRegistry, adapter: FeishuChannelAdapter) -> None:
    if adapter.name in registry.list_names():
        return
    registry.register(adapter)


def _get_nested(data: dict[str, Any], keys: list[str], *, default: Any) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return default if current is None else current
