"""Supervisor Plan models conforming to the Incident Commander output contract."""

from typing import List, Literal
from pydantic import BaseModel, Field


FaultDomain = Literal[
    "INFRASTRUCTURE",
    "APPLICATION_CODE",
    "DEPENDENCY_UPSTREAM",
    "DATABASE_STORAGE"
]

AgentTarget = Literal[
    "log_analyzer",
    "metrics_correlator",
    "codebase_inspector"
]


class TaskDispatch(BaseModel):
    """Specification for a sub-task dispatched concurrently to a diagnostic worker."""
    agent: AgentTarget = Field(description="Target specialized worker agent")
    instruction: str = Field(description="Target query, time window, metrics or PR to inspect")
    priority: int = Field(default=1, description="Priority level (1=highest, 2=secondary)")


class SupervisorPlan(BaseModel):
    """Deterministic triage plan produced by the Incident Commander."""
    incident_summary: str = Field(description="One-line technical summary of anomalous state")
    affected_component: str = Field(description="Service name and Kubernetes namespace")
    suspected_fault_domains: List[FaultDomain] = Field(
        default_factory=list,
        description="Identified potential fault domains"
    )
    tasks_to_dispatch: List[TaskDispatch] = Field(
        default_factory=list,
        description="List of tasks to dispatch concurrently to workers"
    )
    iteration_increment: int = Field(default=1, description="Iteration increment (normally 1)")
    should_terminate_to_synthesis: bool = Field(
        default=False,
        description="Whether to halt exploration and force transition to synthesis"
    )
