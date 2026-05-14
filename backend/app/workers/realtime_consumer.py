from __future__ import annotations

import json
import os
from collections.abc import Callable

import redis

from app.core.config import settings


class RedisStreamConsumer:
    def __init__(
        self,
        stream_name: str = "feature-events",
        group_name: str = "feature-workers",
        consumer_name: str = "worker-1",
        dlq_stream_name: str = "feature-events-dlq",
        max_retries: int = 3,
        batch_size: int = 10,
        block_ms: int = 2000,
    ) -> None:
        self.stream_name = stream_name
        self.group_name = group_name
        self.consumer_name = consumer_name
        self.dlq_stream_name = dlq_stream_name
        self.max_retries = max_retries
        self.batch_size = batch_size
        self.block_ms = block_ms
        self.redis_client = redis.from_url(settings.redis_url, decode_responses=True)

    def ensure_group(self) -> None:
        try:
            self.redis_client.xgroup_create(self.stream_name, self.group_name, id="0", mkstream=True)
        except redis.ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    def _to_dlq_payload(self, fields: dict[str, str], message_id: str, error: str) -> dict[str, str]:
        payload = dict(fields)
        payload["_source_message_id"] = message_id
        payload["_last_error"] = error
        return payload

    def run_once(self, handler: Callable[[dict[str, str]], None]) -> int:
        records = self.redis_client.xreadgroup(
            self.group_name,
            self.consumer_name,
            {self.stream_name: ">"},
            count=self.batch_size,
            block=self.block_ms,
        )
        if not records:
            return 0

        processed = 0
        for _stream, messages in records:
            for message_id, fields in messages:
                try:
                    handler(fields)
                    self.redis_client.xack(self.stream_name, self.group_name, message_id)
                except Exception as exc:  # noqa: BLE001
                    retry_count = int(fields.get("_retry_count", "0")) + 1
                    if retry_count > self.max_retries:
                        dlq_payload = self._to_dlq_payload(fields, message_id, str(exc))
                        self.redis_client.xadd(self.dlq_stream_name, dlq_payload)
                    else:
                        next_payload = dict(fields)
                        next_payload["_retry_count"] = str(retry_count)
                        next_payload["_last_error"] = str(exc)
                        self.redis_client.xadd(self.stream_name, next_payload)
                    self.redis_client.xack(self.stream_name, self.group_name, message_id)
                processed += 1

        return processed

    def run_forever(self, handler: Callable[[dict[str, str]], None]) -> None:
        self.ensure_group()
        while True:
            self.run_once(handler)


def _default_handler(fields: dict[str, str]) -> None:
    # Placeholder processing hook. In production, replace with transformation/inference handoff.
    _ = fields


def main() -> None:
    consumer = RedisStreamConsumer(
        stream_name=os.getenv("REALTIME_STREAM_NAME", "feature-events"),
        group_name=os.getenv("REALTIME_GROUP_NAME", "feature-workers"),
        consumer_name=os.getenv("REALTIME_CONSUMER_NAME", "worker-1"),
        dlq_stream_name=os.getenv("REALTIME_DLQ_STREAM_NAME", "feature-events-dlq"),
        max_retries=int(os.getenv("REALTIME_MAX_RETRIES", "3")),
        batch_size=int(os.getenv("REALTIME_BATCH_SIZE", "10")),
        block_ms=int(os.getenv("REALTIME_BLOCK_MS", "2000")),
    )
    consumer.run_forever(_default_handler)


if __name__ == "__main__":
    main()
