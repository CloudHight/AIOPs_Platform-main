"""Lambda entry points for anomaly detection and remediation processing."""

from __future__ import annotations

import json
import logging
from typing import Any

from .alerting import AlertPublisher
from .anomaly_store import AnomalyStore
from .config import RuntimeConfig, load_config
from .discovery import monitored_instance_ids
from .events import EventPublisher
from .inference import extract_score, invoke_json
from .jira_client import JiraClient, load_jira_credentials
from .logs_reader import recent_nginx_errors
from .metrics_reader import average_cpu_utilization
from .models import AnomalySignal, AnomalyStatus, RemediationMessage, epoch_seconds, utc_now
from .remediation import RemediationScheduler, Remediator

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    config = load_config()
    if _is_sqs_event(event):
        return handle_remediation_event(event, config)
    return handle_detection_event(event, config)


def handle_detection_event(event: dict[str, Any], config: RuntimeConfig) -> dict[str, Any]:
    store = AnomalyStore(config.dynamodb_table)
    alerts = AlertPublisher(config.sns_topic_arn)
    events = EventPublisher(config.event_bus_name)
    scheduler = RemediationScheduler(config.processing_queue_url)

    requested_instance_ids = event.get("instance_ids")
    instance_ids = (
        [str(instance_id) for instance_id in requested_instance_ids]
        if isinstance(requested_instance_ids, list)
        else monitored_instance_ids(config.instance_tag_key, config.instance_tag_value)
    )
    processed = 0
    detected = 0

    for instance_id in instance_ids:
        for signal in detect_signals(instance_id, config):
            processed += 1
            if not signal.is_anomalous():
                continue
            detected += 1
            record, is_new = store.record_detection(config.environment, signal, config.ttl_days)
            event_detail = _event_detail(record, signal)
            events.publish("anomaly detected", event_detail)
            if is_new or not record.get("alerted_at"):
                try:
                    alerts.publish_anomaly(signal, record)
                    record = store.mark(record["anomaly_id"], AnomalyStatus.ALERTED, alerted_at=utc_now())
                    events.publish("alert sent", event_detail)
                except Exception as exc:
                    logger.exception("alert_failed", extra=event_detail)
                    record = store.mark(record["anomaly_id"], AnomalyStatus.ALERT_FAILED, alert_error=str(exc))
                    events.publish("alert failed", {**event_detail, "error": str(exc)})

            if not record.get("jira_issue_key"):
                record = _create_jira_ticket(config, store, signal, record, events)

            existing_schedule = int(record.get("remediation_scheduled_for_epoch", 0) or 0)
            if existing_schedule > epoch_seconds():
                continue

            scheduled_for = epoch_seconds(config.grace_period_minutes * 60)
            message = RemediationMessage(
                anomaly_id=record["anomaly_id"],
                correlation_id=record["correlation_id"],
                environment=config.environment,
                instance_id=signal.instance_id,
                anomaly_type=signal.anomaly_type,
                scheduled_for_epoch=scheduled_for,
            )
            scheduler.schedule(message, config.grace_period_minutes)
            store.mark(
                record["anomaly_id"],
                AnomalyStatus.GRACE_PERIOD,
                remediation_scheduled_at=utc_now(),
                remediation_scheduled_for_epoch=scheduled_for,
            )
            events.publish("remediation scheduled", event_detail)

    return {"processed_signals": processed, "detected_anomalies": detected}


def detect_signals(instance_id: str, config: RuntimeConfig) -> list[AnomalySignal]:
    cpu_average = average_cpu_utilization(instance_id) or 0.0
    cpu_payload = {"instances": [{"instance_id": instance_id, "cpu_average": cpu_average}]}
    try:
        cpu_response = invoke_json(config.cpu_model_endpoint, cpu_payload)
        cpu_score = extract_score(cpu_response, fallback=cpu_average / 100)
    except Exception as exc:
        logger.warning("cpu_inference_failed_using_metric_fallback", extra={"instance_id": instance_id, "error": str(exc)})
        cpu_score = cpu_average / 100

    log_evidence = recent_nginx_errors(instance_id)
    log_payload = {"instances": [{"instance_id": instance_id, **log_evidence}]}
    try:
        log_response = invoke_json(config.log_model_endpoint, log_payload)
        error_count = float(log_evidence.get("error_count", 0))
        log_score = extract_score(log_response, fallback=min(error_count / 10, 1.0))
    except Exception as exc:
        logger.warning("log_inference_failed_using_log_fallback", extra={"instance_id": instance_id, "error": str(exc)})
        error_count = float(log_evidence.get("error_count", 0))
        log_score = min(error_count / 10, 1.0)

    return [
        AnomalySignal(
            instance_id=instance_id,
            anomaly_type="cpu",
            score=cpu_score,
            threshold=config.cpu_threshold,
            severity=_severity(cpu_score, config.cpu_threshold),
            evidence={"cpu_average": cpu_average},
            model_endpoint=config.cpu_model_endpoint,
        ),
        AnomalySignal(
            instance_id=instance_id,
            anomaly_type="log",
            score=log_score,
            threshold=config.log_threshold,
            severity=_severity(log_score, config.log_threshold),
            evidence=log_evidence,
            model_endpoint=config.log_model_endpoint,
        ),
    ]


