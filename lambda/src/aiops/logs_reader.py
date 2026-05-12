"""CloudWatch Logs readers for Nginx evidence and rechecks."""

from __future__ import annotations

import logging
import time

from botocore.exceptions import BotoCoreError, ClientError

from . import aws_clients


ERROR_PATTERNS = (" 5", "error", "exception", "timeout", "upstream")
logger = logging.getLogger(__name__)


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
        except (BotoCoreError, ClientError) as exc:
            logger.warning(
                "cloudwatch_log_read_failed",
                extra={"log_group": group, "instance_id": instance_id, "error": str(exc)},
            )
            continue
        for event in response.get("events", []):
            message = event.get("message", "")
            if any(pattern in message.lower() for pattern in ERROR_PATTERNS):
                messages.append(message[:500])
    return {"error_count": len(messages), "samples": messages[:5]}
