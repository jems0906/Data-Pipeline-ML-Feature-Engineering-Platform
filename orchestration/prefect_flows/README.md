# Prefect Orchestration

## What this flow covers
- Scheduled batch ingestion
- Retry handling on ingestion task
- Quality status checks
- Freshness SLO evaluation
- Retraining trigger hook
- Backfill support pattern (historical query windows)

## Run locally
1. Install backend dependencies from `backend/requirements.txt`.
2. From repository root, run:
   - `python -m orchestration.prefect_flows.main_flow`
3. Optional Prefect server and deployments can be added with:
   - `prefect server start`
   - `prefect deployment build orchestration/prefect_flows/main_flow.py:batch_feature_pipeline -n local`
