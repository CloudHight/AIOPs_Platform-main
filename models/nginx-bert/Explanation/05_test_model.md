# `models/nginx-bert/05_test_model.py` Explanation

## Purpose

This script tests the anomaly classifier either locally from a saved model directory or remotely through a deployed SageMaker endpoint.

## Main functions

- `parse_args()`
- `normalize_text(text)`
- `load_threshold(model_dir)`
- `test_local(model_dir, samples)`
- `test_endpoint(endpoint_name, samples)`

## What it does

### Text normalization

`normalize_text(...)` masks IP addresses, timestamps, request IDs, numeric identifiers, floating-point values, and integers. This keeps test inputs aligned with the format used in training and deployment.

### Local test mode

`test_local(...)`:

1. Loads the tokenizer and model from a local directory.
2. Loads the decision threshold from `threshold_config.json`, defaulting to `0.5`.
3. Tokenizes the sample inputs.
4. Runs inference with PyTorch.
5. Converts anomaly probabilities into:
- `LABEL_1` for anomaly
- `LABEL_0` for normal
6. Prints scores alongside the original sample text.

### Endpoint test mode

`test_endpoint(...)`:

1. Creates a SageMaker Runtime client.
2. Sends normalized sample inputs to the endpoint as JSON.
3. Prints the endpoint response for each sample.

### Script entry

The script includes a built-in list of example log lines covering both normal and anomalous patterns. If `--endpoint-name` is provided, it tests the endpoint. Otherwise, it tests a local model directory.

## Why it matters in the workflow

This is the quick verification stage for model behavior. It helps confirm that a local artifact or deployed endpoint is classifying representative logs as expected.

## Inputs and outputs

Input:

- Local model directory through `--model-dir`
- Or deployed SageMaker endpoint through `--endpoint-name`

Output:

- Printed inference results for sample log lines

## Notable implementation details

- Local testing uses the threshold learned during training if `threshold_config.json` exists.
- Endpoint testing sends already-normalized text to the deployed inference service.
- The built-in samples mix access logs and error logs to exercise multiple anomaly styles.

## Assumptions and limitations

- The script is a smoke test, not a full benchmark.
- It uses a fixed set of hard-coded examples instead of a dataset file.
- Endpoint testing requires network access and the endpoint to be available.
