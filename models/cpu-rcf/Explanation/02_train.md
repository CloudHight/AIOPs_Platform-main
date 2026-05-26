# `models/cpu-rcf/02_train.py` Explanation

## Purpose

This script trains an Amazon SageMaker Random Cut Forest model using the synthetic CPU dataset created in `01_create.py`.

## Main function

`train_model(input_file="cpu_time_series_realistic.csv", model_info_file="model_info.json")`

## What it does

1. Loads the dataset CSV.
2. Verifies that the file is not empty and contains the `Average` column.
3. Extracts the `Average` values as a one-dimensional training array.
4. Prints dataset statistics and selected hyperparameters.
5. Creates a SageMaker `RandomCutForest` estimator.
6. Launches training with `rcf.fit(...)`.
7. Saves the training job name to `model_info.json`.
8. Returns the trained estimator object.

## Why it matters in the workflow

This file is the training stage of the pipeline. It converts the synthetic numeric values into a trained anomaly-detection model that can later be deployed and queried.

## Inputs and outputs

Input:
- `cpu_time_series_realistic.csv`

Output:
- `model_info.json` containing the SageMaker training job name

## SageMaker configuration

The estimator is configured with:

- `instance_count=1`
- `instance_type='ml.m5.large'`
- `num_trees=100`
- `num_samples_per_tree=256`
- `feature_dim=1`
- evaluation metrics for accuracy and precision/recall/F-score

## Notable implementation details

- Training uses only the `Average` column. The `Timestamp` and `anomaly` label are ignored during model fitting.
- `get_execution_role()` means the script assumes it is running inside a SageMaker environment with a valid IAM execution role.
- The saved artifact is minimal: only the training job name is preserved, not a broader config bundle.

## Important caveat

The docstring still describes an older data distribution using Gaussian clusters around 5% and 92% CPU. That does not match the current dataset generator in `01_create.py`, which uses uniform ranges from `0.5-80` and `85-100`.

## Assumptions and limitations

- This script depends on SageMaker SDK availability and permissions.
- It does not perform local training.
- It does not validate whether the dataset distribution is sensible before training.
