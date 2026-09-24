"""Root Cause Synthesis & Remediation Gate models conforming to Output Contract #5."""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


RemediationActionType = Literal[
    "REVERT_DEPLOYMENT",
    "RESTART_PODS_CANARY",
    "SCALE_REPLICAS",
    "FAILOVER_DATABASE",
    "ROLLBACK_CONFIG",
    "CUSTOM_SCRIPT"
]


class RootCauseAnalysis(BaseModel):
    """Correlated multi-agent root cause analysis."""
    title: str = Field(description="Clear, technical summary of root cause")
    confidence_percentage: int = Field(
        ge=0,
        le=100,
        description="Confidence percentage (0 to 100)"
    )
    primary_fault_domain: str = Field(
        description="Identified primary fault domain (e.g. APPLICATION_CODE, INFRASTRUCTURE)"
    )
    chain_of_events: List[str] = Field(
        default_factory=list,
        description="Step-by-step chronological causal chain of events leading to outage"
    )


class ProposedRemediation(BaseModel):
    """Calculated automated remediation plan with strict blast radius assessment."""
    action_type: RemediationActionType = Field(description="Taxonomy classification of remediation action")
    command_or_script: str = Field(description="Idempotent script/command to execute upon approval")
    expected_recovery_time_seconds: int = Field(description="Estimated time to recovery (MTTR in seconds)")
    blast_radius: str = Field(description="Downtime risk, in-flight request impact, session data evaluation")
    rollback_plan: str = Field(description="Counter-action plan if proposed remediation fails")


class SlackBlockKitCard(BaseModel):
    """Interactive Slack card structure with cryptographic approval controls."""
    headline: str = Field(description="Slack card bold headline with severity and target service")
    confidence_badge: str = Field(description="Visual confidence badge (e.g. '94% Confident')")
    evidence_summary: str = Field(description="Concise synthesis of evidence for on-call SRE")
    action_button_label: str = Field(description="Approval button text")
    reject_button_label: str = Field(description="Rejection/escalation button text")
    blocks: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Raw Slack Block Kit payload"
    )

    def to_slack_blocks(self, incident_id: str) -> List[Dict[str, Any]]:
        """Render interactive Slack Block Kit blocks with action IDs and incident binding."""
        return [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": self.headline,
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Confidence:*\n{self.confidence_badge}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Incident ID:*\n`{incident_id}`"
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Evidence Summary:*\n{self.evidence_summary}"
                }
            },
            {"type": "divider"},
            {
                "type": "actions",
                "block_id": f"incident_gate_{incident_id}",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": f"✅ {self.action_button_label}",
                            "emoji": True
                        },
                        "style": "primary",
                        "value": f"approve:{incident_id}",
                        "action_id": "approve_remediation"
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": f"❌ {self.reject_button_label}",
                            "emoji": True
                        },
                        "style": "danger",
                        "value": f"reject:{incident_id}",
                        "action_id": "reject_remediation"
                    }
                ]
            }
        ]


class IncidentTriageReport(BaseModel):
    """Complete Incident Triage Report produced by the Root Cause Synthesizer."""
    root_cause_analysis: RootCauseAnalysis = Field(description="Diagnostic root cause analysis")
    proposed_remediation: ProposedRemediation = Field(description="Proposed automated remediation")
    slack_block_kit_card: SlackBlockKitCard = Field(description="Human-in-the-loop Slack card")
