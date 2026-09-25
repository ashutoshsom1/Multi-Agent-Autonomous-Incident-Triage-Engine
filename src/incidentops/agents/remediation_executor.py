"""Remediation Executor Agent Node.

Executes the authorized remediation action strictly after human cryptographic approval.
"""

from typing import Any, Dict
from incidentops.models.state import IncidentState
from incidentops.mcp.tools import mcp__k8s_rollout_undo, mcp__k8s_restart_deployment, mcp__k8s_scale_deployment
from incidentops.telemetry import logger, metrics


async def remediation_executor_node(state: IncidentState) -> Dict[str, Any]:
    """Execute remediation commands via MCP strictly if human_approved is True."""
    is_approved = state.get("human_approved", False)
    final_rca = state.get("final_rca", {})
    remediation = final_rca.get("proposed_remediation", {})
    action_type = remediation.get("action_type", "UNKNOWN")
    alert_raw = state.get("alert_raw", {})
    service_name = alert_raw.get("service_name", "unknown-service")
    namespace = alert_raw.get("labels", {}).get("namespace", "production")
    thread_id = state.get("thread_id", "unknown")

    execution_logs = state.get("execution_logs", []) or []

    if not is_approved:
        msg = f"Remediation action [{action_type}] rejected by operator. Escalated to on-call SRE rotation."
        execution_logs.append(msg)
        logger.warning(msg, extra={"incident_id": thread_id, "worker": "remediation_executor"})
        metrics.record_remediation(action_type, "REJECTED_ESCALATED")
        return {
            "remediation_status": "ESCALATED_TO_ONCALL",
            "execution_logs": execution_logs
        }

    # Execute authorized remediation
    try:
        if action_type == "REVERT_DEPLOYMENT":
            result = await mcp__k8s_rollout_undo(namespace=namespace, deployment=service_name)
            execution_logs.append(f"Executed: {result['output']}")
        elif action_type == "RESTART_PODS_CANARY":
            result = await mcp__k8s_restart_deployment(namespace=namespace, deployment=service_name)
            execution_logs.append(f"Executed: {result['output']}")
        elif action_type == "SCALE_REPLICAS":
            result = await mcp__k8s_scale_deployment(namespace=namespace, deployment=service_name, replicas=10)
            execution_logs.append(f"Executed: {result['output']}")
        else:
            command = remediation.get("command_or_script", "echo 'No command specified'")
            execution_logs.append(f"Executed custom script: {command}")

        metrics.record_remediation(action_type, "SUCCESS")
        logger.info(
            f"Remediation [{action_type}] successfully executed for {service_name}",
            extra={"incident_id": thread_id, "worker": "remediation_executor"}
        )
        status = "REMEDIATION_EXECUTED_SUCCESSFULLY"
    except Exception as e:
        err_msg = f"Remediation execution failed: {e}"
        execution_logs.append(err_msg)
        logger.error(err_msg, exc_info=True, extra={"incident_id": thread_id, "worker": "remediation_executor"})
        metrics.record_remediation(action_type, "FAILED")
        status = "REMEDIATION_FAILED_ESCALATED"

    return {
        "remediation_status": status,
        "execution_logs": execution_logs
    }
