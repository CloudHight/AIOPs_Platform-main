import argparse
import os
import time

import boto3
from sagemaker import get_execution_role
from sagemaker.huggingface import HuggingFace
from sagemaker.parameter import CategoricalParameter, ContinuousParameter, IntegerParameter
from sagemaker.tuner import HyperparameterTuner


TERMINAL_STATUSES = {"Completed", "Failed", "Stopped"}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--prefix", default="bert-update/data")
    parser.add_argument("--train-script", default="train.py")
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=60)
    return parser.parse_args()


def launch_sagemaker_tuning(train_uri: str, val_uri: str, test_uri: str, train_script: str = "train.py", role=None):
    if not os.path.isfile(train_script):
        raise FileNotFoundError(f"Training script not found: {train_script}")

    role = role or get_execution_role()

    estimator = HuggingFace(
        entry_point=train_script,
        instance_type="ml.g5.xlarge",
        instance_count=1,
        transformers_version="4.26",
        pytorch_version="1.13",
        py_version="py39",
        role=role,
        enable_network_isolation=False,
        hyperparameters={
            "epochs": 4,
            "model_name": "distilbert-base-uncased",
            "learning_rate": 2e-5,
            "per_device_train_batch_size": 16,
            "max_seq_length": 192,
            "threshold_objective": "f1",
        },
        metric_definitions=[
            {"Name": "eval_f1_anomaly", "Regex": r"'eval_f1_anomaly':\s*([0-9\.]+)"},
            {"Name": "eval_precision", "Regex": r"'eval_precision':\s*([0-9\.]+)"},
            {"Name": "eval_recall", "Regex": r"'eval_recall':\s*([0-9\.]+)"},
            {"Name": "best_threshold", "Regex": r"'best_threshold':\s*([0-9\.]+)"},
        ],
        base_job_name="hf-nginx-anomaly-update",
    )

    tuner = HyperparameterTuner(
        estimator=estimator,
        objective_metric_name="eval_f1_anomaly",
        objective_type="Maximize",
        metric_definitions=estimator.metric_definitions,
        hyperparameter_ranges={
            "learning_rate": ContinuousParameter(1e-5, 5e-5),
            "per_device_train_batch_size": CategoricalParameter([8, 16, 24]),
            "epochs": IntegerParameter(3, 5),
            "max_seq_length": CategoricalParameter([128, 192, 256]),
            "model_name": CategoricalParameter(["distilbert-base-uncased", "bert-base-uncased"]),
        },
        max_jobs=8,
        max_parallel_jobs=1,
    )

    print("[INFO] Launching SageMaker tuning job")
    tuner.fit({"train": train_uri, "validation": val_uri, "test": test_uri}, wait=False)
    print(f"[INFO] Tuning job launched: {tuner.latest_tuning_job.name}")
    return tuner


def monitor_tuning_job(tuning_job_name: str, poll_seconds: int) -> None:
    sm_client = boto3.client("sagemaker")
    print(f"[INFO] Watching tuning job: {tuning_job_name}")

    while True:
        response = sm_client.describe_hyper_parameter_tuning_job(
            HyperParameterTuningJobName=tuning_job_name
        )
        status = response["HyperParameterTuningJobStatus"]
        counters = response.get("TrainingJobStatusCounters", {})
        print(
            f"[TUNING] {status} | "
            f"Completed: {counters.get('Completed', 0)} | "
            f"InProgress: {counters.get('InProgress', 0)} | "
            f"Failed: {counters.get('Failed', 0)} | "
            f"Stopped: {counters.get('Stopped', 0)}"
        )

        best = response.get("BestTrainingJob", {})
        if best.get("TrainingJobName"):
            metric = best.get("FinalHyperParameterTuningJobObjectiveMetric", {})
            metric_name = metric.get("MetricName", "objective")
            metric_value = metric.get("Value", "?")
            print(f"[BEST] {best['TrainingJobName']} | {metric_name}: {metric_value}")

        if status in TERMINAL_STATUSES:
            print(f"[INFO] Tuning job finished with status: {status}")
            return

        time.sleep(poll_seconds)


if __name__ == "__main__":
    args = parse_args()
    tuner = launch_sagemaker_tuning(
        train_uri=f"s3://{args.bucket}/{args.prefix}/train/",
        val_uri=f"s3://{args.bucket}/{args.prefix}/validation/",
        test_uri=f"s3://{args.bucket}/{args.prefix}/test/",
        train_script=args.train_script,
    )
    print(f"[INFO] Tuning job name: {tuner.latest_tuning_job.name}")
    if args.wait:
        monitor_tuning_job(tuner.latest_tuning_job.name, args.poll_seconds)
