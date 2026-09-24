"""Typed LangGraph State definition for IncidentOps AI."""

from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


class IncidentState(TypedDict, total=False):
    """Production-grade typed state machine state for LangGraph.

    Tracks accumulated telemetry, supervisor plans, worker diagnostics,
    synthesized RCA, and human-in-the-loop cryptographic approval status.
    """
    alert_raw: Dict[str, Any]
    iteration_count: int
    supervisor_plan: Optional[Dict[str, Any]]
    log_evidence: Optional[Dict[str, Any]]
    metrics_evidence: Optional[Dict[str, Any]]
    code_evidence: Optional[Dict[str, Any]]
    final_rca: Optional[Dict[str, Any]]
    human_approved: Optional[bool]
    remediation_status: Optional[str]
    approval_signature: Optional[str]
    execution_logs: Optional[List[str]]
    thread_id: Optional[str]
