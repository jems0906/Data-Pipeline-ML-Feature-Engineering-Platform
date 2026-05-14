# Data Pipeline & ML Feature Engineering Platform

End-to-end platform for ingesting, transforming, serving, and versioning ML-ready data with both batch and real-time capabilities.

## Architecture
- **Ingestion**: API, database, and warehouse adapters with retries, API auth, and run tracking
- **ETL/Transformation**: filtering, aggregation, feature engineering, lag/rolling features, missing/outlier handling
- **Feature Store**: PostgreSQL for history + Redis for low-latency online serving
- **ML-Ready Output**: Parquet/CSV/TFRecord exports, time-based train/test split, dataset versioning, data dictionary
- **Orchestration**: Prefect flow for scheduling/retries/freshness/retraining trigger hooks
- **Web Interface**: React UI for pipeline builder, quality dashboard, feature catalog, and usage tracking
- **Automation**: schema drift detection, feature suggestions, data drift checks, retraining trigger logic

## Project Structure
- `backend/`: FastAPI services and core data platform logic
- `frontend/`: React app for operations and discovery
- `orchestration/`: Prefect flows
- `infra/`: SQL and monitoring bootstrap artifacts
- `spark/`: Scala Spark ingestion template
- `data/`: local raw/processed/export/metadata storage

## Local Setup
### 1. Start infrastructure
```bash
docker compose up -d
```

Local host ports used by this project:
- PostgreSQL: `5433`
- Redis: `6380`

The extra infra schema in `infra/sql/init.sql` is applied by backend startup (app-managed bootstrap), so it does not rely on Docker entrypoint script mounts.

### 2. Backend
```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend
```bash
cd frontend
npm install
npm run dev
```

Windows note:
- This project includes a local workaround for environments where endpoint protection blocks native binaries inside `node_modules` paths.
- `frontend/.npmrc` sets `ignore-scripts=true` to avoid blocked postinstall native execution.
- Frontend scripts in `frontend/package.json` copy esbuild to `%TEMP%` and set `ESBUILD_BINARY_PATH` before starting Vite.
- Rollup is pinned to the wasm build through package overrides to avoid loading blocked native `.node` binaries.

### 4. Run orchestration flow
```bash
python -m orchestration.prefect_flows.main_flow
```

## Key API Endpoints
- `GET /api/v1/health`
- `POST /api/v1/pipelines/run`
- `POST /api/v1/pipelines/quality-report`
- `POST /api/v1/pipelines/realtime-event`
- `GET /api/v1/pipelines/alerts`
- `POST /api/v1/pipelines/alerts/dispatch`
- `POST /api/v1/pipelines/proofs/scale`
- `POST /api/v1/pipelines/proofs/warehouse-validation`
- `GET /api/v1/pipelines/lineage/graph`
- `GET /api/v1/features`
- `POST /api/v1/features/lookup`
- `GET /api/v1/features/usage`
- `POST /api/v1/features/usage`

`POST /api/v1/pipelines/run` now also materializes registered feature values into the feature store. The response includes:
- `feature_store.registered_features`: number of registered definitions from `transformations.register_features`
- `feature_store.materialized_values`: number of row-level values written during the run

To write values, include `transformations.register_features` entries with:
- `name`: feature column in transformed output
- `entity_key`: entity column name (defaults to `entity_id`)

After a successful run, `POST /api/v1/features/lookup` can return non-null values for matching entities and `as_of` timestamps.

`POST /api/v1/pipelines/realtime-event` writes incoming events to raw JSONL storage and publishes them to Redis Streams for near-real-time consumers.

`GET /api/v1/pipelines/alerts` returns recent quality and freshness alerts persisted by pipeline monitoring checks.

`POST /api/v1/pipelines/alerts/dispatch` fans out recent alerts to configured channels (`alert_channels_csv`) and records notification history.

Alert transport configuration:
- Slack delivery uses `SLACK_WEBHOOK_URL` for channels prefixed with `slack://`.
- Email delivery uses `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_USE_TLS`, and `SMTP_SENDER` for channels prefixed with `email://recipient@domain`.
- If transport credentials are not configured, dispatch records `simulated` notifications so local development still works.

`GET /api/v1/features/usage` and `POST /api/v1/features/usage` expose model-feature usage tracking for feature governance and reuse discovery.

For real-time stream consumption workers, run:
```bash
cd backend
py -3 -m app.workers.realtime_consumer
```

