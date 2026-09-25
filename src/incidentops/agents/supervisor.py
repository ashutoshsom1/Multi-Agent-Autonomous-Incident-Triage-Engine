"""Incident Supervisor / Orchestrator Agent Node.

FSM Commander, loop-guard controller, and diagnostic task dispatcher.
"""

import json
import time
from typing import Any, Dict
from incidentops.config import settings
from incidentops.models.state import IncidentState
from incidentops.models.supervisor import SupervisorPlan, TaskDispatch
from incidentops.prompts.supervisor_prompt import INCIDENT_SUPERVISOR_SYSTEM_PROMPT
from incidentops.agents.llm_factory import llm_engine
from incidentops.telemetry import logger, metrics


async def supervisor_node(state: IncidentState) -> Dict[str, Any]:
    """Execute supervisor node to formulate diagnostic plan with strict loop guard.

    Constraints enforced:
    - LOOP-BOUND GUARD: If iteration_count >= 3, force should_terminate_to_synthesis=True.
    - DETERMINISTIC DISPATCH: Routes tasks to log_analyzer, metrics_correlator, codebase_inspector.
    """
    start_time = time.time()
    iteration_count = state.get("iteration_count", 0)
    alert_raw = state.get("alert_raw", {})
    service_name = alert_raw.get("service_name", "unknown-service")
    labels = alert_raw.get("labels", {})
    namespace = labels.get("namespace", settings.k8s_namespace_default)
    thread_id = state.get("thread_id", "unknown")

    logger.info(
        f"Supervisor dispatching triage for {service_name} (iteration: {iteration_count})",
        extra={"incident_id": thread_id, "worker": "supervisor"}
    )

    # 1. Loop-Bound Guard Enforcement
    if iteration_count >= settings.max_iteration_guard:
        logger.warning(
            f"Max loop guard reached ({settings.max_iteration_guard}) for {service_name}. Forcing state transition to synthesis.",
            extra={"incident_id": thread_id, "worker": "supervisor"}
        )
        plan = SupervisorPlan(
            incident_summary=f"Max loop bounds ({settings.max_iteration_guard}) reached for {service_name}. Forcing state transition to synthesis.",
            affected_component=f"{service_name} ({namespace})",
            suspected_fault_domains=["APPLICATION_CODE", "INFRASTRUCTURE"],
            tasks_to_dispatch=[],
            iteration_increment=1,
            should_terminate_to_synthesis=True
        )
        metrics.record_worker_execution("supervisor", time.time() - start_time)
        return {
            "supervisor_plan": plan.model_dump(),
            "iteration_count": iteration_count + 1
        }

    # 2. Formulate user prompt with alert JSON
    user_prompt = f"""Incoming High-Severity Alert Webhook:
{json.dumps(alert_raw, indent=2)}

Formulate your targeted diagnostic triage plan. Ensure tasks are dispatched to log_analyzer, metrics_correlator, and codebase_inspector."""

    # 3. Deterministic Mock Fallback for offline execution & benchmarks
    mock_plan = {
        "incident_summary": f"High error rates and latency degradation detected in {service_name}",
        "affected_component": f"{service_name} (namespace: {namespace})",
        "suspected_fault_domains": ["APPLICATION_CODE", "DATABASE_STORAGE", "INFRASTRUCTURE"],
        "tasks_to_dispatch": [
            {
                "agent": "log_analyzer",
                "instruction": f"Search logs for {service_name} in namespace {namespace} for timeout errors, stack traces, and error rate spike in [T-15m, T+5m]",
                "priority": 1
            },
            {
                "agent": "metrics_correlator",
                "instruction": f"Evaluate CPU, Memory, Connection Pool saturation, and P99 latency deviation for {service_name}",
                "priority": 1
            },
            {
                "agent": "codebase_inspector",
                "instruction": f"Inspect repository commits, PRs, and Helm configs merged within the last 60 minutes affecting {service_name}",
                "priority": 2
            }
        ],
        "iteration_increment": 1,
        "should_terminate_to_synthesis": False
    }

    try:
        plan = await llm_engine.generate_structured(
            system_prompt=INCIDENT_SUPERVISOR_SYSTEM_PROMPT,
            user_message=user_prompt,
            response_model=SupervisorPlan,
            mock_fallback=mock_plan
        )
    except Exception as e:
        logger.error(f"Supervisor LLM call failed: {e}. Falling back to default dispatch.", exc_info=True)
        plan = SupervisorPlan.model_validate(mock_plan)

    duration = time.time() - start_time
    metrics.record_worker_execution("supervisor", duration)

    return {
        "supervisor_plan": plan.model_dump(),
        "iteration_count": iteration_count + 1
    }
