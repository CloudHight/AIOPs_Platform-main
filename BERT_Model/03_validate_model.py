import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import boto3


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--training-job-name", default="", help="SageMaker training job name")
    parser.add_argument("--tuning-job-name", default="", help="SageMaker hyperparameter tuning job name")
    parser.add_argument("--output-file", default="", help="Optional path to write validation metrics JSON")
    parser.add_argument(
        "--minimum-f1",
        type=float,
        default=float(os.environ.get("LOG_MIN_F1", "0.8")),
        help="Minimum acceptable anomaly-class F1 score.",
    )
    return parser.parse_args()


def format_metrics(metrics: List[Dict[str, Any]]) -> Dict[str, float]:
    return {
        item.get("MetricName", "unknown"): float(item.get("Value", 0.0))
        for item in metrics
        if item.get("MetricName") is not None
    }


def resolve_from_tuning_job(sm_client, tuning_job_name: str) -> Dict[str, Any]:
    tuning = sm_client.describe_hyper_parameter_tuning_job(
        HyperParameterTuningJobName=tuning_job_name
    )
    best_job = tuning.get("BestTrainingJob", {})
    training_job_name = best_job.get("TrainingJobName")
    if not training_job_name:
        status = tuning.get("HyperParameterTuningJobStatus", "Unknown")
        raise ValueError(
            f"No best training job is available yet for tuning job {tuning_job_name}. Current status: {status}"
        )

    training = sm_client.describe_training_job(TrainingJobName=training_job_name)
    return {
        "mode": "tuning",
        "tuning": tuning,
        "training": training,
        "training_job_name": training_job_name,
        "objective_metric": best_job.get("FinalHyperParameterTuningJobObjectiveMetric", {}),
        "tuned_hyperparameters": best_job.get("TunedHyperParameters", {}),
    }


def resolve_from_training_job(sm_client, training_job_name: str) -> Dict[str, Any]:
    training = sm_client.describe_training_job(TrainingJobName=training_job_name)
    return {
        "mode": "training",
        "training": training,
        "training_job_name": training_job_name,
        "objective_metric": {},
        "tuned_hyperparameters": {},
    }


def print_summary(payload: Dict[str, Any]) -> None:
    training = payload["training"]
    training_metrics = format_metrics(training.get("FinalMetricDataList", []))
    artifact_uri = training.get("ModelArtifacts", {}).get("S3ModelArtifacts", "")

    print("[INFO] Validation summary")
    if payload["mode"] == "tuning":
        tuning = payload["tuning"]
        print(f"  Tuning job: {tuning.get('HyperParameterTuningJobName')}")
        print(f"  Tuning status: {tuning.get('HyperParameterTuningJobStatus')}")
        objective = payload.get("objective_metric", {})
        if objective:
            print(f"  Best objective metric: {objective.get('MetricName')}={objective.get('Value')}")
        tuned_hparams = payload.get("tuned_hyperparameters", {})
        if tuned_hparams:
            print(f"  Tuned hyperparameters: {tuned_hparams}")

    print(f"  Best training job: {payload['training_job_name']}")
    print(f"  Training status: {training.get('TrainingJobStatus')}")
    print(f"  Secondary status: {training.get('SecondaryStatus')}")
    print(f"  Model artifact: {artifact_uri}")

    interesting_metrics = [
        "eval_f1_anomaly",
        "eval_f1_macro",
        "eval_precision",
        "eval_recall",
        "eval_accuracy",
        "best_threshold",
        "threshold_f1",
        "threshold_precision",
        "threshold_recall",
    ]
    available = {name: training_metrics[name] for name in interesting_metrics if name in training_metrics}
    if available:
        print(f"  Reported metrics: {available}")
    else:
        print(f"  Final metrics: {training_metrics}")


def build_evaluation_payload(payload: Dict[str, Any], minimum_f1: float) -> Dict[str, Any]:
    training = payload["training"]
    training_metrics = format_metrics(training.get("FinalMetricDataList", []))
    objective = payload.get("objective_metric", {})
    tuned_hparams = payload.get("tuned_hyperparameters", {})

    metrics = dict(training_metrics)
    if objective.get("MetricName") and objective.get("Value") is not None:
        metrics["objective_metric_name"] = objective["MetricName"]
        metrics["objective_metric_value"] = float(objective["Value"])
    if "best_threshold" not in metrics and "threshold" in tuned_hparams:
        metrics["best_threshold"] = float(tuned_hparams["threshold"])

    f1_score = metrics.get("eval_f1_anomaly")
    if f1_score is None and metrics.get("objective_metric_name") == "eval_f1_anomaly":
        f1_score = metrics.get("objective_metric_value")
        metrics["eval_f1_anomaly"] = f1_score
    if f1_score is None:
        raise ValueError("Validation metrics are missing eval_f1_anomaly.")
    if float(f1_score) < minimum_f1:
        raise ValueError(f"eval_f1_anomaly {f1_score} is below required minimum {minimum_f1}.")
    if metrics.get("best_threshold") is None:
        raise ValueError("Validation metrics are missing best_threshold.")

    artifact_uri = training.get("ModelArtifacts", {}).get("S3ModelArtifacts", "")
    status = training.get("TrainingJobStatus", "")
    if status != "Completed":
        raise ValueError(f"Training job is not completed: {payload['training_job_name']} ({status})")

    return {
        "validation_mode": "sagemaker_training_metrics",
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "tuning_job_name": payload.get("tuning", {}).get("HyperParameterTuningJobName", ""),
        "training_job_name": payload["training_job_name"],
        "training_status": status,
        "model_artifact_s3_uri": artifact_uri,
        "metrics": metrics,
    }


def write_evaluation_payload(output_file: str, payload: Dict[str, Any], minimum_f1: float) -> None:
    evaluation = build_evaluation_payload(payload, minimum_f1)
    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evaluation["metrics"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[INFO] Validation metrics written to {path}")


def main():
    args = parse_args()
    if bool(args.training_job_name) == bool(args.tuning_job_name):
        raise ValueError("Provide exactly one of --training-job-name or --tuning-job-name.")

    sm_client = boto3.client("sagemaker")
    if args.tuning_job_name:
        payload = resolve_from_tuning_job(sm_client, args.tuning_job_name)
    else:
        payload = resolve_from_training_job(sm_client, args.training_job_name)
    print_summary(payload)
    if args.output_file:
        write_evaluation_payload(args.output_file, payload, args.minimum_f1)


if __name__ == "__main__":
    main()
