# Deployment Environment Matrix

This matrix defines recommended configuration and operational controls for each environment.

## Environment Summary
| Area | Dev | Staging | Prod |
|---|---|---|---|
| Purpose | Local iteration | Pre-release validation | Live serving |
| Infrastructure | Local Docker compose | Managed Postgres/Redis + app host | HA managed Postgres/Redis + app host |
| Data Sources | Demo fallback + sandbox connectors | Real connectors with masked/sampled data | Real connectors with full governance |
| Alert Dispatch | Simulated allowed | Real Slack/email required | Real Slack/email required |
| Worker Mode | Optional local consumer | Mandatory consumer group | Mandatory multi-consumer with autoscaling |
| SLO Enforcement | Informational | Blocking for release criteria | Blocking with incident workflow |

## Required Environment Variables

### Shared
- APP_NAME
- ENVIRONMENT
- API_PREFIX
- POSTGRES_URL
- REDIS_URL
- DEFAULT_TRAIN_RATIO
- OUTLIER_ZSCORE_THRESHOLD
- MISSING_RATE_ALERT_THRESHOLD
- OUTLIER_RATE_ALERT_THRESHOLD
- DEFAULT_FRESHNESS_LAG_SECONDS
- ALERT_CHANNELS_CSV

### Connector Credentials
- BIGQUERY_PROJECT
- BIGQUERY_CREDENTIALS_PATH
- SNOWFLAKE_ACCOUNT
- SNOWFLAKE_USER
- SNOWFLAKE_PASSWORD
- SNOWFLAKE_WAREHOUSE
- SNOWFLAKE_DATABASE
- SNOWFLAKE_SCHEMA
- SNOWFLAKE_ROLE

### Alert Transport
- SLACK_WEBHOOK_URL
- SMTP_HOST
- SMTP_PORT
- SMTP_USERNAME
- SMTP_PASSWORD
- SMTP_USE_TLS
- SMTP_SENDER
- ALERT_DISPATCH_TIMEOUT_SECONDS

## Promotion Checklist
1. Backend tests pass: `py -3 -m pytest tests -q`
2. Frontend build passes: `npm run build`
3. Health checks pass (`/health`, `/health/dependencies`)
4. At least one pipeline run succeeds without demo fallback
5. Alert dispatch returns non-simulated notifications in target environment
6. Realtime consumer is active and processing stream events

## Runtime Commands

### API
```powershell
cd backend
$env:PYTHONPATH = (Get-Location).Path
py -3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Realtime Worker
```powershell
cd backend
py -3 -m app.workers.realtime_consumer
```
