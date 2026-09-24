"""IncidentOps workflow execution controller.

Manages life-cycle of incident triage runs, thread state checkpoints,
and Human-In-The-Loop approvals.
"""

import uuid
from typing import Any, Dict, Optional

from incidentops.graph.state_graph import build_incidentops_graph
from incidentops.models.alert import AlertPayload


class IncidentOpsWorkflowManager:
    """Manages active incident triage StateGraph instances."""

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
        thread_id = thread_id or f"inc-{uuid.uuid4().hex[:8]}"
        config = {"configurable": {"thread_id": thread_id}}

        initial_state = {
            "alert_raw": alert.model_dump(),
            "iteration_count": 0,
            "thread_id": thread_id,
            "execution_logs": [f"Incident triage initiated for {alert.service_name} [{alert.severity}]"]
        }

        result_state = await self.graph.ainvoke(initial_state, config=config)
        return {
            "thread_id": thread_id,
            "status": "HALTED_AWAITING_HUMAN_APPROVAL",
            "state": result_state
        }

    async def resume_with_approval(
        self,
        thread_id: str,
        approved: bool,
        signature: str = "slack-hmac-verified"
    ) -> Dict[str, Any]:
        """Resume graph execution following human approval or rejection."""
        config = {"configurable": {"thread_id": thread_id}}

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
        return {
            "thread_id": thread_id,
            "status": final_state.get("remediation_status", "COMPLETED"),
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
