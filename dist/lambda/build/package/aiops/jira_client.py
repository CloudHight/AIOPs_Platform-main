"""Jira incident integration with deterministic correlation IDs."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any
from urllib import request
from urllib.error import HTTPError, URLError

from . import aws_clients
from .errors import JiraError
from .models import AnomalySignal


@dataclass(frozen=True)
class JiraCredentials:
    api_url: str
    user_email: str
    api_token: str


def load_jira_credentials(secret_id: str, client=None) -> JiraCredentials:
    secrets = client or aws_clients.secretsmanager()
    response = secrets.get_secret_value(SecretId=secret_id)
    secret = json.loads(response["SecretString"])
    credentials = JiraCredentials(
        api_url=secret.get("JIRA_API_URL", "").rstrip("/"),
        user_email=secret.get("JIRA_USER_EMAIL", ""),
        api_token=secret.get("JIRA_API_TOKEN", ""),
    )
    if not all((credentials.api_url, credentials.user_email, credentials.api_token)):
        raise JiraError("Jira secret must contain JIRA_API_URL, JIRA_USER_EMAIL, and JIRA_API_TOKEN")
    return credentials


class JiraClient:
    def __init__(self, credentials: JiraCredentials, project_key: str, issue_type: str = "Incident") -> None:
        self.credentials = credentials
        self.project_key = project_key
        self.issue_type = issue_type

    def create_incident(self, signal: AnomalySignal, record: dict[str, Any], runbook_url: str) -> str:
        summary = (
            f"[AIOps][{record['environment']}][{signal.anomaly_type}] "
            f"{signal.instance_id} correlation:{record['correlation_id']}"
        )
        description = self._description(signal, record, runbook_url)
        payload = {
            "fields": {
                "project": {"key": self.project_key},
                "summary": summary,
                "description": description,
                "issuetype": {"name": self.issue_type},
                "labels": [
                    "aiops",
                    f"environment-{record['environment']}",
                    f"correlation-{record['correlation_id']}",
                ],
            }
        }
        response = self._request("POST", "/rest/api/2/issue", payload)
        key = response.get("key")
        if not key:
            raise JiraError(f"Jira create response did not include issue key: {response}")
        return key

    def add_comment(self, issue_key: str, comment: str) -> None:
        self._request("POST", f"/rest/api/2/issue/{issue_key}/comment", {"body": comment})

    def _description(self, signal: AnomalySignal, record: dict[str, Any], runbook_url: str) -> str:
        evidence = json.dumps(signal.evidence, indent=2, default=str)
        return "\n".join([
            "AIOps anomaly incident",
            "",
            f"Correlation ID: {record['correlation_id']}",
            f"Anomaly ID: {record['anomaly_id']}",
            f"Environment: {record['environment']}",
            f"Instance ID: {signal.instance_id}",
            f"Anomaly type: {signal.anomaly_type}",
            f"Severity: {signal.severity}",
            f"Model endpoint: {signal.model_endpoint}",
            f"Score: {signal.score}",
            f"Threshold: {signal.threshold}",
            f"Detection timestamp: {record.get('detected_at')}",
            f"Remediation status: {record.get('status')}",
            f"Runbook: {runbook_url}",
            "",
            "Evidence:",
            evidence,
        ])

    def _request(self, method: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        token = f"{self.credentials.user_email}:{self.credentials.api_token}".encode("utf-8")
        auth = base64.b64encode(token).decode("ascii")
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self.credentials.api_url}{path}",
            data=data,
            method=method,
            headers={
                "Authorization": f"Basic {auth}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        try:
            with request.urlopen(req, timeout=30) as response:
                body = response.read().decode("utf-8")
        except (HTTPError, URLError, TimeoutError) as exc:
            raise JiraError(f"Jira request failed: {exc}") from exc
        return json.loads(body) if body else {}
