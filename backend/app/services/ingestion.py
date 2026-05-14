from __future__ import annotations

import json
from base64 import b64encode
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
import redis
from sqlalchemy import text
from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.models.feature_store import IngestionRun


class IngestionService:
    def __init__(self, db: Session):
        self.db = db

    def _build_api_request_kwargs(self, config: dict[str, Any]) -> dict[str, Any]:
        params = config.get("params", {})
        headers = dict(config.get("headers", {}))
        auth_config = config.get("auth", {})
        auth_type = auth_config.get("type", "none").lower()

        if auth_type == "bearer":
            token = auth_config.get("token")
            if not token:
                raise ValueError("API bearer auth requires auth.token")
            headers["Authorization"] = f"Bearer {token}"
        elif auth_type == "basic":
            username = auth_config.get("username")
            password = auth_config.get("password")
            if username is None or password is None:
                raise ValueError("API basic auth requires auth.username and auth.password")
            encoded = b64encode(f"{username}:{password}".encode("utf-8")).decode("utf-8")
            headers["Authorization"] = f"Basic {encoded}"
        elif auth_type == "header":
            header_name = auth_config.get("header_name")
            value = auth_config.get("value")
            if not header_name or value is None:
                raise ValueError("API header auth requires auth.header_name and auth.value")
            headers[header_name] = str(value)
        elif auth_type == "query":
            param_name = auth_config.get("param_name")
            value = auth_config.get("value")
            if not param_name or value is None:
                raise ValueError("API query auth requires auth.param_name and auth.value")
            params[param_name] = value
        elif auth_type not in {"", "none"}:
            raise ValueError(f"Unsupported API auth type: {auth_type}")

        return {
            "params": params,
            "headers": headers,
            "timeout": config.get("timeout_seconds", 30),
        }

    def _coerce_payload_to_frame(self, payload: Any, records_path: str | None = None) -> pd.DataFrame:
        if records_path:
            current = payload
            for segment in records_path.split("."):
                if not isinstance(current, dict) or segment not in current:
                    raise ValueError(f"records_path segment not found: {segment}")
                current = current[segment]
            payload = current

        if isinstance(payload, dict):
            payload = payload.get("data", payload)

        if isinstance(payload, list):
            return pd.DataFrame(payload)
        if isinstance(payload, dict):
            return pd.DataFrame([payload])
        raise ValueError("API payload must resolve to a JSON object or list of objects")

    def _ingest_bigquery_batch(self, query: str, config: dict[str, Any]) -> pd.DataFrame:
        try:
            from google.cloud import bigquery
            from google.oauth2 import service_account
        except ImportError as exc:  # pragma: no cover - depends on optional package
            raise ImportError(
                "BigQuery ingestion requires google-cloud-bigquery. Install backend dependencies again after updating requirements."
            ) from exc

        credentials = None
        project = config.get("project") or settings.bigquery_project
        credentials_path = config.get("credentials_path") or settings.bigquery_credentials_path
        credentials_json = config.get("credentials_json")

        if credentials_json:
            info = json.loads(credentials_json) if isinstance(credentials_json, str) else credentials_json
            credentials = service_account.Credentials.from_service_account_info(info)
        elif credentials_path:
            credentials = service_account.Credentials.from_service_account_file(credentials_path)

        client = bigquery.Client(project=project, credentials=credentials)
        return client.query(query).result().to_dataframe(create_bqstorage_client=False)

    def _ingest_snowflake_batch(self, query: str, config: dict[str, Any]) -> pd.DataFrame:
        try:
            import snowflake.connector
        except ImportError as exc:  # pragma: no cover - depends on optional package
            raise ImportError(
                "Snowflake ingestion requires snowflake-connector-python[pandas]. Install backend dependencies again after updating requirements."
            ) from exc

        connection_kwargs = {
            "account": config.get("account") or settings.snowflake_account,
            "user": config.get("user") or settings.snowflake_user,
            "password": config.get("password") or settings.snowflake_password,
            "warehouse": config.get("warehouse") or settings.snowflake_warehouse,
            "database": config.get("database") or settings.snowflake_database,
            "schema": config.get("schema") or settings.snowflake_schema,
            "role": config.get("role") or settings.snowflake_role,
        }
        missing = [key for key, value in connection_kwargs.items() if key in {"account", "user", "password"} and not value]
        if missing:
            raise ValueError(f"Snowflake ingestion missing required connection fields: {', '.join(missing)}")

        with snowflake.connector.connect(**{k: v for k, v in connection_kwargs.items() if v}) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)
                frame = cursor.fetch_pandas_all()
        return frame

    def _start_run(self, run_id: str, source_name: str) -> IngestionRun:
        run = IngestionRun(run_id=run_id, source_name=source_name, status="running")
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def _finish_run(self, run: IngestionRun, records: int, error: str | None = None) -> None:
        run.status = "failed" if error else "completed"
        run.records_ingested = records
        run.error_message = error
        run.ended_at = datetime.utcnow()
        self.db.add(run)
        self.db.commit()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    def ingest_api_batch(self, url: str, config: dict[str, Any]) -> pd.DataFrame:
        request_kwargs = self._build_api_request_kwargs(config)
        method = config.get("method", "GET").upper()
        json_body = config.get("json")
        response = httpx.request(method, url, json=json_body, **request_kwargs)
        response.raise_for_status()
        payload = response.json()
        return self._coerce_payload_to_frame(payload, records_path=config.get("records_path"))

    def ingest_database_batch(self, sql_query: str) -> pd.DataFrame:
        rows = self.db.execute(text(sql_query)).mappings().all()
        return pd.DataFrame(rows)

    def ingest_warehouse_batch(self, source: str, query: str, config: dict[str, Any]) -> pd.DataFrame:
        normalized_source = source.lower()
        allow_demo_fallback = config.get("allow_demo_fallback", False)
        if normalized_source == "bigquery":
            has_bigquery_config = any(
                [
                    config.get("credentials_json"),
                    config.get("credentials_path"),
                    config.get("project"),
                    settings.bigquery_credentials_path,
                    settings.bigquery_project,
                ]
            )
            if allow_demo_fallback and not has_bigquery_config:
                return pd.DataFrame(
                    [
                        {
                            "entity_id": "demo-1",
                            "event_ts": datetime.now(UTC).isoformat(),
                            "amount": 10.2,
                            "warehouse": source,
                            "query": query,
                        }
                    ]
                )
            return self._ingest_bigquery_batch(query, config)
        if normalized_source == "snowflake":
            has_snowflake_config = any(
                [
                    config.get("account"),
                    config.get("user"),
                    config.get("password"),
                    settings.snowflake_account,
                    settings.snowflake_user,
                    settings.snowflake_password,
                ]
            )
            if allow_demo_fallback and not has_snowflake_config:
                return pd.DataFrame(
                    [
                        {
                            "entity_id": "demo-1",
                            "event_ts": datetime.now(UTC).isoformat(),
                            "amount": 10.2,
                            "warehouse": source,
                            "query": query,
                        }
                    ]
                )
            return self._ingest_snowflake_batch(query, config)
        if allow_demo_fallback:
            return pd.DataFrame(
                [
                    {
                        "entity_id": "demo-1",
                        "event_ts": datetime.now(UTC).isoformat(),
                        "amount": 10.2,
                        "warehouse": source,
                        "query": query,
                    }
                ]
            )
        raise ValueError(f"Unsupported warehouse source: {source}. Expected 'bigquery' or 'snowflake'.")

    def ingest_realtime_event(self, run_id: str, source_name: str, event: dict) -> Path:
        run = self._start_run(run_id=run_id, source_name=source_name)
        try:
            output_dir = Path(settings.raw_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"{run_id}.jsonl"
            with output_file.open("a", encoding="utf-8") as fp:
                fp.write(f"{event}\n")
            self._finish_run(run, records=1)
            return output_file
        except Exception as exc:  # noqa: BLE001
            self._finish_run(run, records=0, error=str(exc))
            raise

    def publish_realtime_event(self, stream_name: str, event: dict) -> str:
        client = redis.from_url(settings.redis_url, decode_responses=True)
        payload = {k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) for k, v in event.items()}
        return str(client.xadd(stream_name, payload))

    def run_ingestion(self, run_id: str, source_type: str, source_name: str, config: dict) -> pd.DataFrame:
        run = self._start_run(run_id=run_id, source_name=source_name)
        try:
            if source_type == "api":
                frame = self.ingest_api_batch(url=config["url"], config=config)
            elif source_type == "database":
                frame = self.ingest_database_batch(sql_query=config["query"])
            elif source_type == "warehouse":
                if "rows" in config:
                    frame = pd.DataFrame(config["rows"])
                else:
                    frame = self.ingest_warehouse_batch(source=source_name, query=config["query"], config=config)
            else:
                raise ValueError(f"Unsupported source_type: {source_type}")

            self._finish_run(run, records=len(frame.index))
            return frame
        except Exception as exc:  # noqa: BLE001
            self._finish_run(run, records=0, error=str(exc))
            raise
