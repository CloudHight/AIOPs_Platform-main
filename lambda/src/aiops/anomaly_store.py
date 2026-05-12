"""DynamoDB anomaly persistence and idempotency."""

from __future__ import annotations

from typing import Any

from . import aws_clients
from .models import (
    AnomalySignal,
    AnomalyStatus,
    OPEN_STATUSES,
    anomaly_id,
    correlation_id,
    decimalize,
    epoch_seconds,
    utc_now,
)


class AnomalyStore:
    def __init__(self, table_name: str, table=None) -> None:
        self.table = table or aws_clients.dynamodb_resource().Table(table_name)

    def get(self, item_id: str) -> dict[str, Any] | None:
        response = self.table.get_item(Key={"anomaly_id": item_id})
        return response.get("Item")

    def record_detection(self, environment: str, signal: AnomalySignal, ttl_days: int) -> tuple[dict[str, Any], bool]:
        item_id = anomaly_id(environment, signal.instance_id, signal.anomaly_type)
        corr_id = correlation_id(environment, signal.instance_id, signal.anomaly_type)
        existing = self.get(item_id)
        now = utc_now()
        ttl = epoch_seconds(ttl_days * 86400)
        if existing and existing.get("status") in {status.value for status in OPEN_STATUSES}:
            self.table.update_item(
                Key={"anomaly_id": item_id},
                UpdateExpression=(
                    "SET #status = :status, last_seen_at = :now, last_score = :score, "
                    "severity = :severity, evidence = :evidence, ttl = :ttl "
                    "ADD detection_count :one"
                ),
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues=decimalize({
                    ":status": AnomalyStatus.RECORDED.value,
                    ":now": now,
                    ":score": signal.score,
                    ":severity": signal.severity,
                    ":evidence": signal.evidence,
                    ":ttl": ttl,
                    ":one": 1,
                }),
            )
            updated = self.get(item_id) or existing
            return updated, False

        item = decimalize({
            "anomaly_id": item_id,
            "correlation_id": corr_id,
            "environment": environment,
            "instance_id": signal.instance_id,
            "model_type": signal.anomaly_type,
            "anomaly_type": signal.anomaly_type,
            "status": AnomalyStatus.RECORDED.value,
            "timestamp": now,
            "detected_at": now,
            "last_seen_at": now,
            "last_score": signal.score,
            "threshold": signal.threshold,
            "severity": signal.severity,
            "model_endpoint": signal.model_endpoint,
            "evidence": signal.evidence,
            "detection_count": 1,
            "remediation_attempts": 0,
            "ttl": ttl,
        })
        self.table.put_item(Item=item)
        return item, True

    def mark(self, item_id: str, status: AnomalyStatus, **fields: Any) -> dict[str, Any]:
        updates = {"status": status.value, "updated_at": utc_now(), **fields}
        names = {"#status": "status"}
        expressions = ["#status = :status"]
        values = {":status": updates.pop("status")}
        for index, (key, value) in enumerate(updates.items()):
            name_token = f"#n{index}"
            value_token = f":v{index}"
            names[name_token] = key
            values[value_token] = decimalize(value)
            expressions.append(f"{name_token} = {value_token}")
        response = self.table.update_item(
            Key={"anomaly_id": item_id},
            UpdateExpression="SET " + ", ".join(expressions),
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
            ReturnValues="ALL_NEW",
        )
        return response["Attributes"]

    def increment_remediation_attempt(self, item_id: str) -> dict[str, Any]:
        response = self.table.update_item(
            Key={"anomaly_id": item_id},
            UpdateExpression="SET last_remediation_attempt_at = :now ADD remediation_attempts :one",
            ExpressionAttributeValues={":now": utc_now(), ":one": 1},
            ReturnValues="ALL_NEW",
        )
        return response["Attributes"]
