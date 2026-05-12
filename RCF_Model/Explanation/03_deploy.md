# `RCF_Model/03_deploy.py` Explanation

## Purpose

This script deploys the trained Random Cut Forest model to a SageMaker real-time inference endpoint and stores the endpoint name for later use.

## Main functions

`deploy_model(...)`

This deploys the model to a SageMaker endpoint.

`cleanup_endpoint(endpoint_info_file="endpoint_info.json")`

This deletes the deployed endpoint to avoid ongoing charges.

## What `deploy_model` does

1. Loads `model_info.json`.
2. Reads the saved SageMaker training job name.
3. Reattaches to that trained model using `RandomCutForest.attach(...)`.
4. Deploys the model to a named endpoint.
5. Saves the endpoint name to `endpoint_info.json`.
6. Returns the SageMaker predictor object.

## Default deployment settings

- `instance_count=1`
- `instance_type="ml.t2.medium"`
- `endpoint_name="cpu-anomaly-detector-prod"`

## Why it matters in the workflow

This file is the bridge between training and inference. Without deployment, the model cannot be queried by `04_test.py`.

## Inputs and outputs

Input:
- `model_info.json`

Output:
- `endpoint_info.json`

## What `cleanup_endpoint` does

1. Loads the saved endpoint name from `endpoint_info.json`.
2. Creates a SageMaker client through `boto3`.
3. Sends a `delete_endpoint` request.
4. Prints success or the caught error.

## Notable implementation details

- Deployment uses `RandomCutForest.attach(...)`, so it assumes the training job still exists and is accessible.
- The endpoint name is hard-coded by default, which may cause conflicts if the same name is reused in the same AWS account and region.
- Cleanup only deletes the endpoint, not any endpoint configuration or model artifacts that may also remain in SageMaker.

## Assumptions and limitations

- The script requires valid AWS and SageMaker permissions.
- There is no retry logic, status polling, or defensive validation around deployment failures.
- Error handling is minimal and only present in the cleanup helper.
