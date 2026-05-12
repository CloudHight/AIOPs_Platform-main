"""EventBridge publishing helpers."""

from __future__ import annotations

import json
import logging
from typing import Any

from . import aws_clients

logger = logging.getLogger(__name__)


class EventPublisher:
    def __init__(self, event_bus_name: str, client=None) -> None:
        self.event_bus_name = event_bus_name
        self.client = client or aws_clients.events()

    def publish(self, detail_type: str, detail: dict[str, Any]) -> None:
        entry = {
            "Source": f"anomaly-detection.{detail.get('environment', 'unknown')}",
            "DetailType": detail_type,
            "Detail": json.dumps(detail, default=str),
            "EventBusName": self.event_bus_name,
        }
        self.client.put_events(Entries=[entry])
        logger.info("published_eventbridge_event", extra={"detail_type": detail_type, **detail})
