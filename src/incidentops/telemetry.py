"""Enterprise structured logging and Prometheus metrics exporter for IncidentOps AI."""

import json
import logging
import sys
import time
from collections import defaultdict
from typing import Any, Dict, Optional

from incidentops.config import settings


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured cloud logging (Datadog, CloudWatch, Stackdriver)."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno
        }
        if hasattr(record, "incident_id"):
            log_obj["incident_id"] = getattr(record, "incident_id")
        if hasattr(record, "worker"):
            log_obj["worker"] = getattr(record, "worker")
        if hasattr(record, "duration_ms"):
            log_obj["duration_ms"] = getattr(record, "duration_ms")
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)


def configure_logging():
    """Configure system-wide logging based on settings."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    # Remove existing handlers
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    if settings.log_format == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s")
        )

    root_logger.addHandler(handler)


logger = logging.getLogger("incidentops")


class PrometheusMetricsRegistry:
    """In-memory Prometheus metrics exporter compliant with Prometheus exposition format."""

    def __init__(self):
        self.incidents_total = defaultdict(int)
        self.triage_duration_sum = 0.0
        self.triage_duration_count = 0
        self.worker_duration_sum = defaultdict(float)
        self.worker_duration_count = defaultdict(int)
        self.mcp_tool_calls = defaultdict(int)
        self.remediations_total = defaultdict(int)

    def record_incident(self, severity: str, status: str):
        key = f'severity="{severity}",status="{status}"'
        self.incidents_total[key] += 1

    def record_triage_duration(self, seconds: float):
        self.triage_duration_sum += seconds
        self.triage_duration_count += 1

    def record_worker_execution(self, worker: str, seconds: float):
        self.worker_duration_sum[worker] += seconds
        self.worker_duration_count[worker] += 1

    def record_mcp_call(self, tool: str, status: str):
        key = f'tool="{tool}",status="{status}"'
        self.mcp_tool_calls[key] += 1

    def record_remediation(self, action_type: str, status: str):
        key = f'action_type="{action_type}",status="{status}"'
        self.remediations_total[key] += 1

    def export(self) -> str:
        """Export metrics in standard Prometheus text exposition format."""
        lines = [
            "# HELP incidentops_incidents_total Total number of alerts triaged by severity and status.",
            "# TYPE incidentops_incidents_total counter"
        ]
        for labels, val in self.incidents_total.items():
            lines.append(f"incidentops_incidents_total{{{labels}}} {val}")

        lines.extend([
            "# HELP incidentops_triage_duration_seconds Total time spent in autonomous triage.",
            "# TYPE incidentops_triage_duration_seconds summary",
            f"incidentops_triage_duration_seconds_sum {self.triage_duration_sum:.4f}",
            f"incidentops_triage_duration_seconds_count {self.triage_duration_count}",
        ])

        lines.extend([
            "# HELP incidentops_worker_duration_seconds Total execution time per worker node.",
            "# TYPE incidentops_worker_duration_seconds summary"
        ])
        for worker, count in self.worker_duration_count.items():
            duration_sum = self.worker_duration_sum[worker]
            lines.append(f'incidentops_worker_duration_seconds_sum{{worker="{worker}"}} {duration_sum:.4f}')
            lines.append(f'incidentops_worker_duration_seconds_count{{worker="{worker}"}} {count}')

        lines.extend([
            "# HELP incidentops_mcp_tool_calls_total Total calls executed to MCP tools.",
            "# TYPE incidentops_mcp_tool_calls_total counter"
        ])
        for labels, val in self.mcp_tool_calls.items():
            lines.append(f"incidentops_mcp_tool_calls_total{{{labels}}} {val}")

        lines.extend([
            "# HELP incidentops_remediations_total Remediations executed by action type and status.",
            "# TYPE incidentops_remediations_total counter"
        ])
        for labels, val in self.remediations_total.items():
            lines.append(f"incidentops_remediations_total{{{labels}}} {val}")

        return "\n".join(lines) + "\n"


metrics = PrometheusMetricsRegistry()
