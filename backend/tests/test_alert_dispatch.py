from app.services import alerts


class DummyResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self._rows


class DummyDb:
    def __init__(self):
        self.inserted = []

    def execute(self, stmt, params=None):
        sql = str(stmt)
        if "FROM quality_alerts" in sql:
            return DummyResult(
                [
                    {
                        "id": 1,
                        "run_id": "run-1",
                        "alert_type": "missing_rate",
                        "severity": "medium",
                        "details": {"column": "amount", "rate": 0.3},
                        "created_at": None,
                    }
                ]
            )
        if "INSERT INTO alert_notifications" in sql:
            self.inserted.append(params)
        return DummyResult([])

    def commit(self):
        return None


def test_dispatch_recent_alerts_simulated_when_not_configured(monkeypatch) -> None:
    db = DummyDb()
    monkeypatch.setattr(alerts.settings, "slack_webhook_url", None)
    monkeypatch.setattr(alerts.settings, "smtp_host", None)
    monkeypatch.setattr(alerts.settings, "smtp_sender", None)

    result = alerts.dispatch_recent_alerts(db, ["slack://team", "email://ops@example.com"], limit=5)

    assert result["alerts_considered"] == 1
    assert result["notifications_sent"] == 0
    assert result["notifications_simulated"] == 2
    assert result["notifications_failed"] == 0
    assert len(db.inserted) == 2


def test_dispatch_recent_alerts_sent_with_configured_transports(monkeypatch) -> None:
    db = DummyDb()
    monkeypatch.setattr(alerts.settings, "slack_webhook_url", "https://hooks.slack.test/123")
    monkeypatch.setattr(alerts.settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(alerts.settings, "smtp_sender", "noreply@example.com")

    monkeypatch.setattr(alerts, "_send_slack_webhook", lambda _msg: ("sent", None))
    monkeypatch.setattr(alerts, "_send_email_notification", lambda _recipient, _msg: ("sent", None))

    result = alerts.dispatch_recent_alerts(db, ["slack://team", "email://ops@example.com"], limit=5)

    assert result["notifications_sent"] == 2
    assert result["notifications_simulated"] == 0
    assert result["notifications_failed"] == 0
