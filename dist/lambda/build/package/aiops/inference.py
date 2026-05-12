"""SageMaker inference helpers."""

from __future__ import annotations

import json
from typing import Any

from . import aws_clients
from .errors import InferenceError


def invoke_json(endpoint_name: str, payload: dict[str, Any], client=None) -> dict[str, Any]:
    runtime = client or aws_clients.sagemaker_runtime()
    try:
        response = runtime.invoke_endpoint(
            EndpointName=endpoint_name,
            ContentType="application/json",
            Body=json.dumps(payload).encode("utf-8"),
        )
        body = response["Body"].read().decode("utf-8")
    except Exception as exc:
        raise InferenceError(f"SageMaker invocation failed for {endpoint_name}: {exc}") from exc
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise InferenceError(f"SageMaker response was not JSON for {endpoint_name}: {body[:200]}") from exc


def extract_score(response: dict[str, Any], fallback: float = 0.0) -> float:
    for key in ("score", "anomaly_score", "confidence"):
        if key in response:
            return float(response[key])
    scores = response.get("scores")
    if isinstance(scores, list) and scores:
        first = scores[0]
        if isinstance(first, dict):
            return float(first.get("score", first.get("anomaly_score", fallback)))
        return float(first)
    predictions = response.get("predictions")
    if isinstance(predictions, list) and predictions:
        first = predictions[0]
        if isinstance(first, dict):
            return float(first.get("score", first.get("probability", fallback)))
        return float(first)
    return fallback
