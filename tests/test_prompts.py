"""Unit tests ensuring system prompts contain enterprise directives and guards."""

from incidentops.prompts import (
    INCIDENT_SUPERVISOR_SYSTEM_PROMPT,
    LOG_DIAGNOSTIC_AGENT_PROMPT,
    METRICS_CORRELATION_AGENT_PROMPT,
    CODEBASE_INSPECTOR_AGENT_PROMPT,
    ROOT_CAUSE_SYNTHESIS_PROMPT,
)


def test_supervisor_prompt_constraints():
    prompt = INCIDENT_SUPERVISOR_SYSTEM_PROMPT
    assert "LOOP-BOUND GUARD" in prompt
    assert "iteration_count >= 3" in prompt
    assert "ZERO HALLUCINATION" in prompt
    assert "DETERMINISTIC DISPATCH" in prompt
    assert "SupervisorPlan" in prompt


def test_log_diagnostic_prompt_protocol():
    prompt = LOG_DIAGNOSTIC_AGENT_PROMPT
    assert "mcp__loki_search" in prompt
    assert "mcp__elasticsearch_query" in prompt
    assert "mcp__k8s_get_pod_logs" in prompt
    assert "TIME SYNCHRONIZATION" in prompt
    assert "diagnostic_confidence" in prompt


def test_metrics_prompt_methodology():
    prompt = METRICS_CORRELATION_AGENT_PROMPT
    assert "USEE METHODOLOGY" in prompt
    assert "mcp__prometheus_query_range" in prompt
    assert "P99" in prompt
    assert "saturation_detected" in prompt


def test_codebase_prompt_workflow():
    prompt = CODEBASE_INSPECTOR_AGENT_PROMPT
    assert "INVESTIGATION WORKFLOW" in prompt
    assert "DEPLOYMENT TIMING" in prompt
    assert "DIFF TRIAGE" in prompt
    assert "AUTHOR & PR TRACEABILITY" in prompt
    assert "suspect_deployment_found" in prompt


def test_synthesis_prompt_remediation_taxonomy():
    prompt = ROOT_CAUSE_SYNTHESIS_PROMPT
    assert "NEVER EXECUTE DESTRUCTIVE ACTIONS DIRECTLY" in prompt
    assert "REVERT_DEPLOYMENT" in prompt
    assert "RESTART_PODS_CANARY" in prompt
    assert "SCALE_REPLICAS" in prompt
    assert "FAILOVER_DATABASE" in prompt
    assert "BLAST RADIUS CALCULATION" in prompt
