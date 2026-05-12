# `BERT_Model/04_deploy_model.py` Explanation

## Purpose

This script deploys the trained anomaly-detection model to a SageMaker real-time endpoint. It can resolve the model artifact from a direct S3 URI, a training job, or a tuning job, then deploy the model using the custom `inference.py` entry point.

## Main functions

- `parse_args()`
- `resolve_model_artifacts_uri(model_artifacts_uri, training_job_name, tuning_job_name)`
- `deploy_production_model(model_artifacts_uri, endpoint_name, role=None)`
- `test_production_endpoint(endpoint_name, sample_texts)`

## What it does

### Model artifact resolution

`resolve_model_artifacts_uri(...)` selects the artifact source in this order:

1. Use `--model-artifacts-uri` if supplied directly.
2. If a tuning job is supplied, ask SageMaker for the best training job from that tuning job.
3. If a training job is supplied, describe that job directly.
4. Return the `S3ModelArtifacts` path from SageMaker metadata.

### Deployment

`deploy_production_model(...)`:

1. Gets the SageMaker execution role.
2. Points `source_dir` at the current folder.
3. Creates a `HuggingFaceModel` configured with:
- model artifact in S3
- `inference.py` as the entry point
- Hugging Face runtime versions
4. Deploys the model to the requested endpoint name.

### Post-deploy smoke test

`test_production_endpoint(...)` sends two normalized sample log lines to the new endpoint and prints the responses.

## Why it matters in the workflow

This file turns the trained artifact into a running inference service. It is the production handoff point between model training and live predictions.

## Inputs and outputs

Input:

- One of:
- `--model-artifacts-uri`
- `--training-job-name`
- `--tuning-job-name`
- Required `--endpoint-name`

Output:

- A deployed SageMaker endpoint
- Console output showing the resolved artifact and test responses

## Notable implementation details

- The parser accepts `--instance-type`, but `deploy_production_model(...)` currently ignores that argument and hard-codes `ml.g5.xlarge`.
- Deployment uses `inference.py`, which means prediction behavior is defined by the custom normalization and threshold logic in that file.
- The script performs an immediate smoke test after deployment rather than only deploying and exiting.

## Assumptions and limitations

- It assumes a SageMaker-compatible environment with valid AWS credentials and permissions.
- It does not handle endpoint updates, blue/green deployment, or rollback logic.
- It does not include a cleanup helper for deleting endpoints after use.
