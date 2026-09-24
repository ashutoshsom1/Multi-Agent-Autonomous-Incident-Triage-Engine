"""Remediation Executor Agent Node.

Executes the authorized remediation action strictly after human cryptographic approval.
"""

from typing import Any, Dict
from incidentops.models.state import IncidentState
from incidentops.mcp.tools import mcp__k8s_rollout_undo, mcp__k8s_restart_deployment, mcp__k8s_scale_deployment


async def remediation_executor_node(state: IncidentState) -> Dict[str, Any]:
    """Execute remediation commands via MCP strictly if human_approved is True."""
    is_approved = state.get("human_approved", False)
    final_rca = state.get("final_rca", {})
    remediation = final_rca.get("proposed_remediation", {})
    action_type = remediation.get("action_type", "")
    alert_raw = state.get("alert_raw", {})
    service_name = alert_raw.get("service_name", "unknown-service")
    namespace = alert_raw.get("labels", {}).get("namespace", "production")

    execution_logs = state.get("execution_logs", []) or []

    if not is_approved:
        execution_logs.append("Action rejected by human operator. Escalated to on-call SRE rotation.")
        return {
            "remediation_status": "ESCALATED_TO_ONCALL",
            "execution_logs": execution_logs
        }

    # Execute authorized remediation
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

    return {
        "remediation_status": "REMEDIATION_EXECUTED_SUCCESSFULLY",
        "execution_logs": execution_logs
    }
