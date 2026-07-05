from __future__ import annotations

from typing import Any

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

from hubble.alerts.models import Alert
from hubble.events.models import EventEnvelope
from hubble.incidents.models import Incident
from hubble.reasoning.models import Analysis
from hubble.runtime import HubbleRuntime

app = FastAPI(
    title="Hubble Alert Bot",
    description="A pluggable AI-native AlertOps runtime.",
    version="0.1.0",
)

runtime = HubbleRuntime()


class WebhookResponse(BaseModel):
    event: EventEnvelope
    alert: Alert
    incident: Incident
    analysis: Analysis
    duplicate: bool = False


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhook/{source}", response_model=WebhookResponse)
async def receive_webhook(source: str, payload: dict[str, Any]) -> WebhookResponse:
    result = await runtime.ingest_webhook(source, payload)
    return WebhookResponse(
        event=result.event,
        alert=result.alert,
        incident=result.incident,
        analysis=result.analysis,
        duplicate=result.duplicate,
    )


@app.get("/alerts", response_model=list[Alert])
async def list_alerts() -> list[Alert]:
    return runtime.alert_lifecycle.list_alerts()


@app.get("/incidents", response_model=list[Incident])
async def list_incidents() -> list[Incident]:
    return runtime.incident_lifecycle.list_incidents()


def main() -> None:
    uvicorn.run("hubble.server:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
