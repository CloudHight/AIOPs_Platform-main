# `models/cpu-rcf/06_monitor.py` Explanation

## Purpose

This script performs a post-scoring operational analysis. It applies an anomaly threshold, compares detections with ground truth, prints score statistics, saves an enriched result file, and provides a simple drift check.

## Main functions

`analyze_anomalies(data_file="cpu_time_series_realistic.csv", scores_file="rcf_scores.csv", threshold_score=0.50)`

This combines source data and scores, marks predicted anomalies, and prints summary diagnostics.

`monitor_performance(df)`

This performs a lightweight monitoring pass on the analyzed DataFrame.

## What `analyze_anomalies` does

1. Loads the dataset and the score file.
2. Adds the `RCFScore` column to the source DataFrame.
3. Creates `RCFAnomaly` using the fixed threshold:
- `1` when `RCFScore > threshold_score`
- `0` otherwise
4. Prints:
- how many rows crossed the threshold
- how many true normal and anomalous rows exist
- detected normal and anomaly counts
- false positives and false negatives
- overall score statistics
5. Prints the top detected anomalies sorted by highest score.
6. Saves the enriched DataFrame to `analyzed_results.csv`.
7. Returns the enriched DataFrame.

## What `monitor_performance` does

1. Prints basic dataset and score statistics.
2. Compares a historical mean CPU level with a recent mean CPU level.
3. Computes a simple drift indicator:
- `abs(recent_mean - historical_mean) / historical_mean`
4. Prints a warning if drift exceeds `0.1`.

## Why it matters in the workflow

This file is the operational review stage. It takes the raw model scores and turns them into more interpretable monitoring outputs.

## Inputs and outputs

Input:
- `cpu_time_series_realistic.csv`
- `rcf_scores.csv`

Output:
- `analyzed_results.csv`

## Notable implementation details

- The default threshold is fixed at `0.50`, unlike `05_validate.py`, which derives a threshold from the current labeled data.
- `analyze_anomalies` writes `analyzed_results.csv` twice. The second write is redundant.
- The drift logic compares the first half of the dataset to the last quarter, which is a very rough heuristic rather than a production-grade drift monitor.

## Assumptions and limitations

- The monitoring logic assumes labeled ground truth is available.
- There is no alerting, persistence layer, dashboard integration, or trend tracking across multiple runs.
- Drift detection is based only on mean CPU usage, not on score distribution or richer statistical tests.
