# Release Notes Snippet

## Data Pipeline & ML Feature Engineering Platform - v0.4.0

This release delivers production-grade improvements across ingestion, feature serving, alerting, realtime processing, UI controls, and operational readiness.

### Highlights
- Added native TFRecord export support.
- Added feature usage APIs and persistent model-feature usage tracking.
- Added realtime ingestion endpoint backed by Redis Streams.
- Added realtime worker with retry and DLQ behavior.
- Added quality/freshness alert persistence and alert dispatch endpoint.
- Added Slack/SMTP alert transport adapters with simulation fallback in non-configured environments.
- Added drag-and-drop pipeline stage ordering in UI.
- Added dashboard controls for alert dispatch and realtime event triggering.
- Added deployment matrix, runbooks, incident template, and changelog docs.

### API Additions
- `POST /api/v1/pipelines/realtime-event`
- `GET /api/v1/pipelines/alerts`
- `POST /api/v1/pipelines/alerts/dispatch`
- `GET /api/v1/features/usage`
- `POST /api/v1/features/usage`

### Validation
- Backend test suite passing (latest run: 23 passed).
- Frontend production build passing.
- Health checks passing for API and dependencies.

### Notes
- Alert dispatch returns `sent`, `simulated`, and `failed` counters.
- In local/dev without transport credentials, dispatch operates in simulated mode by design.
