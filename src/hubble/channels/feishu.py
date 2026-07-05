from __future__ import annotations

import base64
import hashlib
import hmac
import time
from typing import Any

import httpx

from hubble.channels.base import ChannelAdapter
from hubble.channels.models import ChannelMessage, ChannelSendResult


class FeishuChannelAdapter(ChannelAdapter):
    """Feishu custom bot webhook channel.

    This adapter only implements outbound notification. Conversation/event subscription
    belongs to a later Feishu listener adapter.
    """

    def __init__(
        self,
        *,
        name: str,
        webhook_url: str,
        secret: str | None = None,
        timeout_seconds: float = 10.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.name = name
        self.webhook_url = webhook_url
        self.secret = secret
        self.timeout_seconds = timeout_seconds
        self.http_client = http_client

    async def send(self, message: ChannelMessage) -> ChannelSendResult:
        payload = _build_feishu_payload(message)
        if self.secret:
            timestamp = str(int(time.time()))
            payload["timestamp"] = timestamp
            payload["sign"] = _sign(timestamp, self.secret)

        try:
            response_json = await self._post(payload)
            code = response_json.get("code", response_json.get("StatusCode", 0))
            ok = code in {0, "0"}
            return ChannelSendResult(
                ok=ok,
                channel=self.name,
                message_id=_extract_message_id(response_json),
                thread_id=message.thread_id,
                error=None if ok else str(response_json.get("msg") or response_json),
                metadata={"response": response_json},
            )
        except Exception as exc:  # noqa: BLE001 - channel boundary must return structured error
            return ChannelSendResult(
                ok=False,
                channel=self.name,
                thread_id=message.thread_id,
                error=f"{type(exc).__name__}: {exc}",
            )

    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.http_client:
            response = await self.http_client.post(self.webhook_url, json=payload)
        else:
            timeout = httpx.Timeout(self.timeout_seconds)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(self.webhook_url, json=payload)

        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("Feishu webhook response must be a JSON object")
        return data


def _build_feishu_payload(message: ChannelMessage) -> dict[str, Any]:
    content = f"**{message.title}**\n\n{message.body}"
    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": _severity_template(message.severity),
                "title": {"tag": "plain_text", "content": message.title},
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": content,
                    },
                }
            ],
        },
    }


def _severity_template(severity: str) -> str:
    return {
        "critical": "red",
        "high": "red",
        "medium": "orange",
        "low": "blue",
        "info": "green",
    }.get(severity, "grey")


def _sign(timestamp: str, secret: str) -> str:
    string_to_sign = f"{timestamp}\n{secret}".encode("utf-8")
    digest = hmac.new(string_to_sign, b"", digestmod=hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def _extract_message_id(response_json: dict[str, Any]) -> str | None:
    data = response_json.get("data")
    if isinstance(data, dict):
        message_id = data.get("message_id") or data.get("messageId")
        return str(message_id) if message_id else None
    return None
