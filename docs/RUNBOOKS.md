# Operations Runbooks

Incident documentation template: [INCIDENT_TEMPLATE.md](INCIDENT_TEMPLATE.md)

## On-Call Quickstart (First 10 Minutes)

### Goal
Stabilize service quickly, identify blast radius, and start evidence capture.

### First 10 Minutes Checklist
1. Acknowledge incident and assign incident commander.
2. Check API health and dependency health.
3. Check recent pipeline alerts and dispatch failures.
4. Confirm realtime worker status and DLQ growth.
5. Decide mitigation path: rollback, retry, or temporary degradation mode.
6. Post first stakeholder update with current impact and ETA window.

### Quick Commands
```powershell
# Health
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/v1/health
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/v1/health/dependencies

# Recent alerts
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/v1/pipelines/alerts?limit=20

# Dispatch status
Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8000/api/v1/pipelines/alerts/dispatch?limit=20' -Method Post

# Redis DLQ inspection
redis-cli XRANGE feature-events-dlq - + COUNT 50
```

### Escalation Trigger
- Escalate to SEV-1 if any of the following are true:
   - API health is non-OK for more than 5 minutes.
   - `notifications_failed` stays above 0 after one remediation cycle.
   - DLQ grows continuously for 10+ minutes with no successful reprocessing.

## 1. Alert Dispatch Failure Runbook

### Symptoms
- `POST /api/v1/pipelines/alerts/dispatch` returns `notifications_failed > 0`
- Notification entries contain transport errors

### Triage Steps
1. Check dispatch API response payload for `error` fields.
2. Verify channel configuration in `ALERT_CHANNELS_CSV`.
3. Validate transport credentials:
   - Slack: `SLACK_WEBHOOK_URL`
   - Email: `SMTP_*` values and sender format
4. Confirm outbound network access from API host.
5. Retry dispatch endpoint after configuration fix.

### Recovery Actions
- For Slack failures: rotate webhook and update environment.
- For SMTP failures: verify TLS mode, auth, relay policy, and sender domain.
- If transport remains down, keep simulated dispatch enabled in non-prod and open incident in prod.

### Verification
- Dispatch response shows `notifications_failed = 0`.
- `notifications_sent > 0` for channels with valid credentials.

## 2. Redis Stream DLQ Replay Runbook

### Context
The realtime worker retries failed events and sends terminal failures to the DLQ stream.

### Default Streams
- Main: `feature-events`
- DLQ: `feature-events-dlq`

### Inspect DLQ
```powershell
redis-cli XRANGE feature-events-dlq - + COUNT 50
```

### Replay Strategy
1. Review `_last_error` and payload fields.
2. Fix root cause in worker logic or downstream dependencies.
3. Re-publish corrected DLQ events to the main stream.
4. Remove/mark replayed DLQ messages via operational script.

### Example Replay (single event)
```powershell
# Example conceptual command; adjust fields to your payload schema.
redis-cli XADD feature-events * entity_id demo-1 amount 10.2 event_ts 2026-01-01T00:00:00Z
```

### Verification
- Worker ACKs replayed message in main stream.
- No new DLQ entry created for the replayed event.

## 3. Freshness SLO Breach Runbook

### Symptoms
- Alerts include `alert_type = freshness_slo`
- Lag exceeds `DEFAULT_FRESHNESS_LAG_SECONDS`

### Actions
1. Confirm upstream ingestion schedule and connector health.
2. Trigger pipeline run/backfill for delayed window.
3. Verify latest `event_ts` is advancing for impacted features.
4. Re-check alerts endpoint for breach reduction.

### Exit Criteria
- Freshness status back to `ok`.
- No new breach alerts for impacted feature after the next run window.
