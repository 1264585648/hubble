import json

import httpx
import pytest

from hubble.channels.config import load_channel_registry_from_file
from hubble.channels.feishu import FeishuChannelAdapter
from hubble.channels.models import ChannelMessage


@pytest.mark.asyncio
async def test_feishu_channel_sends_interactive_card() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://open.feishu.cn/webhook/test"
        body = json.loads(request.content.decode("utf-8"))
        assert body["msg_type"] == "interactive"
        assert body["card"]["header"]["template"] == "red"
        assert body["card"]["header"]["title"]["content"] == "Critical Alert"
        assert "payment-api" in body["card"]["elements"][0]["text"]["content"]
        return httpx.Response(200, json={"code": 0, "msg": "success", "data": {"message_id": "msg_1"}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    channel = FeishuChannelAdapter(
        name="feishu-sre",
        webhook_url="https://open.feishu.cn/webhook/test",
        http_client=client,
    )

    result = await channel.send(
        ChannelMessage(
            title="Critical Alert",
            body="payment-api error rate is high",
            severity="critical",
            incident_id="inc_1",
            alert_id="alert_1",
        )
    )
    await client.aclose()

    assert result.ok is True
    assert result.channel == "feishu-sre"
    assert result.message_id == "msg_1"


@pytest.mark.asyncio
async def test_feishu_channel_returns_structured_error() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": 19001, "msg": "invalid webhook"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    channel = FeishuChannelAdapter(
        name="feishu-sre",
        webhook_url="https://open.feishu.cn/webhook/test",
        http_client=client,
    )

    result = await channel.send(ChannelMessage(title="Alert", body="body", severity="high"))
    await client.aclose()

    assert result.ok is False
    assert result.channel == "feishu-sre"
    assert "invalid webhook" in (result.error or "")


@pytest.mark.asyncio
async def test_feishu_channel_adds_signature_when_secret_configured() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        assert "timestamp" in body
        assert "sign" in body
        assert body["sign"]
        return httpx.Response(200, json={"code": 0, "msg": "success"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    channel = FeishuChannelAdapter(
        name="feishu-sre",
        webhook_url="https://open.feishu.cn/webhook/test",
        secret="test-secret",
        http_client=client,
    )

    result = await channel.send(ChannelMessage(title="Alert", body="body", severity="medium"))
    await client.aclose()

    assert result.ok is True


def test_channel_config_loads_feishu_when_env_exists(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HUBBLE_FEISHU_WEBHOOK_URL", "https://open.feishu.cn/webhook/test")
    monkeypatch.setenv("HUBBLE_FEISHU_WEBHOOK_SECRET", "test-secret")

    config_file = tmp_path / "hubble.yaml"
    config_file.write_text(
        """
notifiers:
  channels:
    - name: console
      type: console
      enabled: true
    - name: feishu-sre
      type: feishu
      enabled: true
      webhook_url_env: HUBBLE_FEISHU_WEBHOOK_URL
      secret_env: HUBBLE_FEISHU_WEBHOOK_SECRET
      timeout_seconds: 5
""",
        encoding="utf-8",
    )

    registry = load_channel_registry_from_file(config_file)

    assert "console" in registry.list_names()
    assert "feishu-sre" in registry.list_names()


def test_channel_config_skips_feishu_without_webhook_env(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("HUBBLE_FEISHU_WEBHOOK_URL", raising=False)

    config_file = tmp_path / "hubble.yaml"
    config_file.write_text(
        """
notifiers:
  channels:
    - name: feishu-sre
      type: feishu
      enabled: true
      webhook_url_env: HUBBLE_FEISHU_WEBHOOK_URL
""",
        encoding="utf-8",
    )

    registry = load_channel_registry_from_file(config_file)

    assert "console" in registry.list_names()
    assert "feishu-sre" not in registry.list_names()
