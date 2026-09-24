"""System prompts suite for IncidentOps AI multi-agent triage."""

from incidentops.prompts.supervisor_prompt import INCIDENT_SUPERVISOR_SYSTEM_PROMPT
from incidentops.prompts.log_analyzer_prompt import LOG_DIAGNOSTIC_AGENT_PROMPT
from incidentops.prompts.metrics_correlator_prompt import METRICS_CORRELATION_AGENT_PROMPT
from incidentops.prompts.codebase_inspector_prompt import CODEBASE_INSPECTOR_AGENT_PROMPT
from incidentops.prompts.root_cause_synthesizer_prompt import ROOT_CAUSE_SYNTHESIS_PROMPT

__all__ = [
    "INCIDENT_SUPERVISOR_SYSTEM_PROMPT",
    "LOG_DIAGNOSTIC_AGENT_PROMPT",
    "METRICS_CORRELATION_AGENT_PROMPT",
    "CODEBASE_INSPECTOR_AGENT_PROMPT",
    "ROOT_CAUSE_SYNTHESIS_PROMPT",
]
