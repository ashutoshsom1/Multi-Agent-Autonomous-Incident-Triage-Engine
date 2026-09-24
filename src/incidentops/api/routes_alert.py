"""FastAPI routes for Alert Webhook ingestion (Prometheus, Datadog, PagerDuty)."""

from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Request
from incidentops.models.alert import AlertPayload
from incidentops.graph.workflow import workflow_manager

router = APIRouter(prefix="/api/v1/alerts", tags=["Alert Webhooks"])


@router.post("/webhook")
async def ingest_alert_webhook(request: Request) -> Dict[str, Any]:
    """Ingest alert webhook from Prometheus Alertmanager, Datadog, or PagerDuty.

    Normalizes payload into AlertPayload and initiates autonomous multi-agent triage.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Detect provider format
    if "alerts" in body:
        alert = AlertPayload.from_prometheus_alertmanager(body)
    elif "event_type" in body or "tags" in body:
        alert = AlertPayload.from_datadog(body)
    elif "event" in body and "data" in body.get("event", {}):
        alert = AlertPayload.from_pagerduty(body)
    elif "service_name" in body:
        alert = AlertPayload.model_validate(body)
    else:
        # Fallback generic parsing
        alert = AlertPayload(
            alert_id=f"alert-{int(request.headers.get('date', 0) or 1)}",
            service_name=body.get("service", body.get("app", "unknown-service")),
            severity=body.get("severity", "HIGH"),
            description=str(body.get("description", body.get("message", "Generic incident alert"))),
            labels=body.get("labels", body)
        )

    # Trigger autonomous triage
    result = await workflow_manager.start_triage(alert)
    thread_id = result["thread_id"]
    state = result["state"]

    final_rca = state.get("final_rca", {})
    slack_card = final_rca.get("slack_block_kit_card", {})

    return {
        "status": "INCIDENT_TRIAGED_AWAITING_APPROVAL",
        "thread_id": thread_id,
        "service_name": alert.service_name,
        "severity": alert.severity,
        "root_cause_analysis": final_rca.get("root_cause_analysis"),
        "proposed_remediation": final_rca.get("proposed_remediation"),
        "slack_card": slack_card
    }
