#!/usr/bin/env python3
"""ModelOps artifact packaging and Terraform handoff utilities."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return os.environ.get("GIT_COMMIT", "unknown")


def read_json(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def read_csv_first_row(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return {}
    return {key: coerce_value(value) for key, value in rows[0].items()}


def coerce_value(value: Any) -> Any:
    if value is None:
        return value
    if isinstance(value, (int, float, bool)):
        return value
    text = str(value)
    if text == "":
        return None
    if text.lower() in {"true", "false"}:
        return text.lower() == "true"
    try:
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        return text


def s3_parts(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path.strip("/"):
        raise ValueError(f"Invalid S3 URI: {uri}")
    return parsed.netloc, parsed.path.strip("/")


def resolve_training_artifact(training_job_name: str) -> str:
    import boto3

    client = boto3.client("sagemaker")
    response = client.describe_training_job(TrainingJobName=training_job_name)
    return response["ModelArtifacts"]["S3ModelArtifacts"]


def resolve_tuning_artifact(tuning_job_name: str) -> tuple[str, str]:
    import boto3

    client = boto3.client("sagemaker")
    tuning = client.describe_hyper_parameter_tuning_job(
        HyperParameterTuningJobName=tuning_job_name
    )
    best_job = tuning.get("BestTrainingJob", {})
    training_job_name = best_job.get("TrainingJobName")
    if not training_job_name:
        status = tuning.get("HyperParameterTuningJobStatus", "Unknown")
        raise ValueError(f"Tuning job has no best training job yet: {tuning_job_name} ({status})")
    return training_job_name, resolve_training_artifact(training_job_name)


def load_metrics(evaluation_file: str | None) -> dict[str, Any]:
    if not evaluation_file:
        return {}
    suffix = Path(evaluation_file).suffix.lower()
    if suffix == ".json":
        return read_json(evaluation_file)
    if suffix == ".csv":
        return read_csv_first_row(evaluation_file)
    raise ValueError(f"Unsupported evaluation file format: {evaluation_file}")


def package(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir) / args.model_name
    output_dir.mkdir(parents=True, exist_ok=True)

    training_job_name = args.training_job_name
    artifact_uri = args.model_artifact_s3_uri
    if args.tuning_job_name and not artifact_uri:
        training_job_name, artifact_uri = resolve_tuning_artifact(args.tuning_job_name)
    elif training_job_name and not artifact_uri:
        artifact_uri = resolve_training_artifact(training_job_name)

    if not artifact_uri and not args.local_model_artifact:
        raise ValueError("Provide --model-artifact-s3-uri, --local-model-artifact, --training-job-name, or --tuning-job-name.")

    metrics = load_metrics(args.evaluation_file)
    threshold = None if args.threshold in {"", None} else args.threshold
    if threshold is None:
        threshold = metrics.get("threshold") or metrics.get("best_threshold")

    artifact_s3_uri = artifact_uri or ""
    metadata = {
        "project": "AIOps",
        "model_name": args.model_name,
        "model_version": args.model_version,
        "git_commit": args.git_commit or git_commit(),
        "jenkins_build_number": args.jenkins_build_number,
        "training_started_at": args.training_started_at,
        "training_completed_at": args.training_completed_at or utc_now(),
        "training_data_version": args.training_data_version,
        "training_job_name": training_job_name,
        "tuning_job_name": args.tuning_job_name,
        "container_image_uri": args.container_image_uri,
        "artifact_s3_uri": artifact_s3_uri,
        "local_model_artifact": args.local_model_artifact,
        "inference_contract": {
            "content_type": args.content_type,
            "response_shape": args.response_shape,
        },
        "thresholds": {
            "anomaly_score_threshold": coerce_value(threshold),
        },
        "metrics": metrics,
    }

    evaluation = {
        "model_name": args.model_name,
        "model_version": args.model_version,
        "metrics": metrics,
        "thresholds": metadata["thresholds"],
        "inference_contract": metadata["inference_contract"],
        "validated_at": utc_now(),
    }

    write_json(output_dir / "metadata.json", metadata)
    write_json(output_dir / "evaluation.json", evaluation)
    write_json(output_dir / "handoff.json", {
        "model_name": args.model_name,
        "model_version": args.model_version,
        "source_model_artifact_s3_uri": artifact_s3_uri,
        "local_model_artifact": args.local_model_artifact,
        "container_image_uri": args.container_image_uri,
        "metadata_path": str(output_dir / "metadata.json"),
        "evaluation_path": str(output_dir / "evaluation.json"),
    })
    print(f"[INFO] Packaged metadata in {output_dir}")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def publish(args: argparse.Namespace) -> None:
    import boto3

    handoff = read_json(args.handoff_file)
    model_name = handoff["model_name"]
    model_version = handoff["model_version"]
    prefix = f"{args.s3_prefix.rstrip('/')}/{model_name}/{model_version}"
    artifact_key = f"{prefix}/model.tar.gz"
    metadata_key = f"{prefix}/metadata.json"
    evaluation_key = f"{prefix}/evaluation.json"

    s3 = boto3.client("s3")
    source_s3_uri = handoff.get("source_model_artifact_s3_uri")
    local_artifact = handoff.get("local_model_artifact")
    if source_s3_uri:
        source_bucket, source_key = s3_parts(source_s3_uri)
        s3.copy_object(
            Bucket=args.bucket,
            Key=artifact_key,
            CopySource={"Bucket": source_bucket, "Key": source_key},
        )
    elif local_artifact:
        s3.upload_file(local_artifact, args.bucket, artifact_key)
    else:
        raise ValueError("Handoff has no source model artifact.")

    s3.upload_file(handoff["metadata_path"], args.bucket, metadata_key)
    s3.upload_file(handoff["evaluation_path"], args.bucket, evaluation_key)

    published = {
        "model_name": model_name,
        "model_version": model_version,
        "model_artifact_s3_uri": f"s3://{args.bucket}/{artifact_key}",
        "metadata_s3_uri": f"s3://{args.bucket}/{metadata_key}",
        "evaluation_s3_uri": f"s3://{args.bucket}/{evaluation_key}",
        "container_image_uri": handoff["container_image_uri"],
    }
    output_dir = Path(args.output_dir)
    write_json(output_dir / f"{model_name}-published.json", published)
    print(json.dumps(published, indent=2, sort_keys=True))


def write_tfvars(args: argparse.Namespace) -> None:
    cpu = read_json(args.cpu_published_file) if args.cpu_published_file else {}
    log = read_json(args.log_published_file) if args.log_published_file else {}
    payload: dict[str, Any] = {}
    if cpu:
        payload.update({
            "model_version": cpu["model_version"],
            "cpu_model_artifact_s3_uri": cpu["model_artifact_s3_uri"],
            "cpu_model_image_uri": cpu["container_image_uri"],
        })
    if log:
        payload.update({
            "model_version": payload.get("model_version", log["model_version"]),
            "log_model_artifact_s3_uri": log["model_artifact_s3_uri"],
            "log_model_image_uri": log["container_image_uri"],
        })
    write_json(Path(args.output_file), payload)
    print(f"[INFO] Wrote Terraform model vars to {args.output_file}")


def copy_for_local_package(args: argparse.Namespace) -> None:
    destination = Path(args.output_dir) / args.model_name / args.model_version / "model.tar.gz"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.local_model_artifact, destination)
    print(f"[INFO] Copied local artifact to {destination}")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)

    package_cmd = sub.add_parser("package")
    package_cmd.add_argument("--model-name", required=True)
    package_cmd.add_argument("--model-version", required=True)
    package_cmd.add_argument("--container-image-uri", required=True)
    package_cmd.add_argument("--content-type", required=True)
    package_cmd.add_argument("--response-shape", required=True)
    package_cmd.add_argument("--model-artifact-s3-uri", default="")
    package_cmd.add_argument("--local-model-artifact", default="")
    package_cmd.add_argument("--training-job-name", default="")
    package_cmd.add_argument("--tuning-job-name", default="")
    package_cmd.add_argument("--evaluation-file", default="")
    package_cmd.add_argument("--threshold", default=None)
    package_cmd.add_argument("--training-started-at", default="")
    package_cmd.add_argument("--training-completed-at", default="")
    package_cmd.add_argument("--training-data-version", default="synthetic-v1")
    package_cmd.add_argument("--git-commit", default="")
    package_cmd.add_argument("--jenkins-build-number", default=os.environ.get("BUILD_NUMBER", "local"))
    package_cmd.add_argument("--output-dir", default="dist/modelops")
    package_cmd.set_defaults(func=package)

    publish_cmd = sub.add_parser("publish")
    publish_cmd.add_argument("--handoff-file", required=True)
    publish_cmd.add_argument("--bucket", required=True)
    publish_cmd.add_argument("--s3-prefix", default="models")
    publish_cmd.add_argument("--output-dir", default="dist/modelops")
    publish_cmd.set_defaults(func=publish)

    tfvars_cmd = sub.add_parser("write-tfvars")
    tfvars_cmd.add_argument("--cpu-published-file", default="")
    tfvars_cmd.add_argument("--log-published-file", default="")
    tfvars_cmd.add_argument("--output-file", default="dist/modelops/model-artifacts.auto.tfvars.json")
    tfvars_cmd.set_defaults(func=write_tfvars)

    copy_cmd = sub.add_parser("copy-local")
    copy_cmd.add_argument("--model-name", required=True)
    copy_cmd.add_argument("--model-version", required=True)
    copy_cmd.add_argument("--local-model-artifact", required=True)
    copy_cmd.add_argument("--output-dir", default="dist/modelops")
    copy_cmd.set_defaults(func=copy_for_local_package)

    return root


def main() -> None:
    args = parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
