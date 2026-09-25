"""IncidentOps workflow execution controller.

Manages life-cycle of incident triage runs, thread state checkpoints,
and Human-In-The-Loop approvals with telemetry and audit tracking.
"""

import time
import uuid
from typing import Any, Dict, Optional

from incidentops.graph.state_graph import build_incidentops_graph
from incidentops.models.alert import AlertPayload
from incidentops.telemetry import logger, metrics


class IncidentOpsWorkflowManager:
    """Manages active incident triage StateGraph instances with persistence and metrics."""

    def __init__(self, checkpointer: Optional[Any] = None):
        self.graph = build_incidentops_graph(checkpointer=checkpointer)

    async def start_triage(
        self,
        alert: AlertPayload,
        thread_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Trigger autonomous incident triage for an incoming alert.

        Executes up to the Human Approval Gate interrupt.
        """
        start_time = time.time()
        thread_id = thread_id or f"inc-{uuid.uuid4().hex[:8]}"
        config = {"configurable": {"thread_id": thread_id}}

        logger.info(
            f"Initiating autonomous triage for alert [{alert.alert_id}] on {alert.service_name}",
            extra={"incident_id": thread_id, "worker": "workflow"}
        )

        initial_state = {
            "alert_raw": alert.model_dump(),
            "iteration_count": 0,
            "thread_id": thread_id,
            "execution_logs": [f"Incident triage initiated for {alert.service_name} [{alert.severity}]"]
        }

        try:
            result_state = await self.graph.ainvoke(initial_state, config=config)
            duration = time.time() - start_time
            metrics.record_triage_duration(duration)
            metrics.record_incident(alert.severity, "AWAITING_APPROVAL")
            logger.info(
                f"Triage completed in {duration:.2f}s. Halted at Human Approval Gate.",
                extra={"incident_id": thread_id, "worker": "workflow", "duration_ms": duration * 1000}
            )
            return {
                "thread_id": thread_id,
                "status": "HALTED_AWAITING_HUMAN_APPROVAL",
                "state": result_state,
                "duration_seconds": round(duration, 2)
            }
        except Exception as e:
            duration = time.time() - start_time
            metrics.record_incident(alert.severity, "TRIAGE_ERROR")
            logger.error(
                f"Autonomous triage failed for {alert.service_name}: {e}",
                exc_info=True,
                extra={"incident_id": thread_id, "worker": "workflow"}
            )
            raise e

    async def resume_with_approval(
        self,
        thread_id: str,
        approved: bool,
        signature: str = "slack-hmac-verified"
    ) -> Dict[str, Any]:
        """Resume graph execution following human approval or rejection."""
        config = {"configurable": {"thread_id": thread_id}}
        logger.info(
            f"Resuming incident {thread_id} with human authorization: approved={approved}",
            extra={"incident_id": thread_id, "worker": "workflow"}
        )

        # Update state before approval gate
        self.graph.update_state(
            config,
            {
                "human_approved": approved,
                "approval_signature": signature
            }
        )

        # Resume execution through approval_gate -> remediation_executor -> END
        final_state = await self.graph.ainvoke(None, config=config)
        status = final_state.get("remediation_status", "COMPLETED")
        logger.info(
            f"Remediation lifecycle completed for {thread_id}: status={status}",
            extra={"incident_id": thread_id, "worker": "workflow"}
        )
        return {
            "thread_id": thread_id,
            "status": status,
            "state": final_state
        }

    def get_state(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve current snapshot state for an incident."""
        config = {"configurable": {"thread_id": thread_id}}
        snapshot = self.graph.get_state(config)
        if snapshot and snapshot.values:
            return {
                "thread_id": thread_id,
                "next": snapshot.next,
                "values": snapshot.values
            }
        return None


# Global singleton workflow engine
workflow_manager = IncidentOpsWorkflowManager()
