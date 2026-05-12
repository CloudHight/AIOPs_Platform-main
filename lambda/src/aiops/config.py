"""Environment and SSM-backed runtime configuration."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

_CACHE: dict[str, Any] = {}
_CACHE_TTL_SECONDS = 300


def _as_bool(value: str | bool | None, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass
class RuntimeConfig:
    environment: str
    dynamodb_table: str
    sns_topic_arn: str
    processing_queue_url: str
    event_bus_name: str
    cpu_model_endpoint: str
    log_model_endpoint: str
    jira_project_key: str
    jira_credentials_secret: str
    instance_tag_key: str
    instance_tag_value: str
    cpu_threshold: float
    log_threshold: float
    grace_period_minutes: int
    auto_remediation_enabled: bool
    dry_run: bool
    max_remediation_attempts: int
    remediation_cooldown_minutes: int
    ttl_days: int
    runbook_url: str

    @classmethod
    def from_environment(cls) -> "RuntimeConfig":
        return cls(
            environment=os.environ.get("ENVIRONMENT", "dev"),
            dynamodb_table=os.environ["DYNAMODB_TABLE"],
            sns_topic_arn=os.environ["SNS_TOPIC_ARN"],
            processing_queue_url=os.environ["PROCESSING_QUEUE_URL"],
            event_bus_name=os.environ["EVENT_BUS_NAME"],
            cpu_model_endpoint=os.environ["CPU_MODEL_ENDPOINT"],
            log_model_endpoint=os.environ["LOG_MODEL_ENDPOINT"],
            jira_project_key=os.environ["JIRA_PROJECT_KEY"],
            jira_credentials_secret=os.environ["JIRA_CREDENTIALS_SECRET"],
            instance_tag_key=os.environ.get("INSTANCE_TAG_KEY", "AnomalyMonitoring"),
            instance_tag_value=os.environ.get("INSTANCE_TAG_VALUE", "enabled"),
            cpu_threshold=float(os.environ.get("ANOMALY_THRESHOLD_CPU", "0.85")),
            log_threshold=float(os.environ.get("ANOMALY_THRESHOLD_LOG", "0.8")),
            grace_period_minutes=int(os.environ.get("GRACE_PERIOD_MINUTES", "15")),
            auto_remediation_enabled=_as_bool(os.environ.get("AUTO_REMEDIATION_ENABLED"), False),
            dry_run=_as_bool(os.environ.get("DRY_RUN"), True),
            max_remediation_attempts=int(os.environ.get("MAX_REMEDIATION_ATTEMPTS", "1")),
            remediation_cooldown_minutes=int(os.environ.get("REMEDIATION_COOLDOWN_MINUTES", "60")),
            ttl_days=int(os.environ.get("ANOMALY_TTL_DAYS", "30")),
            runbook_url=os.environ.get("RUNBOOK_URL", "docs/operations-runbook.md"),
        )


def load_config(ssm_client=None, force_refresh: bool = False) -> RuntimeConfig:
    from . import aws_clients

    now = time.time()
    if not force_refresh and _CACHE and now - _CACHE["loaded_at"] < _CACHE_TTL_SECONDS:
        return _CACHE["config"]

    config = RuntimeConfig.from_environment()
    client = ssm_client or aws_clients.ssm()
    path = f"/AnomalyDetection/{config.environment}/"
    try:
        response = client.get_parameters_by_path(Path=path, WithDecryption=True, Recursive=False)
    except Exception:
        _CACHE.update({"loaded_at": now, "config": config})
        return config

    values = {item["Name"].split("/")[-1]: item["Value"] for item in response.get("Parameters", [])}
    config.cpu_threshold = float(values.get("CpuThreshold", config.cpu_threshold))
    config.log_threshold = float(values.get("LogThreshold", config.log_threshold))
    config.grace_period_minutes = int(values.get("GracePeriodMinutes", config.grace_period_minutes))
    config.auto_remediation_enabled = _as_bool(
        values.get("AutoRemediationEnabled"), config.auto_remediation_enabled
    )
    config.dry_run = _as_bool(values.get("DryRun"), config.dry_run)
    config.max_remediation_attempts = int(values.get("MaxRemediationAttempts", config.max_remediation_attempts))
    config.remediation_cooldown_minutes = int(
        values.get("RemediationCooldownMinutes", config.remediation_cooldown_minutes)
    )

    _CACHE.update({"loaded_at": now, "config": config})
    return config
