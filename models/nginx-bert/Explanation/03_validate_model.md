# `models/nginx-bert/03_validate_model.py` Explanation

## Purpose

This script validates the outcome of model training by reading SageMaker metadata for either a single training job or a hyperparameter tuning job. It prints a summary of status, model artifact location, and reported metrics.

## Main functions

- `parse_args()`
- `format_metrics(metrics)`
- `resolve_from_tuning_job(sm_client, tuning_job_name)`
- `resolve_from_training_job(sm_client, training_job_name)`
- `print_summary(payload)`
- `main()`

## What it does

### Input mode selection

The script requires exactly one of:

- `--training-job-name`
- `--tuning-job-name`

If both or neither are provided, it raises an error.

### Metric formatting

`format_metrics(...)` turns SageMaker’s metric list format into a plain dictionary keyed by metric name.

### Tuning-job resolution

`resolve_from_tuning_job(...)`:

1. Describes the tuning job.
2. Finds the best training job selected by SageMaker.
3. Loads the details of that best training job.
4. Returns a payload containing tuning metadata, training metadata, objective metric, and tuned hyperparameters.

### Training-job resolution

`resolve_from_training_job(...)` loads metadata directly for a single training job and returns a similar payload structure without tuning-specific fields.

### Summary output

`print_summary(...)` prints:

- tuning job name and status, if applicable
- best objective metric
- tuned hyperparameters
- best training job name
- training status
- secondary training status
- model artifact S3 URI
- selected metrics such as F1, precision, recall, accuracy, and threshold-related values

## Why it matters in the workflow

This is the inspection step after training. It gives a compact view of what SageMaker produced, without downloading model artifacts or running separate evaluation locally.

## Inputs and outputs

Input:

- SageMaker training job name or tuning job name

Output:

- Printed validation summary in the console

## Notable implementation details

- For tuning jobs, it refuses to proceed until a best training job is available.
- It prioritizes a curated list of "interesting" metrics before falling back to printing all final metrics.
- It does not write a report file; it is a read-and-print utility.

## Assumptions and limitations

- The script depends entirely on SageMaker metadata being available and accurate.
- It does not compare predictions against a local dataset.
- It does not inspect the contents of `model.tar.gz`; it only reports the artifact location and metrics SageMaker recorded.
