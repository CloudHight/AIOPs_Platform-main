"""Shared incident and remediation data models."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any


class AnomalyStatus(StrEnum):
    DETECTED = "DETECTED"
    RECORDED = "RECORDED"
    ALERTED = "ALERTED"
    TICKETED = "TICKETED"
    GRACE_PERIOD = "GRACE_PERIOD"
    RECHECKED = "RECHECKED"
    REMEDIATED = "REMEDIATED"
    VERIFIED = "VERIFIED"
    CLOSED = "CLOSED"
    REMEDIATION_SKIPPED = "REMEDIATION_SKIPPED"
    REMEDIATION_FAILED = "REMEDIATION_FAILED"
    JIRA_FAILED = "JIRA_FAILED"
    ALERT_FAILED = "ALERT_FAILED"
    FALSE_POSITIVE = "FALSE_POSITIVE"


OPEN_STATUSES = {
    AnomalyStatus.DETECTED,
    AnomalyStatus.RECORDED,
    AnomalyStatus.ALERTED,
    AnomalyStatus.TICKETED,
    AnomalyStatus.GRACE_PERIOD,
    AnomalyStatus.RECHECKED,
    AnomalyStatus.JIRA_FAILED,
    AnomalyStatus.ALERT_FAILED,
}


TERMINAL_STATUSES = {
    AnomalyStatus.REMEDIATED,
    AnomalyStatus.VERIFIED,
    AnomalyStatus.CLOSED,
    AnomalyStatus.REMEDIATION_SKIPPED,
    AnomalyStatus.REMEDIATION_FAILED,
    AnomalyStatus.FALSE_POSITIVE,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def epoch_seconds(offset_seconds: int = 0) -> int:
    return int(time.time()) + offset_seconds


def correlation_id(environment: str, instance_id: str, anomaly_type: str) -> str:
    raw = f"{environment}:{instance_id}:{anomaly_type}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


def anomaly_id(environment: str, instance_id: str, anomaly_type: str) -> str:
    return f"{environment}#{instance_id}#{anomaly_type}"


def decimalize(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {key: decimalize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [decimalize(item) for item in value]
    return value


@dataclass(frozen=True)
class AnomalySignal:
    instance_id: str
    anomaly_type: str
    score: float
    threshold: float
    severity: str
    evidence: dict[str, Any] = field(default_factory=dict)
    model_endpoint: str = ""

    def is_anomalous(self) -> bool:
        return self.score >= self.threshold


@dataclass(frozen=True)
class RemediationMessage:
    anomaly_id: str
    correlation_id: str
    environment: str
    instance_id: str
    anomaly_type: str
    scheduled_for_epoch: int

    def to_payload(self) -> dict[str, Any]:
        return {
            "message_type": "remediation_recheck",
            "anomaly_id": self.anomaly_id,
            "correlation_id": self.correlation_id,
            "environment": self.environment,
            "instance_id": self.instance_id,
            "anomaly_type": self.anomaly_type,
            "scheduled_for_epoch": self.scheduled_for_epoch,
        }
