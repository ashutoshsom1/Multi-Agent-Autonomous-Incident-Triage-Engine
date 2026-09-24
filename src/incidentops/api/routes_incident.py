"""Incident querying, direct approval, and scenario simulation endpoints."""

from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from incidentops.models.alert import AlertPayload
from incidentops.graph.workflow import workflow_manager

router = APIRouter(prefix="/api/v1/incidents", tags=["Incidents & Simulation"])


class ManualApprovalRequest(BaseModel):
    approved: bool = Field(description="Whether the remediation is approved")
    signature: str = Field(default="api-bearer-authorized", description="Signature or token")
    notes: Optional[str] = Field(default="", description="Operator approval notes")


class SimulationRequest(BaseModel):
    scenario: str = Field(
        default="db_pool_exhaustion",
        description="Scenario to simulate: db_pool_exhaustion | oom_killed"
    )


@router.get("/{thread_id}")
async def get_incident_status(thread_id: str) -> Dict[str, Any]:
    """Retrieve full live snapshot and telemetry evidence for an incident."""
    snapshot = workflow_manager.get_state(thread_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"Incident {thread_id} not found")
    return snapshot


@router.post("/{thread_id}/approval")
async def approve_incident_remediation(
    thread_id: str,
    payload: ManualApprovalRequest
) -> Dict[str, Any]:
    """Direct API endpoint for human approval (used by CLI, Dashboard, or CI/CD)."""
    snapshot = workflow_manager.get_state(thread_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"Incident {thread_id} not found")

    result = await workflow_manager.resume_with_approval(
        thread_id=thread_id,
        approved=payload.approved,
        signature=payload.signature
    )
    return result


@router.post("/simulate")
async def simulate_incident(req: SimulationRequest) -> Dict[str, Any]:
    """Simulate a realistic enterprise incident to test autonomous triage and HITL gate."""
    if req.scenario == "oom_killed":
        alert = AlertPayload(
            alert_id="prom-alert-oom-payment-gw",
            service_name="payment-gateway",
            environment="production",
            severity="CRITICAL",
            description="KubePodCrashLooping: container_memory_working_set_bytes exceeded 2.0GiB cgroup quota",
            labels={
                "alertname": "PodOOMKilled",
                "namespace": "production",
                "container": "payment-gateway",
                "cluster": "prod-us-east-1"
            }
        )
    else:
        # Default: DB connection pool exhaustion
        alert = AlertPayload(
            alert_id="prom-alert-dbpool-order-api",
            service_name="order-service-api",
            environment="production",
            severity="CRITICAL",
            description="HighHttp5xxErrorRate: 450 err/sec on /v2/orders/checkout with connection pool timeout",
            labels={
                "alertname": "ConnectionPoolExhausted",
                "namespace": "production",
                "container": "order-api",
                "cluster": "prod-us-east-1"
            }
        )

    result = await workflow_manager.start_triage(alert)
    thread_id = result["thread_id"]
    state = result["state"]

    return {
        "message": f"Simulated incident '{req.scenario}' triaged successfully.",
        "thread_id": thread_id,
        "service_name": alert.service_name,
        "severity": alert.severity,
        "root_cause_analysis": state.get("final_rca", {}).get("root_cause_analysis"),
        "proposed_remediation": state.get("final_rca", {}).get("proposed_remediation"),
        "slack_block_kit_card": state.get("final_rca", {}).get("slack_block_kit_card"),
        "telemetry": {
            "logs": state.get("log_evidence"),
            "metrics": state.get("metrics_evidence"),
            "code": state.get("code_evidence")
        }
    }
