# `models/cpu-rcf/01_create.py` Explanation

## Purpose

This script generates a synthetic CPU-utilization dataset for anomaly detection experiments. It creates both normal and anomalous samples and saves them to a CSV file for the later training and evaluation steps.

## Main function

`create_dataset(output_file="cpu_time_series_realistic.csv")`

This is the only function in the file and is also called when the script is run directly.

## What it does

1. Creates 2,000 timestamped records starting from `2025-08-19 00:00`.
2. Generates normal CPU values for 95% of the dataset using a uniform range of `0.5` to `80.0`.
3. Generates anomalous CPU values for the remaining 5% using a uniform range of `85.0` to `100.0`.
4. Assigns labels:
- `0` for normal
- `1` for anomaly
5. Shuffles the combined records so anomalies are mixed into the timeline.
6. Builds a DataFrame with:
- `Timestamp`
- `Average`
- `anomaly`
7. Prints summary statistics for both classes.
8. Writes the dataset to CSV.

## Why it matters in the workflow

This file is the data source for the rest of the pipeline. Every later step expects the dataset it creates, especially the `Average` feature column and the `anomaly` ground-truth label.

## Inputs and outputs

Input:
- No external input is required.

Output:
- CSV file, defaulting to `cpu_time_series_realistic.csv`

## Notable implementation details

- The script uses a deliberately clean separation between normal and anomalous ranges: normal values stop at `80`, anomalies start at `85`.
- Because of that gap, the downstream model has an easier anomaly-detection problem than it would on real production data.
- The timestamps use `i % 1440`, so after one day the minute offsets repeat. That means timestamps are not strictly increasing across all 2,000 records.
- The file imports `random` and uses `random.shuffle` to randomize row order after generation.

## Assumptions and limitations

- The dataset is synthetic and simplified.
- Only one feature is modeled: CPU average utilization.
- There is no trend, seasonality, or realistic temporal dependence after shuffling.
- Since labels are included in the dataset, later validation can compare predicted anomalies against known ground truth.
