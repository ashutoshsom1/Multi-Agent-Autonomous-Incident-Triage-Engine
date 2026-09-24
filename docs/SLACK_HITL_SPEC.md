# 🔐 Slack Interactive HITL Gate Specification

This document details the cryptographic security specification and Block Kit card layout for the **Human-in-the-Loop (HITL)** remediation gate.

---

## 1. Cryptographic HMAC-SHA256 Signature Verification

To prevent unauthorized, rogue, or replayed remediation execution, all Slack interactive callbacks must pass cryptographic verification:

```python
signature = "v0=" + hmac_sha256(
    secret=SLACK_SIGNING_SECRET,
    data=f"v0:{timestamp}:{raw_request_body}"
)
```

### Security Requirements:
1. **Replay Attack Defense:** Request timestamps older than 300 seconds are rejected with HTTP 403.
2. **Timing Attack Defense:** Signatures are compared using constant-time evaluation (`hmac.compare_digest`).
3. **Payload Integrity:** Any tampering with the incident ID or action values in the POST body invalidates the signature.

---

## 2. Interactive Block Kit Card Layout

```json
[
  {
    "type": "header",
    "text": {
      "type": "plain_text",
      "text": "🚨 [P1-CRITICAL] Root Cause Isolated: order-service-api",
      "emoji": true
    }
  },
  {
    "type": "section",
    "fields": [
      {
        "type": "mrkdwn",
        "text": "*Confidence:*\n94% Confident"
      },
      {
        "type": "mrkdwn",
        "text": "*Incident ID:*\n`inc-7a91bf`"
      }
    ]
  },
  {
    "type": "section",
    "text": {
      "type": "mrkdwn",
      "text": "*Evidence Summary:*\nLogs reveal DB connection pool exhaustion (450 err/s) directly introduced by PR #412."
    }
  },
  {
    "type": "divider"
  },
  {
    "type": "actions",
    "block_id": "incident_gate_inc-7a91bf",
    "elements": [
      {
        "type": "button",
        "text": {
          "type": "plain_text",
          "text": "✅ Approve Rollback (Deploy v2.14.1)",
          "emoji": true
        },
        "style": "primary",
        "value": "approve:inc-7a91bf",
        "action_id": "approve_remediation"
      },
      {
        "type": "button",
        "text": {
          "type": "plain_text",
          "text": "❌ Reject & Escalate to On-Call SRE",
          "emoji": true
        },
        "style": "danger",
        "value": "reject:inc-7a91bf",
        "action_id": "reject_remediation"
      }
    ]
  }
]
```
