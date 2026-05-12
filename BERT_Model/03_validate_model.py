import argparse
from typing import Any, Dict, List

import boto3


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--training-job-name", default="", help="SageMaker training job name")
    parser.add_argument("--tuning-job-name", default="", help="SageMaker hyperparameter tuning job name")
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


if __name__ == "__main__":
    main()
