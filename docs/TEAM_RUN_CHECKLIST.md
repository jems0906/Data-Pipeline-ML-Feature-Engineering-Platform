# Team Run Checklist

Use this checklist for local onboarding, smoke validation, and release handoff.

## 1. Infrastructure
```powershell
cd "d:\project\Data Pipeline & ML Feature Engineering Platform"
docker compose up -d
docker compose ps
```

Expected:
- Postgres healthy on host port `5433`
- Redis healthy on host port `6380`

## 2. Backend Setup and Tests
```powershell
cd backend
copy .env.example .env
$env:PYTHONPATH = (Get-Location).Path
py -3 -m pytest tests -q
```

Expected:
- Tests pass

## 3. Backend Runtime
```powershell
cd backend
$env:PYTHONPATH = (Get-Location).Path
py -3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Health checks:
```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/v1/health
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/v1/health/dependencies
```

## 4. Frontend Runtime and Build
```powershell
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
npm run build
```

Expected:
- Dev endpoint responds at `http://127.0.0.1:5173`
- Build completes successfully

## 5. Pipeline Smoke
```powershell
$payload = @{ run_id = 'team-smoke-001'; source = @{ source_type = 'warehouse'; source_name = 'bigquery'; config = @{ query = 'SELECT 1'; allow_demo_fallback = $true } }; transformations = @{ required_columns = @('entity_id','event_ts','amount'); register_features = @(@{ name = 'amount'; entity_key = 'entity_id'; dtype = 'float' }) } } | ConvertTo-Json -Depth 12
Invoke-WebRequest -UseBasicParsing -Uri http://127.0.0.1:8000/api/v1/pipelines/run -Method Post -ContentType 'application/json' -Body $payload
```

Expected:
- Pipeline response includes exports, quality metrics, and feature_store counters

## 6. Realtime and Alerting Smoke
```powershell
$evt = @{ run_id = 'team-rt-001'; source_name = 'webhook'; stream_name = 'feature-events'; event = @{ entity_id = 'demo-rt-1'; event_ts = '2026-01-01T00:00:00Z'; amount = 11.5 } } | ConvertTo-Json -Depth 8
Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8000/api/v1/pipelines/realtime-event' -Method Post -ContentType 'application/json' -Body $evt
Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8000/api/v1/pipelines/alerts?limit=10'
Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8000/api/v1/pipelines/alerts/dispatch?limit=10' -Method Post
```

Expected:
- Realtime endpoint returns stream id
- Alerts endpoint returns recent alerts (if any)
- Dispatch endpoint returns sent/simulated/failed counters

## 7. Optional Worker Run
```powershell
cd backend
py -3 -m app.workers.realtime_consumer
```

Expected:
- Worker joins stream and processes events
