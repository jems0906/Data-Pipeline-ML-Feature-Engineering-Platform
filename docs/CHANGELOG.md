# Changelog

## v0.4.0 - 2026-05-14

### Added
- Native TFRecord export writer with TFRecord framing and checksum masking.
- Feature usage APIs (`GET/POST /features/usage`) with persistence.
- Realtime ingestion endpoint (`POST /pipelines/realtime-event`) with Redis Streams publish.
- Realtime consumer worker with retry handling and DLQ routing.
- Quality/freshness alert persistence and listing (`GET /pipelines/alerts`).
- Alert dispatch endpoint (`POST /pipelines/alerts/dispatch`) with Slack/SMTP transport adapters and simulation fallback.
- Drag-and-drop stage ordering in pipeline builder UI.
- UI controls for realtime event send and alert dispatch summary.

### Changed
- Pipeline run response expanded with feature usage and alert counters.
- Frontend docs and setup guidance expanded for Windows and operations workflows.

### Validated
- Backend tests passing after feature additions.
- Frontend production build passing.
- Live API checks validated for pipeline run, realtime event, alerts, and dispatch.

## v0.3.0 - 2026-05-14

### Added
- Point-in-time feature value materialization during pipeline runs.
- Dependency health endpoint improvements.
- Standalone UI and Vite parity for health strip components.

### Fixed
- Windows Vite/esbuild execution workaround via temp binary path.
- Rollup native module fallback with wasm override.
- SQL bootstrap stability via backend-managed initialization.

## v0.2.0 - 2026-05-14

### Added
- Core ingestion, transformation, validation, export, and feature store APIs.
- Prefect orchestration flow scaffold.
- React pages for pipeline, quality, feature catalog, and usage views.

## v0.1.0 - 2026-05-14

### Added
- Initial monorepo scaffold for backend, frontend, orchestration, infra, and spark template.
