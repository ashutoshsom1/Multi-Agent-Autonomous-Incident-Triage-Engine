"""Unit & integration tests for LangGraph StateGraph, loop bounds, and FSM execution."""

import pytest
from incidentops.models.alert import AlertPayload
from incidentops.graph.state_graph import build_incidentops_graph
from incidentops.agents.supervisor import supervisor_node
from incidentops.config import settings


@pytest.mark.asyncio
async def test_supervisor_loop_bound_guard():
    """Verify that when iteration_count >= 3, supervisor enforces loop termination."""
    state = {
        "alert_raw": {
            "service_name": "order-service-api",
            "severity": "CRITICAL",
            "labels": {"namespace": "production"}
        },
        "iteration_count": 3  # Hit max limit
    }
    result = await supervisor_node(state)
    plan = result["supervisor_plan"]

    assert result["iteration_count"] == 4
    assert plan["should_terminate_to_synthesis"] is True
    assert len(plan["tasks_to_dispatch"]) == 0
    assert "Max loop bounds" in plan["incident_summary"]


@pytest.mark.asyncio
async def test_end_to_end_graph_execution_with_approval(sample_alert):
    """Verify complete graph run: triage -> interrupt at approval gate -> resume -> execute remediation."""
    graph = build_incidentops_graph()
    thread_id = "test-thread-fsm-001"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "alert_raw": sample_alert.model_dump(),
        "iteration_count": 0,
        "thread_id": thread_id
    }

    # 1. First execution up to interrupt_before=['approval_gate']
    state_before_approval = await graph.ainvoke(initial_state, config=config)

    assert state_before_approval.get("supervisor_plan") is not None
    assert state_before_approval.get("log_evidence") is not None
    assert state_before_approval.get("metrics_evidence") is not None
    assert state_before_approval.get("code_evidence") is not None
    assert state_before_approval.get("final_rca") is not None
    # Remediation not executed yet
    assert state_before_approval.get("human_approved") is None

    # Check next node in checkpoint
    snapshot = graph.get_state(config)
    assert "approval_gate" in snapshot.next

    # 2. Simulate Human Approval
    graph.update_state(config, {"human_approved": True, "approval_signature": "v0=test-sig-123"})
    state_after_approval = await graph.ainvoke(None, config=config)

    assert state_after_approval.get("human_approved") is True
    assert state_after_approval.get("remediation_status") == "REMEDIATION_EXECUTED_SUCCESSFULLY"
    assert len(state_after_approval.get("execution_logs", [])) > 0


@pytest.mark.asyncio
async def test_graph_execution_with_rejection(sample_alert):
    """Verify graph behavior when human rejects proposed remediation action."""
    graph = build_incidentops_graph()
    thread_id = "test-thread-fsm-reject"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "alert_raw": sample_alert.model_dump(),
        "iteration_count": 0,
        "thread_id": thread_id
    }

    await graph.ainvoke(initial_state, config=config)

    # Human Rejects
    graph.update_state(config, {"human_approved": False, "approval_signature": "operator-rejected"})
    final_state = await graph.ainvoke(None, config=config)

    assert final_state.get("human_approved") is False
    assert final_state.get("remediation_status") == "ESCALATED_TO_ONCALL"
    assert any("Escalated to on-call" in log for log in final_state.get("execution_logs", []))
