"""Log Diagnostic models conforming to Worker Agent 1 output contract."""

from typing import List, Literal
from pydantic import BaseModel, Field


LogSource = Literal["loki", "elasticsearch", "k8s_pod"]


class LogDiagnosticResult(BaseModel):
    """Structured diagnostic telemetry extracted by the Log Diagnostic Agent."""
    log_source: LogSource = Field(description="Telemetry source queried (loki, elasticsearch, or k8s_pod)")
    query_executed: str = Field(description="Exact query string executed against the log store")
    error_fingerprint: str = Field(description="Primary error signature / exception type")
    stack_trace_snippet: str = Field(description="Truncated relevant stack trace (max 30 lines)")
    error_rate_spike: str = Field(description="Error volume velocity, e.g. '450 errors/sec (baseline: 0.2/sec)'")
    first_seen_timestamp: str = Field(description="ISO-8601 UTC timestamp of first anomalous event")
    diagnostic_confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Diagnostic confidence between 0.0 and 1.0"
    )
    key_findings: List[str] = Field(
        default_factory=list,
        description="Concrete observations referencing file names, lines, or failed downstream attempts"
    )
