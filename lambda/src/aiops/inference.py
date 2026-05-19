"""SageMaker inference helpers."""

from __future__ import annotations

import json
from typing import Any

from .errors import InferenceError


def invoke(endpoint_name: str, request_body: str | bytes, content_type: str, client=None) -> Any:
    if client is None:
        from . import aws_clients

        runtime = aws_clients.sagemaker_runtime()
    else:
        runtime = client
    request_body_bytes = request_body if isinstance(request_body, bytes) else request_body.encode("utf-8")
    try:
        response = runtime.invoke_endpoint(
            EndpointName=endpoint_name,
            ContentType=content_type,
            Body=request_body_bytes,
        )
        response_body = response["Body"].read().decode("utf-8")
    except Exception as exc:
        raise InferenceError(f"SageMaker invocation failed for {endpoint_name}: {exc}") from exc
    try:
        return json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise InferenceError(f"SageMaker response was not JSON for {endpoint_name}: {response_body[:200]}") from exc


def invoke_json(endpoint_name: str, payload: dict[str, Any], client=None) -> Any:
    return invoke(endpoint_name, json.dumps(payload), "application/json", client=client)


def invoke_csv(endpoint_name: str, rows: list[float], client=None) -> Any:
    body = "\n".join(str(row) for row in rows)
    if body:
        body = f"{body}\n"
    return invoke(endpoint_name, body, "text/csv", client=client)


def extract_score(response: Any, fallback: float = 0.0) -> float:
    if isinstance(response, list) and response:
        first = response[0]
        if isinstance(first, dict):
            score = first.get("score")
            if score is None:
                score = first.get("anomaly_score", fallback)
            return float(score)
        return float(first)
    if not isinstance(response, dict):
        return fallback
    for key in ("score", "anomaly_score", "confidence"):
        if key in response:
            return float(response[key])
    scores = response.get("scores")
    if isinstance(scores, list) and scores:
        first = scores[0]
        if isinstance(first, dict):
            score = first.get("score")
            if score is None:
                score = first.get("anomaly_score", fallback)
            return float(score)
        return float(first)
    predictions = response.get("predictions")
    if isinstance(predictions, list) and predictions:
        first = predictions[0]
        if isinstance(first, dict):
            score = first.get("score")
            if score is None:
                score = first.get("probability", fallback)
            return float(score)
        return float(first)
    return fallback
