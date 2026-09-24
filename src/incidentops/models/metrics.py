"""Metrics Correlation models conforming to Worker Agent 2 output contract."""

from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field


BottleneckType = Literal[
    "MEMORY_EXHAUSTION_OOM",
    "THREAD_POOL_STARVATION",
    "NETWORK_EGRESS_DROP",
    "CONNECTION_POOL_EXHAUSTION",
    "CPU_THROTTLING",
    "DISK_IO_SATURATION",
    "NONE"
]


class TelemetryEvidence(BaseModel):
    """Quantitative evidence collected from Prometheus USE / RED metrics."""
    metric_name: str = Field(description="Primary anomalous metric identifier")
    observed_value: str = Field(description="Observed peak or current metric value")
    threshold_limit: str = Field(description="Configured SLO threshold or container limit")
    p99_latency_ms: Optional[float] = Field(default=None, description="Observed P99 latency in milliseconds")
    baseline_p99_ms: Optional[float] = Field(default=None, description="Historical baseline P99 latency in ms")
    extra_details: Dict[str, Any] = Field(default_factory=dict, description="Additional metric details")


class MetricsCorrelationResult(BaseModel):
    """Correlation findings evaluated via USEE methodology (USE & RED metrics)."""
    evaluated_metrics: List[str] = Field(
        default_factory=list,
        description="Metrics evaluated (e.g. CPU, Memory, P99_Latency, Error_Rate, Connection_Pool)"
    )
    saturation_detected: bool = Field(description="Whether resource saturation or exhaustion was detected")
    primary_bottleneck: Union[BottleneckType, str] = Field(
        description="Primary bottleneck isolated during telemetry evaluation"
    )
    telemetry_evidence: Union[TelemetryEvidence, Dict[str, Any]] = Field(
        description="Quantitative evidence supporting the conclusion"
    )
    correlation_confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score for telemetry correlation"
    )
    synthesis_summary: str = Field(
        description="Quantitative 2-line explanation of resource depletion and anomalous dynamics"
    )
