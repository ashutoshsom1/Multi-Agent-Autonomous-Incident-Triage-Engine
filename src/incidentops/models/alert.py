"""Alert payload schemas and normalizers for Prometheus, Datadog, and PagerDuty."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Literal
from pydantic import BaseModel, Field


AlertSeverity = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
Environment = Literal["production", "staging", "canary"]


class AlertPayload(BaseModel):
    """Normalized alert schema consumed by the Incident Supervisor Agent."""
    alert_id: str = Field(description="Unique alert identifier")
    service_name: str = Field(description="Affected service / microservice name")
    environment: Environment = Field(default="production", description="Runtime environment")
    severity: AlertSeverity = Field(default="HIGH", description="Alert severity level")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO-8601 UTC timestamp of trigger"
    )
    description: str = Field(description="Alert trigger rule details and summary")
    labels: Dict[str, Any] = Field(
        default_factory=dict,
        description="Labels containing namespace, pod prefix, cluster, region, etc."
    )
    raw_payload: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Raw webhook payload preserved for auditing"
    )

    @classmethod
    def from_prometheus_alertmanager(cls, payload: Dict[str, Any]) -> "AlertPayload":
        """Normalize a Prometheus Alertmanager webhook payload."""
        alerts = payload.get("alerts", [{}])
        first = alerts[0] if alerts else {}
        labels = first.get("labels", {})
        annotations = first.get("annotations", {})

        severity_raw = labels.get("severity", "critical").upper()
        severity = severity_raw if severity_raw in ("CRITICAL", "HIGH", "MEDIUM", "LOW") else "HIGH"

        env_raw = labels.get("environment", labels.get("env", "production")).lower()
        environment = env_raw if env_raw in ("production", "staging", "canary") else "production"

        return cls(
            alert_id=labels.get("alertname", f"prom-{int(datetime.now().timestamp())}"),
            service_name=labels.get("service", labels.get("app", labels.get("job", "unknown-service"))),
            environment=environment,
            severity=severity,
            timestamp=first.get("startsAt", datetime.now(timezone.utc).isoformat()),
            description=annotations.get("description", annotations.get("summary", "Prometheus alert triggered")),
            labels=labels,
            raw_payload=payload
        )

    @classmethod
    def from_datadog(cls, payload: Dict[str, Any]) -> "AlertPayload":
        """Normalize a Datadog monitor webhook payload."""
        event_type = payload.get("event_type", "").lower()
        severity: AlertSeverity = "CRITICAL" if "error" in event_type or "critical" in event_type else "HIGH"
        tags = payload.get("tags", [])
        tag_dict = {}
        for tag in tags:
            if ":" in tag:
                k, v = tag.split(":", 1)
                tag_dict[k] = v

        env_raw = tag_dict.get("env", "production").lower()
        environment = env_raw if env_raw in ("production", "staging", "canary") else "production"

        return cls(
            alert_id=str(payload.get("id", f"dd-{int(datetime.now().timestamp())}")),
            service_name=tag_dict.get("service", payload.get("title", "unknown-service")),
            environment=environment,
            severity=severity,
            timestamp=payload.get("date", datetime.now(timezone.utc).isoformat()),
            description=payload.get("body", payload.get("title", "Datadog monitor alert")),
            labels=tag_dict,
            raw_payload=payload
        )

    @classmethod
    def from_pagerduty(cls, payload: Dict[str, Any]) -> "AlertPayload":
        """Normalize a PagerDuty v2 webhook payload."""
        event = payload.get("event", payload)
        data = event.get("data", {})
        service = data.get("service", {}).get("summary", "unknown-service")
        urgency = data.get("urgency", "high").upper()
        severity: AlertSeverity = "CRITICAL" if urgency == "HIGH" else "MEDIUM"

        return cls(
            alert_id=data.get("id", f"pd-{int(datetime.now().timestamp())}"),
            service_name=service,
            environment="production",
            severity=severity,
            timestamp=event.get("occurred_at", datetime.now(timezone.utc).isoformat()),
            description=data.get("title", data.get("summary", "PagerDuty incident triggered")),
            labels={"urgency": urgency, "service_name": service},
            raw_payload=payload
        )
