"""LangGraph StateGraph builder for IncidentOps AI.

Compiles parallel diagnostic fan-out, fan-in synthesis, and human-in-the-loop approval gate.
"""

from typing import Any, Optional
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from incidentops.config import settings
from incidentops.models.state import IncidentState
from incidentops.agents.supervisor import supervisor_node
from incidentops.agents.log_analyzer import log_analyzer_node
from incidentops.agents.metrics_correlator import metrics_correlator_node
from incidentops.agents.codebase_inspector import codebase_inspector_node
from incidentops.agents.synthesizer import root_cause_synthesizer_node
from incidentops.agents.approval_gate import human_approval_gate_node
from incidentops.agents.remediation_executor import remediation_executor_node


def build_incidentops_graph(checkpointer: Optional[Any] = None) -> Any:
    """Compile the IncidentOps AI LangGraph StateGraph with checkpointing and HITL gate.

    Architecture:
    1. START -> supervisor (determines triage plan, enforces loop bounds <= 3)
    2. supervisor -> parallel fan-out: [log_analyzer, metrics_correlator, codebase_inspector]
    3. parallel workers -> fan-in: synthesizer (correlates multi-modal evidence into RCA)
    4. synthesizer -> approval_gate (halted via interrupt_before)
    5. approval_gate -> remediation_executor (executes idempotent action if approved)
    6. remediation_executor -> END
    """
    if checkpointer is None:
        if settings.enable_postgres_checkpointer and settings.postgres_uri:
            try:
                from langgraph.checkpoint.postgres import PostgresSaver
                import psycopg
                # Use connection pool or connection
                conn = psycopg.connect(settings.postgres_uri, autocommit=True)
                checkpointer = PostgresSaver(conn)
                checkpointer.setup()
            except Exception as e:
                # Graceful fallback to in-memory checkpointer if Postgres is not reachable
                checkpointer = MemorySaver()
        else:
            checkpointer = MemorySaver()

    builder = StateGraph(IncidentState)

    # Register Nodes
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("log_analyzer", log_analyzer_node)
    builder.add_node("metrics_correlator", metrics_correlator_node)
    builder.add_node("codebase_inspector", codebase_inspector_node)
    builder.add_node("synthesizer", root_cause_synthesizer_node)
    builder.add_node("approval_gate", human_approval_gate_node)
    builder.add_node("remediation_executor", remediation_executor_node)

    # Edges: Sequential and Parallel Fan-Out
    builder.add_edge(START, "supervisor")
    builder.add_edge("supervisor", "log_analyzer")
    builder.add_edge("supervisor", "metrics_correlator")
    builder.add_edge("supervisor", "codebase_inspector")

    # Fan-In to Synthesis
    builder.add_edge(
        ["log_analyzer", "metrics_correlator", "codebase_inspector"],
        "synthesizer"
    )

    # Remediation Authorization Gate & Execution
    builder.add_edge("synthesizer", "approval_gate")
    builder.add_edge("approval_gate", "remediation_executor")
    builder.add_edge("remediation_executor", END)

    # Compile with checkpointing and interrupt at approval gate
    return builder.compile(
        checkpointer=checkpointer,
        interrupt_before=["approval_gate"]
    )