def handle_remediation_event(event: dict[str, Any], config: RuntimeConfig) -> dict[str, Any]:
    store = AnomalyStore(config.dynamodb_table)
    scheduler = RemediationScheduler(config.processing_queue_url)
    events = EventPublisher(config.event_bus_name)
    remediator = Remediator(config)
    processed = 0

    for record in event["Records"]:
        processed += 1
        payload = json.loads(record["body"])
        if scheduler.reschedule_until_due(payload):
            events.publish("remediation waiting", payload)
            continue

        anomaly = store.get(payload["anomaly_id"])
        if not anomaly:
            events.publish("remediation skipped", {**payload, "reason": "anomaly_record_missing"})
            continue

        current_signal = _recheck_anomaly(anomaly, config)
        detail = _event_detail(anomaly, current_signal)
        if not current_signal.is_anomalous():
            store.mark(
                anomaly["anomaly_id"],
                AnomalyStatus.CLOSED,
                resolved_at=utc_now(),
                remediation_skip_reason="signal_recovered",
                last_score=current_signal.score,
            )
            events.publish("remediation skipped", {**detail, "reason": "signal_recovered"})
            continue

        store.mark(anomaly["anomaly_id"], AnomalyStatus.RECHECKED, rechecked_at=utc_now())
        try:
            result = remediator.execute(anomaly)
        except Exception as exc:
            logger.exception("remediation_failed", extra=detail)
            store.increment_remediation_attempt(anomaly["anomaly_id"])
            store.mark(anomaly["anomaly_id"], AnomalyStatus.REMEDIATION_FAILED, remediation_error=str(exc))
            events.publish("remediation failed", {**detail, "error": str(exc)})
            continue
        if result["status"] == "executed":
            store.increment_remediation_attempt(anomaly["anomaly_id"])
            store.mark(anomaly["anomaly_id"], AnomalyStatus.REMEDIATED, remediation_result=result)
            events.publish("remediation succeeded", {**detail, **result})
        else:
            store.mark(
                anomaly["anomaly_id"],
                AnomalyStatus.REMEDIATION_SKIPPED,
                remediation_result=result,
                remediation_skip_reason=result["reason"],
            )
            events.publish("remediation skipped", {**detail, **result})

    return {"processed_messages": processed}


def _create_jira_ticket(
    config: RuntimeConfig,
    store: AnomalyStore,
    signal: AnomalySignal,
    record: dict[str, Any],
    events: EventPublisher,
) -> dict[str, Any]:
    detail = _event_detail(record, signal)
    try:
        jira = JiraClient(load_jira_credentials(config.jira_credentials_secret), config.jira_project_key)
        issue_key = jira.create_incident(signal, record, config.runbook_url)
        updated = store.mark(record["anomaly_id"], AnomalyStatus.TICKETED, jira_issue_key=issue_key, ticketed_at=utc_now())
        events.publish("jira ticket created", {**detail, "jira_issue_key": issue_key})
        return updated
    except Exception as exc:
        logger.exception("jira_failed", extra=detail)
        updated = store.mark(record["anomaly_id"], AnomalyStatus.JIRA_FAILED, jira_error=str(exc))
        events.publish("jira ticket failed", {**detail, "error": str(exc)})
        return updated


def _recheck_anomaly(anomaly: dict[str, Any], config: RuntimeConfig) -> AnomalySignal:
    signals = {signal.anomaly_type: signal for signal in detect_signals(anomaly["instance_id"], config)}
    return signals[anomaly["anomaly_type"]]


def _event_detail(record: dict[str, Any], signal: AnomalySignal) -> dict[str, Any]:
    return {
        "correlation_id": record["correlation_id"],
        "environment": record["environment"],
        "instance_id": signal.instance_id,
        "anomaly_type": signal.anomaly_type,
        "anomaly_id": record["anomaly_id"],
        "severity": signal.severity,
        "score": signal.score,
        "threshold": signal.threshold,
        "jira_issue_key": record.get("jira_issue_key", ""),
        "jira_ticket_id": record.get("jira_issue_key", ""),
    }


def _severity(score: float, threshold: float) -> str:
    if score >= threshold * 1.5:
        return "critical"
    if score >= threshold * 1.2:
        return "high"
    return "medium"


def _is_sqs_event(event: dict[str, Any]) -> bool:
    records = event.get("Records", [])
    return bool(records and records[0].get("eventSource") == "aws:sqs")
