"""Realistic Enterprise Telemetry Simulator for MCP Tools.

Provides high-fidelity incident scenarios for offline execution, unit/integration testing,
and live demonstrations without requiring live Elasticsearch, Loki, Prometheus, or GitHub instances.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class MockTelemetryProvider:
    """Generates deterministic, realistic incident telemetry for MCP tool calls."""

    @staticmethod
    def get_order_service_scenario() -> Dict[str, Any]:
        """Scenario: Connection pool exhaustion caused by PR #412."""
        return {
            "loki": {
                "logs": [
                    {
                        "timestamp": "2026-09-24T14:28:12Z",
                        "level": "ERROR",
                        "logger": "db.connection_pool",
                        "message": "Timeout: QueuePool limit of size 10 overflow 5 reached, connection timed out, timeout 2.00",
                        "stack_trace": (
                            "sqlalchemy.exc.TimeoutError: QueuePool limit of size 10 overflow 5 reached\n"
                            "  File 'src/database/connection_pool.py', line 48, in get_connection\n"
                            "    conn = self._pool.connect(timeout=self.timeout)\n"
                            "  File 'sqlalchemy/pool/base.py', line 512, in connect\n"
                            "    return _ConnectionFairy._checkout(self)\n"
                            "sqlalchemy.exc.TimeoutError: Connection pool exhausted after 2000ms"
                        ),
                        "count": 450
                    }
                ],
                "error_rate": "450 errors/sec (baseline: 0.2/sec)",
                "error_fingerprint": "sqlalchemy.exc.TimeoutError: QueuePool limit exceeded"
            },
            "k8s_pod": {
                "pod_name": "order-service-api-7d6f549c-8w2k9",
                "namespace": "production",
                "container": "order-api",
                "logs": (
                    "[2026-09-24T14:28:10.102Z] INFO  [main] Server listening on port 8080\n"
                    "[2026-09-24T14:28:12.441Z] ERROR [db.pool] Connection pool exhausted: max overflow 5 reached\n"
                    "[2026-09-24T14:28:14.992Z] WARN  [health] Liveness probe failed: HTTP 500 Internal Server Error\n"
                    "[2026-09-24T14:28:16.120Z] ERROR [router] 504 Gateway Timeout on /v2/orders/checkout"
                )
            },
            "prometheus": {
                "metrics": {
                    "container_memory_working_set_bytes": "680 MiB",
                    "container_spec_memory_limit_bytes": "2.00 GiB",
                    "http_request_p99_latency_ms": 4820.0,
                    "baseline_p99_ms": 180.0,
                    "connection_pool_saturation": "100.0%",
                    "active_connections": 15,
                    "waiting_threads_in_queue": 142,
                    "http_5xx_rate": "450/sec",
                    "http_2xx_rate": "12/sec"
                },
                "primary_bottleneck": "CONNECTION_POOL_EXHAUSTION",
                "saturation_detected": True,
                "synthesis_summary": "DB connection pool size saturated at 15/15 connections with 142 threads queued. P99 latency degraded from 180ms to 4820ms."
            },
            "github": {
                "suspect_deployment_found": True,
                "commit_sha": "d4e29ab",
                "pr_number": 412,
                "author": "sarah.chen@company.com",
                "deployment_timestamp": "2026-09-24T14:15:00Z",
                "offending_code_paths": [
                    "src/database/connection_pool.py:L48",
                    "helm/values-prod.yaml:L112"
                ],
                "diff_analysis": (
                    "PR #412 ('Optimize DB connection timeouts') reduced pool timeout from 30s to 2s "
                    "and max_overflow from 50 to 5 in helm/values-prod.yaml, starving worker threads during traffic burst."
                ),
                "confidence_score": 0.96
            }
        }

    @staticmethod
    def get_memory_oom_scenario() -> Dict[str, Any]:
        """Scenario: Memory leak and OOMKilled container."""
        return {
            "loki": {
                "logs": [
                    {
                        "timestamp": "2026-09-24T10:14:02Z",
                        "level": "FATAL",
                        "logger": "runtime",
                        "message": "java.lang.OutOfMemoryError: Java heap space",
                        "stack_trace": (
                            "java.lang.OutOfMemoryError: Java heap space\n"
                            "  at com.company.payment.cache.TransactionCache.put(TransactionCache.java:88)\n"
                            "  at com.company.payment.service.PaymentProcessor.process(PaymentProcessor.java:142)"
                        ),
                        "count": 12
                    }
                ],
                "error_rate": "12 OOM panics/sec",
                "error_fingerprint": "java.lang.OutOfMemoryError: Java heap space"
            },
            "k8s_pod": {
                "pod_name": "payment-gateway-canary-6b99c8f-p9m4x",
                "namespace": "production",
                "container": "payment-gateway",
                "logs": (
                    "[2026-09-24T10:14:00Z] WARN  GC overhead limit exceeded\n"
                    "[2026-09-24T10:14:02Z] FATAL OutOfMemoryError in thread 'worker-9'\n"
                    "Command terminated with exit code 137 (OOMKilled by Linux cgroup kernel)"
                )
            },
            "prometheus": {
                "metrics": {
                    "container_memory_working_set_bytes": "1.98 GiB",
                    "container_spec_memory_limit_bytes": "2.00 GiB (99% limit reached)",
                    "http_request_p99_latency_ms": 3200.0,
                    "baseline_p99_ms": 120.0,
                    "oom_kill_events_total": 4
                },
                "primary_bottleneck": "MEMORY_EXHAUSTION_OOM",
                "saturation_detected": True,
                "synthesis_summary": "JVM heap consumption reached 99.2% of container cgroup quota (1.98 GiB / 2.0 GiB), triggering kernel OOMKiller."
            },
            "github": {
                "suspect_deployment_found": False,
                "commit_sha": None,
                "pr_number": None,
                "author": None,
                "deployment_timestamp": None,
                "offending_code_paths": [],
                "diff_analysis": "No code releases or config deployments detected in the last 4 hours. Issue appears to be slow memory leak in long-running canary replica.",
                "confidence_score": 0.88
            }
        }
