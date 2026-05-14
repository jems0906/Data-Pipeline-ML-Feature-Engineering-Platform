from __future__ import annotations

import json
import smtplib
from email.message import EmailMessage
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings


def _format_message(alert: dict[str, Any], channel: str) -> str:
    prefix = "[ALERT]"
    return f"{prefix} channel={channel} run_id={alert['run_id']} type={alert['alert_type']} severity={alert['severity']} details={json.dumps(alert['details'])}"


def _send_slack_webhook(message: str) -> tuple[str, str | None]:
    if not settings.slack_webhook_url:
        return "simulated", "SLACK_WEBHOOK_URL not configured"

    try:
        response = httpx.post(
            settings.slack_webhook_url,
            json={"text": message},
            timeout=settings.alert_dispatch_timeout_seconds,
        )
        response.raise_for_status()
        return "sent", None
    except Exception as exc:  # noqa: BLE001
        return "failed", str(exc)


def _send_email_notification(recipient: str, message: str) -> tuple[str, str | None]:
    if not settings.smtp_host or not settings.smtp_sender:
        return "simulated", "SMTP_HOST or SMTP_SENDER not configured"

    try:
        mail = EmailMessage()
        mail["Subject"] = "Data Platform Alert"
        mail["From"] = settings.smtp_sender
        mail["To"] = recipient
        mail.set_content(message)

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=settings.alert_dispatch_timeout_seconds) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_username and settings.smtp_password:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(mail)

        return "sent", None
    except Exception as exc:  # noqa: BLE001
        return "failed", str(exc)


def _dispatch_to_channel(channel: str, message: str) -> tuple[str, str | None]:
    if channel.startswith("slack://"):
        return _send_slack_webhook(message)

    if channel.startswith("email://"):
        recipient = channel.replace("email://", "", 1).strip()
        if not recipient:
            return "failed", "email channel missing recipient"
        return _send_email_notification(recipient, message)

    return "simulated", f"unsupported channel protocol: {channel}"


def dispatch_recent_alerts(db: Session, channels: list[str], limit: int = 20) -> dict:
    rows = db.execute(
        text(
            """
            SELECT id, run_id, alert_type, severity, details, created_at
            FROM quality_alerts
            ORDER BY created_at DESC
            LIMIT :limit
            """
        ),
        {"limit": max(1, min(limit, 500))},
    ).mappings()

    alerts = list(rows)
    sent = 0
    simulated = 0
    failed = 0
    notifications: list[dict] = []

    for alert in alerts:
        for channel in channels:
            message = _format_message(alert, channel)
            status, error = _dispatch_to_channel(channel, message)
            db.execute(
                text(
                    """
                    INSERT INTO alert_notifications(alert_id, channel, status, message)
                    VALUES (:alert_id, :channel, :status, :message)
                    """
                ),
                {
                    "alert_id": alert["id"],
                    "channel": channel,
                    "status": status,
                    "message": message if not error else f"{message} | error={error}",
                },
            )
            notifications.append(
                {
                    "alert_id": alert["id"],
                    "channel": channel,
                    "status": status,
                    "message": message,
                    "error": error,
                }
            )
            if status == "sent":
                sent += 1
            elif status == "simulated":
                simulated += 1
            else:
                failed += 1

    db.commit()
    return {
        "alerts_considered": len(alerts),
        "notifications_sent": sent,
        "notifications_simulated": simulated,
        "notifications_failed": failed,
        "channels": channels,
        "notifications": notifications,
    }
