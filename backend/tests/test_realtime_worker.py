from app.workers.realtime_consumer import RedisStreamConsumer


class FakeRedis:
    def __init__(self) -> None:
        self.group_created = False
        self.stream_messages: list[tuple[str, dict[str, str]]] = []
        self.dlq_messages: list[dict[str, str]] = []
        self.acked: list[str] = []

    def xgroup_create(self, *_args, **_kwargs) -> None:
        self.group_created = True

    def xreadgroup(self, _group, _consumer, _streams, count=10, block=0):
        _ = count
        _ = block
        if not self.stream_messages:
            return []
        batch = self.stream_messages[:1]
        self.stream_messages = self.stream_messages[1:]
        return [("feature-events", batch)]

    def xack(self, _stream, _group, message_id):
        self.acked.append(message_id)

    def xadd(self, stream, fields):
        if stream == "feature-events-dlq":
            self.dlq_messages.append(dict(fields))
            return "dlq-1"
        self.stream_messages.append((f"retry-{len(self.stream_messages)+1}", dict(fields)))
        return "retry-id"


def test_worker_acknowledges_on_success() -> None:
    consumer = RedisStreamConsumer(max_retries=2)
    fake = FakeRedis()
    fake.stream_messages.append(("1-0", {"entity_id": "a1", "amount": "10.2"}))
    consumer.redis_client = fake

    seen: list[dict[str, str]] = []

    def handler(fields: dict[str, str]) -> None:
        seen.append(fields)

    count = consumer.run_once(handler)

    assert count == 1
    assert seen[0]["entity_id"] == "a1"
    assert fake.acked == ["1-0"]
    assert not fake.dlq_messages


def test_worker_retries_then_sends_to_dlq() -> None:
    consumer = RedisStreamConsumer(max_retries=1)
    fake = FakeRedis()
    fake.stream_messages.append(("1-0", {"entity_id": "a1"}))
    consumer.redis_client = fake

    def handler(_fields: dict[str, str]) -> None:
        raise ValueError("boom")

    first = consumer.run_once(handler)
    second = consumer.run_once(handler)

    assert first == 1
    assert second == 1
    assert len(fake.dlq_messages) == 1
    assert fake.dlq_messages[0]["_source_message_id"] == "retry-1"
    assert "boom" in fake.dlq_messages[0]["_last_error"]
