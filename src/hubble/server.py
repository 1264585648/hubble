from __future__ import annotations

from typing import Any

import uvicorn
from fastapi import FastAPI

from hubble.core.engine import AlertEngine
from hubble.core.models import AlertAnalysis
from hubble.ingress.base import WebhookNormalizer
from hubble.model.base import EchoModelProvider, ModelRouter
from hubble.notifiers.base import ConsoleNotifier, NotifierRegistry
from hubble.tools.base import ToolRegistry

app = FastAPI(
    title="Hubble Alert Bot",
    description="A pluggable AI alert bot runtime.",
    version="0.1.0",
)


def create_engine() -> AlertEngine:
    model_router = ModelRouter(default_provider=EchoModelProvider())

    tool_registry = ToolRegistry()

    notifier_registry = NotifierRegistry()
    notifier_registry.register(ConsoleNotifier())

    return AlertEngine(
        model_router=model_router,
        tool_registry=tool_registry,
        notifier_registry=notifier_registry,
        default_channels=["console"],
    )


engine = create_engine()


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhook/{source}", response_model=AlertAnalysis)
async def receive_webhook(source: str, payload: dict[str, Any]) -> AlertAnalysis:
    alert = WebhookNormalizer.normalize(source=source, payload=payload)
    return await engine.handle_alert(alert)


def main() -> None:
    uvicorn.run("hubble.server:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
