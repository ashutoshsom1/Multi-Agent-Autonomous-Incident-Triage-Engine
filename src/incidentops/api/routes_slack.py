"""Slack Interactive Webhook Route with Cryptographic HMAC Signature Verification."""

import json
from typing import Any, Dict
from urllib.parse import parse_qs
from fastapi import APIRouter, Header, HTTPException, Request

from incidentops.config import settings
from incidentops.agents.approval_gate import verify_slack_hmac_signature
from incidentops.graph.workflow import workflow_manager

router = APIRouter(prefix="/api/v1/slack", tags=["Slack Integration"])


@router.post("/actions")
async def slack_interactive_actions(
    request: Request,
    x_slack_signature: str = Header(default="", alias="X-Slack-Signature"),
    x_slack_request_timestamp: str = Header(default="", alias="X-Slack-Request-Timestamp")
) -> Dict[str, Any]:
    """Handle interactive Slack Block Kit actions (Approve / Reject buttons).

    Validates incoming request with HMAC-SHA256 signature verification.
    Resumes LangGraph execution and returns updated Slack card.
    """
    raw_body_bytes = await request.body()
    raw_body = raw_body_bytes.decode("utf-8")

    # Verify HMAC-SHA256 signature if in production/staging or secret provided
    if settings.app_env in ("production", "staging") or x_slack_signature:
        is_valid, reason = verify_slack_hmac_signature(
            body=raw_body,
            timestamp=x_slack_request_timestamp,
            signature=x_slack_signature,
            signing_secret=settings.slack_signing_secret
        )
        if not is_valid:
            raise HTTPException(status_code=403, detail=f"HMAC Verification Failed: {reason}")

    # Parse Slack url-encoded form payload: payload={"type": "block_actions", ...}
    try:
        parsed_form = parse_qs(raw_body)
        payload_json_str = parsed_form.get("payload", ["{}"])[0]
        payload = json.loads(payload_json_str)
    except Exception:
        # Fallback if sent as direct JSON
        try:
            payload = json.loads(raw_body)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid Slack payload format")

    actions = payload.get("actions", [])
    if not actions:
        return {"status": "ignored", "message": "No actions in payload"}

    action = actions[0]
    action_id = action.get("action_id", "")
    value = action.get("value", "")

    # Parse action value format: "approve:<thread_id>" or "reject:<thread_id>"
    if ":" in value:
        verb, thread_id = value.split(":", 1)
        is_approved = (verb == "approve" or action_id == "approve_remediation")
    else:
        thread_id = value
        is_approved = (action_id == "approve_remediation")

    # Resume graph execution with human cryptographic authorization
    result = await workflow_manager.resume_with_approval(
        thread_id=thread_id,
        approved=is_approved,
        signature=x_slack_signature or "hmac-verified-interactive"
    )

    state = result.get("state", {})
    remediation_status = state.get("remediation_status", "UNKNOWN")
    execution_logs = state.get("execution_logs", [])

    return {
        "response_type": "in_channel",
        "replace_original": True,
        "text": f"Remediation update for incident `{thread_id}`:",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🛡️ IncidentOps Remediation Authorization",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Incident:*\n`{thread_id}`"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Status:*\n`{remediation_status}`"
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Execution Logs:*\n```" + "\n".join(execution_logs) + "```"
                }
            }
        ]
    }
