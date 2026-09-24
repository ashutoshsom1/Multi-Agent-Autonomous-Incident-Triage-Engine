"""Unit tests for Slack HMAC-SHA256 signature verification protocol."""

import time
from incidentops.agents.approval_gate import (
    generate_slack_hmac_signature,
    verify_slack_hmac_signature
)


def test_valid_slack_hmac_signature():
    secret = "my-test-signing-secret"
    timestamp = str(int(time.time()))
    body = 'payload={"type":"block_actions","actions":[{"action_id":"approve_remediation","value":"approve:inc-1"}]}'

    signature = generate_slack_hmac_signature(body, timestamp, signing_secret=secret)
    assert signature.startswith("v0=")

    is_valid, msg = verify_slack_hmac_signature(
        body=body,
        timestamp=timestamp,
        signature=signature,
        signing_secret=secret
    )
    assert is_valid is True
    assert "successfully" in msg


def test_tampered_payload_hmac_rejection():
    secret = "my-test-signing-secret"
    timestamp = str(int(time.time()))
    original_body = 'payload={"action":"approve"}'
    signature = generate_slack_hmac_signature(original_body, timestamp, signing_secret=secret)

    tampered_body = 'payload={"action":"delete_all_databases"}'
    is_valid, msg = verify_slack_hmac_signature(
        body=tampered_body,
        timestamp=timestamp,
        signature=signature,
        signing_secret=secret
    )
    assert is_valid is False
    assert "mismatch" in msg


def test_replay_attack_expired_timestamp():
    secret = "my-test-signing-secret"
    old_timestamp = str(int(time.time()) - 400)  # > 300s skew
    body = 'payload={"action":"approve"}'
    signature = generate_slack_hmac_signature(body, old_timestamp, signing_secret=secret)

    is_valid, msg = verify_slack_hmac_signature(
        body=body,
        timestamp=old_timestamp,
        signature=signature,
        signing_secret=secret,
        tolerance_seconds=300
    )
    assert is_valid is False
    assert "Timestamp expired" in msg