## Connector Configuration
### API ingestion auth
`source.config.auth` supports:
- `{"type": "bearer", "token": "..."}`
- `{"type": "basic", "username": "...", "password": "..."}`
- `{"type": "header", "header_name": "X-API-Key", "value": "..."}`
- `{"type": "query", "param_name": "api_key", "value": "..."}`

Optional API fields:
- `method`: HTTP method, default `GET`
- `headers`: extra request headers
- `params`: query string parameters
- `json`: JSON request body
- `records_path`: dot path for nested list payloads such as `result.items`

### BigQuery
- Set `BIGQUERY_PROJECT` and optionally `BIGQUERY_CREDENTIALS_PATH` in [backend/.env.example](backend/.env.example).
- Use `source_name: "bigquery"` and pass the SQL in `source.config.query`.

### Snowflake
- Set `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`, and optional warehouse/database/schema/role values in [backend/.env.example](backend/.env.example).
- Use `source_name: "snowflake"` and pass the SQL in `source.config.query`.

Demo UI and local flow runs keep `allow_demo_fallback: true` so the sample pipeline still works without warehouse credentials.

## Notes for Scale
- Use Spark-based transformations for petabyte-scale processing
- Store feature parquet in object storage / warehouse partitions
- Move scheduler to managed Prefect/Airflow deployment
- Add Great Expectations/Deequ for enterprise data quality
- Replace TFRecord placeholder with native TensorFlow serializer where needed

## Scale and Warehouse Proof Runs
Use these endpoints to generate measurable reports under `data/metadata/`:

1. Scale and 100+ model reuse proof:
```bash
Invoke-RestMethod -Method Post -ContentType "application/json" -Uri http://127.0.0.1:8010/api/v1/pipelines/proofs/scale -Body '{"model_count":120,"feature_pool_size":300,"features_per_model":20,"synthetic_rows":200000,"synthetic_partitions":8}'
```

2. Enterprise lineage graph materialization:
```bash
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8010/api/v1/pipelines/lineage/graph?limit=500"
```

3. Production warehouse validation (requires valid credentials in payload or env):
```bash
Invoke-RestMethod -Method Post -ContentType "application/json" -Uri http://127.0.0.1:8010/api/v1/pipelines/proofs/warehouse-validation -Body '{"checks":[{"source_name":"bigquery","query":"SELECT 1","config":{"project":"your-project"}},{"source_name":"snowflake","query":"SELECT 1","config":{"account":"your-account","user":"user","password":"password"}}]}'
```

## Known Windows Workarounds
- Some endpoint protection policies can block native binaries when executed from `node_modules` (for example `esbuild.exe` and native Rollup modules).
- This repo is configured to work around that behavior:
	- `frontend/.npmrc` uses `ignore-scripts=true`
	- Frontend scripts set `ESBUILD_BINARY_PATH` to `%TEMP%\\esbuild.exe`
	- `rollup` is overridden to `@rollup/wasm-node`
- If frontend commands fail after cleanup, run `npm install` again from `frontend/` and retry `npm run dev` or `npm run build`.

## Verification Checklist
Run these checks after setup or before handoff:

1. Infrastructure:
```bash
docker compose up -d
docker compose ps
```

2. Backend tests:
```bash
cd backend
$env:PYTHONPATH = (Get-Location).Path
py -3 -m pytest tests -q
```

3. Backend runtime:
```bash
py -3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

4. Frontend runtime/build:
```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
npm run build
```

5. Health probes:
```bash
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/v1/health
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/v1/health/dependencies
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5173
```

## Production Operations
- Environment matrix: [docs/DEPLOYMENT_MATRIX.md](docs/DEPLOYMENT_MATRIX.md)
- Runbooks (alert failures, DLQ replay, freshness breaches): [docs/RUNBOOKS.md](docs/RUNBOOKS.md)
- On-call quickstart (first 10 minutes): [docs/RUNBOOKS.md](docs/RUNBOOKS.md#on-call-quickstart-first-10-minutes)
- Incident report template: [docs/INCIDENT_TEMPLATE.md](docs/INCIDENT_TEMPLATE.md)
- Release changelog: [docs/CHANGELOG.md](docs/CHANGELOG.md)
- Release notes snippet (PR/announcement): [docs/RELEASE_NOTES_SNIPPET.md](docs/RELEASE_NOTES_SNIPPET.md)
- Team run checklist: [docs/TEAM_RUN_CHECKLIST.md](docs/TEAM_RUN_CHECKLIST.md)
