# 📋 IncidentOps AI: SRE Production Operations Runbook

**Document Owner:** SRE & Platform Engineering  
**Classification:** Enterprise Production Operations  
**Target Availability:** 99.95% (Multi-AZ)  
**Target MTTT (Mean Time to Triage):** $\le 90$ seconds  

---

## 1. Incident Severity Matrix & Triage SLA

| Severity | Definition | Autonomous Engine Action | Target MTTT | Escalation SLA |
|---|---|---|---|---|
| **P1 - CRITICAL** | Customer-facing outage, data plane failure, severe latency degradation ($>5\times$ baseline), or active cascade. | Autonomous parallel MCP triage; generate RCA & Blast Radius; post interactive Slack card; require cryptographic human sign-off. | $< 90$ seconds | PagerDuty On-Call escalated if unapproved in 5 minutes. |
| **P2 - HIGH** | Redundancy loss, container CrashLoopBackOff, localized 5xx errors ($>2\%$), or single node partition. | Autonomous parallel MCP triage; generate diagnostic telemetry report; notify `#incidents-high`. | $< 120$ seconds | SRE review within 15 minutes. |
| **P3 - MEDIUM** | Non-critical component warning, elevated memory trend without OOM, canary error elevation. | Background telemetry aggregation and automated commit diff correlation. | $< 5$ minutes | Reviewed during business hours. |

---

## 2. Ingestion Architecture & Alertmanager Setup

IncidentOps AI exposes `/api/v1/alerts/webhook` to ingest incoming alerts from Prometheus Alertmanager, Datadog Monitors, and PagerDuty Webhooks.

### Prometheus Alertmanager Configuration (`alertmanager.yml`)
```yaml
route:
  receiver: "incidentops-ai"
  group_by: ["alertname", "cluster", "service"]
  group_wait: 10s
  group_interval: 30s
  repeat_interval: 1h
  routes:
    - match:
        severity: critical
      receiver: "incidentops-ai"
      continue: true

receivers:
  - name: "incidentops-ai"
    webhook_configs:
      - url: "https://incidentops.internal.net/api/v1/alerts/webhook"
        send_resolved: false
        http_config:
          bearer_token: "${INCIDENTOPS_API_KEY}"
```

---

## 3. High Availability, Checkpoint Storage & State Recovery

### PostgreSQL Checkpointer Architecture
IncidentOps AI uses `PostgresSaver` backed by a multi-replica PostgreSQL cluster with connection pooling (`psycopg_pool.ConnectionPool`).
- **Checkpoint Retention:** State snapshots are retained for 90 days for post-mortem compliance.
- **Failover Behavior:** If the primary PostgreSQL instance fails, connection pools automatically reconnect to the standby replica. In-flight agent state is hydrated from the last committed node.
- **Disaster Recovery:** Automated hourly pg_dump snapshots stored in encrypted object storage (S3/GCS) with CMEK.

### Backup Command
```bash
pg_dump -h db-primary.internal -U incidentops -d incidentops_checkpoints -F c -b -v -f /backups/incidentops_$(date +%Y%m%d_%H%M%S).dump
```

---

## 4. Human-in-the-Loop (HITL) Gate Operations

### Cryptographic HMAC-SHA256 Authorization Protocol
All interactive remediation requests dispatched to Slack require an HMAC-SHA256 signature generated with `SLACK_SIGNING_SECRET`.

1. **Approval Window:** Operators have a 300-second timestamp tolerance window to approve or reject actions. Requests exceeding this threshold fail with `HTTP 403 Forbidden` to prevent replay attacks.
2. **Blast Radius Verification:** Every proposed remediation card includes:
   - Target namespace and Kubernetes deployment
   - Estimated MTTR (seconds)
   - Estimated in-flight session impact
   - Idempotent rollback verification command
3. **Audit Trail:** Every approved action is logged with the operator's cryptographic signature, user ID, timestamp, and stdout/stderr execution stream in the audit log.

### Emergency Bypass / Manual CLI Intervention
If the Slack webhook integration is unavailable, an authorized SRE can execute or approve remediation directly via the authenticated API:

```bash
curl -X POST "https://incidentops.internal.net/api/v1/incidents/inc-7d6f549c/approval" \
  -H "Authorization: Bearer ${INCIDENTOPS_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"approved": true, "signature": "sre-manual-override-key-secops", "notes": "Approved during Slack outage"}'
```

---

## 5. Fault Tolerance & Partial Telemetry Policies

1. **Worker Isolation:** Each MCP worker (`log_analyzer`, `metrics_correlator`, `codebase_inspector`) executes within an isolated task context with a strict 15-second timeout.
2. **Partial Telemetry Synthesis:** If an upstream telemetry provider (e.g. Grafana Loki) is unreachable or rate-limited, the worker captures the error diagnostic, lowers its confidence score, and allows the StateGraph to continue to `root_cause_synthesizer`. The engine synthesizes root cause from remaining modalities (metrics and Git diffs) rather than terminating the triage process.
3. **Loop Bound Safety:** The supervisor node enforces a deterministic loop bound (`iteration_count <= 3`). If root cause cannot be isolated within 3 iterations, exploration terminates immediately and escalates to human on-call with accumulated telemetry.

---

## 6. Observability, Health Probes & Metrics

The engine exposes standard Prometheus metrics at `/metrics` and Kubernetes probes:

- **Liveness Probe:** `GET /health/liveness` (Returns HTTP 200 if process is responsive)
- **Readiness Probe:** `GET /health/readiness` (Verifies PostgreSQL connection pool, LLM provider availability, and MCP tool health)
- **Prometheus Metrics:**
  - `incidentops_incidents_total{severity, status}`
  - `incidentops_triage_duration_seconds_bucket`
  - `incidentops_worker_duration_seconds{worker}`
  - `incidentops_remediations_total{action_type, status}`
  - `incidentops_mcp_tool_calls_total{tool, status}`
