import argparse
import json
from pathlib import Path

import boto3
from sagemaker import get_execution_role
from sagemaker.huggingface import HuggingFaceModel


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-artifacts-uri", default="")
    parser.add_argument("--training-job-name", default="")
    parser.add_argument("--tuning-job-name", default="")
    parser.add_argument("--endpoint-name", required=True)
    parser.add_argument("--instance-type", default="ml.g5.xlarge")
    return parser.parse_args()


def resolve_model_artifacts_uri(model_artifacts_uri: str, training_job_name: str, tuning_job_name: str) -> str:
    if model_artifacts_uri:
        return model_artifacts_uri

    sm_client = boto3.client("sagemaker")
    if tuning_job_name:
        tuning = sm_client.describe_hyper_parameter_tuning_job(
            HyperParameterTuningJobName=tuning_job_name
        )
        best_job = tuning.get("BestTrainingJob", {})
        training_job_name = best_job.get("TrainingJobName", "")
        if not training_job_name:
            status = tuning.get("HyperParameterTuningJobStatus", "Unknown")
            raise ValueError(
                f"No best training job is available yet for tuning job {tuning_job_name}. Current status: {status}"
            )

    if not training_job_name:
        raise ValueError("Provide one of --model-artifacts-uri, --training-job-name, or --tuning-job-name.")

    training = sm_client.describe_training_job(TrainingJobName=training_job_name)
    return training["ModelArtifacts"]["S3ModelArtifacts"]


def deploy_production_model(model_artifacts_uri, endpoint_name, role=None):
    role = role or get_execution_role()
    source_dir = str(Path(__file__).resolve().parent)
    model = HuggingFaceModel(
        model_data=model_artifacts_uri,
        transformers_version="4.26",
        pytorch_version="1.13",
        py_version="py39",
        role=role,
        entry_point="inference.py",
        source_dir=source_dir,
    )

    print(f"[INFO] Deploying production model to endpoint: {endpoint_name}")
    predictor = model.deploy(
        initial_instance_count=1,
        instance_type="ml.g5.xlarge",
        endpoint_name=endpoint_name,
    )
    print(f"[INFO] Model deployed successfully to endpoint: {endpoint_name}")
    print("[INFO] Endpoint inference uses threshold_config.json from the model artifact when available")
    return predictor


def test_production_endpoint(endpoint_name, sample_texts):
    runtime = boto3.client("sagemaker-runtime")
    print("[INFO] Testing production endpoint...")
    for idx, text in enumerate(sample_texts, start=1):
        response = runtime.invoke_endpoint(
            EndpointName=endpoint_name,
            ContentType="application/json",
            Body=json.dumps({"inputs": text}),
        )
        result = json.loads(response["Body"].read().decode())
        print(f"  Sample {idx}: {result}")


if __name__ == "__main__":
    args = parse_args()
    model_artifacts_uri = resolve_model_artifacts_uri(
        model_artifacts_uri=args.model_artifacts_uri,
        training_job_name=args.training_job_name,
        tuning_job_name=args.tuning_job_name,
    )
    endpoint_name = args.endpoint_name
    sample_texts = [
        '<IP> - - [<TIME>] "GET /health HTTP/1.1" 200 <NUM> "-" "ELB-HealthChecker/2.0" rt=<FLOAT> req_id=<ID>',
        '<IP> - - [<TIME>] "POST /api/payments HTTP/1.1" 503 <NUM> "-" "Mozilla/5.0" rt=<FLOAT> req_id=<ID>',
    ]
    print(f"[INFO] Resolved model artifact: {model_artifacts_uri}")
    deploy_production_model(model_artifacts_uri, endpoint_name)
    test_production_endpoint(endpoint_name, sample_texts)
    print(f"[INFO] Production deployment complete. Endpoint: {endpoint_name}")
