"""Worker Agent 2: Metrics Correlation Agent Node.

USEE Methodology (Utilization, Saturation, Errors, Duration) via Prometheus MCP tools.
"""

import json
from typing import Any, Dict
from incidentops.models.state import IncidentState
from incidentops.models.metrics import MetricsCorrelationResult
from incidentops.prompts.metrics_correlator_prompt import METRICS_CORRELATION_AGENT_PROMPT
from incidentops.mcp.tools import mcp__prometheus_query_range
from incidentops.agents.llm_factory import llm_engine


async def metrics_correlator_node(state: IncidentState) -> Dict[str, Any]:
    """Execute metrics correlation worker to detect resource saturation and latency deviations."""
    alert_raw = state.get("alert_raw", {})
    service_name = alert_raw.get("service_name", "unknown-service")
    labels = alert_raw.get("labels", {})
    namespace = labels.get("namespace", "production")

    # 1. MCP Tool Execution (Prometheus query range)
    prom_results = await mcp__prometheus_query_range(
        query=f'histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{{service="{service_name}"}}[5m])) by (le))',
        start="now-15m",
        end="now",
        step="15s"
    )

    # 2. Formulate LLM message with tool output
    user_prompt = f"""Target Service: {service_name} (namespace: {namespace})
Alert Context: {json.dumps(alert_raw, indent=2)}

Prometheus MCP Range Query Output:
{json.dumps(prom_results, indent=2)}

Apply USEE methodology (Utilization, Saturation, Errors, Duration).
Evaluate CPU, Memory, Connection Pool, and P99 latency against baseline."""

    # 3. Deterministic Mock Fallback
    mock_result = {
        "evaluated_metrics": ["CPU", "Memory", "P99_Latency", "Error_Rate", "Connection_Pool"],
        "saturation_detected": True,
        "primary_bottleneck": "THREAD_POOL_STARVATION",
        "telemetry_evidence": {
            "metric_name": "container_connection_pool_active_connections",
            "observed_value": "15 active connections (100% capacity)",
            "threshold_limit": "Max pool size: 10 + 5 overflow",
            "p99_latency_ms": 4820.0,
            "baseline_p99_ms": 180.0
        },
        "correlation_confidence": 0.94,
        "synthesis_summary": "Connection pool reached 100% saturation with 142 queued threads. P99 latency spiked from 180ms to 4820ms accompanied by 450 err/sec 5xx burst."
    }

    # 4. Invoke LLM Engine
    metrics_result = await llm_engine.generate_structured(
        system_prompt=METRICS_CORRELATION_AGENT_PROMPT,
        user_message=user_prompt,
        response_model=MetricsCorrelationResult,
        mock_fallback=mock_result
    )

    return {"metrics_evidence": metrics_result.model_dump()}
