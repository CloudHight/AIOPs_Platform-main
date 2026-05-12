"""SNS notification logic."""

from __future__ import annotations

import json
from typing import Any

from . import aws_clients
from .errors import AlertingError
from .models import AnomalySignal


class AlertPublisher:
    def __init__(self, topic_arn: str, client=None) -> None:
        self.topic_arn = topic_arn
        self.client = client or aws_clients.sns()

    def publish_anomaly(self, signal: AnomalySignal, record: dict[str, Any]) -> None:
        message = {
            "title": "AIOps anomaly detected",
            "correlation_id": record["correlation_id"],
            "anomaly_id": record["anomaly_id"],
            "environment": record["environment"],
            "instance_id": signal.instance_id,
            "anomaly_type": signal.anomaly_type,
            "severity": signal.severity,
            "score": signal.score,
            "threshold": signal.threshold,
            "status": record["status"],
            "jira_issue_key": record.get("jira_issue_key"),
            "jira_ticket_id": record.get("jira_issue_key"),
            "evidence": signal.evidence,
        }
        try:
            self.client.publish(
                TopicArn=self.topic_arn,
                Subject=f"AIOps {signal.severity} {signal.anomaly_type} anomaly",
                Message=json.dumps(message, indent=2, default=str),
                MessageAttributes={
                    "correlation_id": {"DataType": "String", "StringValue": record["correlation_id"]},
                    "anomaly_type": {"DataType": "String", "StringValue": signal.anomaly_type},
                    "severity": {"DataType": "String", "StringValue": signal.severity},
                },
            )
        except Exception as exc:
            raise AlertingError(f"Failed to publish SNS alert: {exc}") from exc
