"""Grace-period scheduling and safe remediation execution."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

from . import aws_clients
from .config import RuntimeConfig
from .discovery import instance_has_required_tags
from .models import RemediationMessage, epoch_seconds, utc_now


APPROVED_LOG_REMEDIATION_COMMANDS = [
    "sudo systemctl restart nginx",
    "if command -v docker >/dev/null 2>&1; then docker ps --format '{{.Names}}' | grep -E '^aiops|testapp' | xargs -r docker restart; fi",
]


class RemediationScheduler:
    def __init__(self, queue_url: str, client=None) -> None:
        self.queue_url = queue_url
        self.client = client or aws_clients.sqs()

    def schedule(self, message: RemediationMessage, grace_period_minutes: int) -> None:
        delay = min(max(grace_period_minutes * 60, 0), 900)
        self.client.send_message(
            QueueUrl=self.queue_url,
            DelaySeconds=delay,
            MessageBody=json.dumps(message.to_payload()),
            MessageAttributes={
                "correlation_id": {"DataType": "String", "StringValue": message.correlation_id},
                "anomaly_type": {"DataType": "String", "StringValue": message.anomaly_type},
            },
        )

    def reschedule_until_due(self, payload: dict[str, Any]) -> bool:
        scheduled_for = int(payload.get("scheduled_for_epoch", 0))
        remaining = scheduled_for - int(time.time())
        if remaining <= 0:
            return False
        self.client.send_message(
            QueueUrl=self.queue_url,
            DelaySeconds=min(remaining, 900),
            MessageBody=json.dumps(payload),
        )
        return True


class Remediator:
    def __init__(self, config: RuntimeConfig, ec2_client=None, ssm_client=None) -> None:
        self.config = config
        self.ec2 = ec2_client or aws_clients.ec2()
        self.ssm = ssm_client or aws_clients.ssm()

    def execute(self, anomaly: dict[str, Any]) -> dict[str, Any]:
        if not self.config.auto_remediation_enabled:
            return self._skipped("auto_remediation_disabled")
        if self.config.dry_run:
            return self._skipped("dry_run_enabled")

        attempts = int(anomaly.get("remediation_attempts", 0))
        if attempts >= self.config.max_remediation_attempts:
            return self._skipped("attempt_limit_reached")
        last_attempt = _parse_datetime(anomaly.get("last_remediation_attempt_at"))
        if last_attempt:
            elapsed_minutes = (datetime.now(timezone.utc) - last_attempt).total_seconds() / 60
            if elapsed_minutes < self.config.remediation_cooldown_minutes:
                return self._skipped("cooldown_active")

        instance_id = anomaly["instance_id"]
        if not instance_has_required_tags(
            instance_id,
            self.config.instance_tag_key,
            self.config.instance_tag_value,
            client=self.ec2,
        ):
            return self._skipped("instance_not_eligible")

        anomaly_type = anomaly["anomaly_type"]
        if anomaly_type == "cpu":
            self.ec2.reboot_instances(InstanceIds=[instance_id])
            return {"status": "executed", "action": "ec2_reboot", "executed_at": utc_now()}

        if anomaly_type == "log":
            response = self.ssm.send_command(
                InstanceIds=[instance_id],
                DocumentName="AWS-RunShellScript",
                Parameters={"commands": APPROVED_LOG_REMEDIATION_COMMANDS},
                Comment=f"AIOps remediation correlation {anomaly['correlation_id']}",
            )
            return {
                "status": "executed",
                "action": "restart_nginx_and_app",
                "ssm_command_id": response["Command"]["CommandId"],
                "executed_at": utc_now(),
            }

        return self._skipped(f"unsupported_anomaly_type_{anomaly_type}")

    @staticmethod
    def _skipped(reason: str) -> dict[str, Any]:
        return {
            "status": "skipped",
            "reason": reason,
            "executed_at": utc_now(),
            "next_allowed_epoch": epoch_seconds(0),
        }


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
