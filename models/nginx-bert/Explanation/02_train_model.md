# `models/nginx-bert/02_train_model.py` Explanation

## Purpose

This script launches a SageMaker Hugging Face hyperparameter tuning job for the anomaly-classification model and can optionally monitor that tuning job until it completes.

## Main functions

- `parse_args()`
- `launch_sagemaker_tuning(train_uri, val_uri, test_uri, train_script="train.py", role=None)`
- `monitor_tuning_job(tuning_job_name, poll_seconds)`

## What it does

### Argument parsing

The script accepts:

- `--bucket` for the S3 bucket containing the dataset
- `--prefix` for the dataset prefix in S3
- `--train-script` for the training entry point, defaulting to `train.py`
- `--wait` to keep monitoring after launching
- `--poll-seconds` to control monitor frequency

### Tuning job creation

`launch_sagemaker_tuning(...)`:

1. Verifies the training script exists locally.
2. Gets the SageMaker execution role.
3. Builds a `HuggingFace` estimator.
4. Configures base hyperparameters such as:
- `epochs`
- `model_name`
- `learning_rate`
- `per_device_train_batch_size`
- `max_seq_length`
- `threshold_objective`
5. Registers metric definitions so SageMaker can extract metrics from training logs.
6. Wraps the estimator in a `HyperparameterTuner`.
7. Starts the tuning job using S3 input channels for train, validation, and test data.

### Monitoring

`monitor_tuning_job(...)` repeatedly queries SageMaker and prints:

- overall tuning status
- counts of completed, in-progress, failed, and stopped jobs
- current best training job and best objective metric when available

## Why it matters in the workflow

This file is the orchestration layer for model training in SageMaker. It does not train the model itself; instead, it tells SageMaker to run `train.py` across a set of hyperparameter combinations.

## Inputs and outputs

Input:

- S3 dataset directories:
- `s3://<bucket>/<prefix>/train/`
- `s3://<bucket>/<prefix>/validation/`
- `s3://<bucket>/<prefix>/test/`
- Local training script, usually `train.py`

Output:

- A SageMaker hyperparameter tuning job
- Console logs showing the launched tuning job name and optional progress updates

## Notable implementation details

- The estimator uses GPU-backed instance type `ml.g5.xlarge`.
- `max_parallel_jobs=1` means tuning runs sequentially, likely to control cost or quota pressure.
- The objective metric is `eval_f1_anomaly`, which means the tuning process optimizes anomaly-class F1 specifically.
- The metric extraction regex expects metric names printed from `train.py`.

## Assumptions and limitations

- This script assumes it is running in an environment with SageMaker access and a valid execution role.
- It depends on the dataset already being uploaded to S3 in the expected folder structure.
- It only launches tuning jobs; it does not support plain non-tuned training directly.
