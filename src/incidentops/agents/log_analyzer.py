"""Worker Agent 1: Log Diagnostic Agent Node.

Extracts, filters, and analyzes log streams from Loki, Elasticsearch, or K8s pods.
"""

import json
from typing import Any, Dict
from incidentops.models.state import IncidentState
from incidentops.models.logs import LogDiagnosticResult
from incidentops.prompts.log_analyzer_prompt import LOG_DIAGNOSTIC_AGENT_PROMPT
from incidentops.mcp.tools import mcp__loki_search, mcp__k8s_get_pod_logs
from incidentops.agents.llm_factory import llm_engine


async def log_analyzer_node(state: IncidentState) -> Dict[str, Any]:
    """Execute log diagnostic worker to extract stack traces and error rate spikes."""
    alert_raw = state.get("alert_raw", {})
    service_name = alert_raw.get("service_name", "unknown-service")
    labels = alert_raw.get("labels", {})
    namespace = labels.get("namespace", "production")

    # 1. MCP Tool Execution (Loki and K8s pod logs)
    loki_results = await mcp__loki_search(
        query=f'{{app="{service_name}", namespace="{namespace}"}} |= "error"',
        limit=50
    )
    k8s_results = await mcp__k8s_get_pod_logs(
        namespace=namespace,
        pod_name=f"{service_name}-worker",
        previous=True
    )

    # 2. Formulate LLM message with tool output
    user_prompt = f"""Target Service: {service_name} (namespace: {namespace})
Alert Context: {json.dumps(alert_raw, indent=2)}

MCP Tool Execution Results:
--- Loki Stream Output ---
{json.dumps(loki_results, indent=2)}

--- K8s Pod Log Output ---
{json.dumps(k8s_results, indent=2)}

Analyze these logs. Extract error fingerprint, stack trace snippet (max 30 lines), error rate spike, and key observations."""

    # 3. Deterministic Mock Fallback
    mock_result = {
        "log_source": "loki",
        "query_executed": f'{{app="{service_name}", namespace="{namespace}"}} |= "error"',
        "error_fingerprint": "sqlalchemy.exc.TimeoutError: QueuePool limit of size 10 overflow 5 reached",
        "stack_trace_snippet": (
            "sqlalchemy.exc.TimeoutError: QueuePool limit of size 10 overflow 5 reached\n"
            "  File 'src/database/connection_pool.py', line 48, in get_connection\n"
            "    conn = self._pool.connect(timeout=self.timeout)\n"
            "  File 'sqlalchemy/pool/base.py', line 512, in connect\n"
            "    return _ConnectionFairy._checkout(self)\n"
            "sqlalchemy.exc.TimeoutError: Connection pool exhausted after 2000ms"
        ),
        "error_rate_spike": "450 errors/sec (baseline: 0.2/sec)",
        "first_seen_timestamp": alert_raw.get("timestamp", "2026-09-24T14:28:12Z"),
        "diagnostic_confidence": 0.95,
        "key_findings": [
            "Connection pool exhaustion on /v2/orders/checkout endpoint starting at 14:28 UTC.",
            "QueuePool overflow reached max capacity (5/5) with 142 waiting threads.",
            "Pods failing liveness probes with HTTP 500 / 504 Gateway Timeout."
        ]
    }

    # 4. Invoke LLM Engine
    diagnostic_result = await llm_engine.generate_structured(
        system_prompt=LOG_DIAGNOSTIC_AGENT_PROMPT,
        user_message=user_prompt,
        response_model=LogDiagnosticResult,
        mock_fallback=mock_result
    )

    return {"log_evidence": diagnostic_result.model_dump()}
