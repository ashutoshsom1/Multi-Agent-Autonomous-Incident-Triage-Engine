"""Root Cause Synthesis Agent Node.

Synthesizes multi-agent diagnostic evidence (Logs, Metrics, Git/Code) into an incontrovertible RCA,
calculates blast radius, and drafts the Human-in-the-Loop Slack Card payload.
"""

import json
from typing import Any, Dict
from incidentops.models.state import IncidentState
from incidentops.models.rca import IncidentTriageReport, RootCauseAnalysis, ProposedRemediation, SlackBlockKitCard
from incidentops.prompts.root_cause_synthesizer_prompt import ROOT_CAUSE_SYNTHESIS_PROMPT
from incidentops.agents.llm_factory import llm_engine


async def root_cause_synthesizer_node(state: IncidentState) -> Dict[str, Any]:
    """Execute Root Cause Synthesizer to correlate multi-modal findings into an RCA and remediation plan."""
    alert_raw = state.get("alert_raw", {})
    service_name = alert_raw.get("service_name", "unknown-service")
    log_evidence = state.get("log_evidence", {})
    metrics_evidence = state.get("metrics_evidence", {})
    code_evidence = state.get("code_evidence", {})

    # Formulate multi-modal evidence prompt
    user_prompt = f"""Multi-Agent Incident Diagnostics Synthesis Request:
Target Service: {service_name}
Alert Raw: {json.dumps(alert_raw, indent=2)}

=== Worker 1: Log Diagnostics ===
{json.dumps(log_evidence, indent=2)}

=== Worker 2: Metrics Correlation ===
{json.dumps(metrics_evidence, indent=2)}

=== Worker 3: Codebase Inspection ===
{json.dumps(code_evidence, indent=2)}

Synthesize these findings into an incontrovertible Root Cause Diagnostic (RCA).
Calculate the blast radius, recovery time, and formulate the interactive Slack card."""

    # Deterministic Mock Fallback for offline benchmarks & demo
    mock_report = {
        "root_cause_analysis": {
            "title": f"Database Connection Pool Exhaustion in {service_name} due to aggressive timeout reduction in PR #412",
            "confidence_percentage": 94,
            "primary_fault_domain": "APPLICATION_CODE",
            "chain_of_events": [
                "1. PR #412 merged at 14:15 UTC reducing connection pool timeout to 2s and max overflow to 5.",
                "2. Traffic burst at 14:28 UTC quickly saturated the constrained connection pool (15/15 active).",
                "3. 142 worker threads blocked waiting for connections, elevating P99 latency from 180ms to 4820ms.",
                "4. Order checkout endpoints failed liveness probes with HTTP 500/504, generating 450 errors/sec cascade."
            ]
        },
        "proposed_remediation": {
            "action_type": "REVERT_DEPLOYMENT",
            "command_or_script": f"kubectl rollout undo deployment/{service_name} -n production",
            "expected_recovery_time_seconds": 45,
            "blast_radius": "Zero user-facing data loss; in-flight requests during rollout restart might retry.",
            "rollback_plan": "Re-apply image tag sha-98213f if rollback fails"
        },
        "slack_block_kit_card": {
            "headline": f"🚨 [P1-CRITICAL] Root Cause Isolated: {service_name}",
            "confidence_badge": "94% Confident",
            "evidence_summary": f"Logs reveal DB connection pool exhaustion (450 err/s) directly introduced by PR #412.",
            "action_button_label": "Approve Rollback (Deploy v2.14.1)",
            "reject_button_label": "Reject & Escalate to On-Call SRE"
        }
    }

    rca_report = await llm_engine.generate_structured(
        system_prompt=ROOT_CAUSE_SYNTHESIS_PROMPT,
        user_message=user_prompt,
        response_model=IncidentTriageReport,
        mock_fallback=mock_report
    )

    return {"final_rca": rca_report.model_dump()}
