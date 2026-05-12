# `RCF_Model/05_validate.py` Explanation

## Purpose

This script evaluates how well the anomaly scores separate the labeled normal and anomalous records. It converts scores into binary predictions using a derived threshold and then computes standard classification metrics.

## Main function

`validate_model(data_file="cpu_time_series_realistic.csv", scores_file="rcf_scores.csv")`

## What it does

1. Loads the original dataset and the generated RCF scores.
2. Splits scores into two groups using the dataset's `anomaly` labels.
3. Prints summary statistics for normal and anomalous score distributions.
4. Computes an "optimal" threshold as:
- midpoint between `normal_scores.max()` and `anomaly_scores.min()`
5. Converts continuous RCF scores into binary predictions using that threshold.
6. Calculates:
- accuracy
- precision
- recall
- F1-score
7. Prints a diagnosis based on expected average score ranges.
8. Saves the metrics and threshold to `validation_results.csv`.
9. Returns a Python dictionary of results.

## Why it matters in the workflow

This is the formal evaluation stage. It tells you whether the scoring behavior observed in `04_test.py` translates into useful anomaly classification performance.

## Inputs and outputs

Input:
- `cpu_time_series_realistic.csv`
- `rcf_scores.csv`

Output:
- `validation_results.csv`

## Metrics used

The script relies on `sklearn.metrics` for:

- `accuracy_score`
- `precision_score`
- `recall_score`
- `f1_score`

## Notable implementation details

- The threshold is derived from the same labeled dataset used for evaluation, so this is not a strict holdout-style validation.
- The diagnosis logic expects normal mean scores below `0.3` and anomaly mean scores above `0.7`.
- `zero_division=0` prevents metric calculation from failing if no positive predictions are made.

## Assumptions and limitations

- The method assumes the score distributions are separable enough that a single midpoint threshold is meaningful.
- There is no train/validation/test split.
- Since the dataset is synthetic and cleanly separated, the reported metrics can look better than real-world performance.
