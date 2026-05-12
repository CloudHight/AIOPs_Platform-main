"""CloudWatch Logs readers for Nginx evidence and rechecks."""

from __future__ import annotations

import time

from . import aws_clients


ERROR_PATTERNS = (" 5", "error", "exception", "timeout", "upstream")


def recent_nginx_errors(instance_id: str, minutes: int = 5, client=None) -> dict[str, object]:
    logs = client or aws_clients.logs()
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - minutes * 60 * 1000
    messages: list[str] = []
    groups = ["nginx/access.log", "nginx/error.log"]

    for group in groups:
        try:
            response = logs.filter_log_events(
                logGroupName=group,
                startTime=start_ms,
                endTime=now_ms,
                filterPattern=instance_id,
                limit=25,
            )
        except Exception:
            continue
        for event in response.get("events", []):
            message = event.get("message", "")
            if any(pattern in message.lower() for pattern in ERROR_PATTERNS):
                messages.append(message[:500])
    return {"error_count": len(messages), "samples": messages[:5]}
