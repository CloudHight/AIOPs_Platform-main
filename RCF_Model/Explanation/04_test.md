# `RCF_Model/04_test.py` Explanation

## Purpose

This script sends the synthetic CPU values to the deployed SageMaker endpoint, collects the Random Cut Forest anomaly scores, saves them, and prints a quick diagnostic summary.

## Main functions

`extract_score_value(record)`

This helper normalizes several possible SageMaker response shapes into a single float score.

`test_model(data_file="cpu_time_series_realistic.csv", endpoint_info_file="endpoint_info.json", scores_file="rcf_scores.csv")`

This is the main inference and analysis function.

## What `extract_score_value` does

It tries to handle different score formats:

- dictionary with `score`
- dictionary with `scores`
- list-wrapped responses
- direct numeric values

If parsing fails, it returns `0.0`.

## What `test_model` does

1. Loads the deployed endpoint name from `endpoint_info.json`.
2. Loads the dataset from CSV.
3. Builds a SageMaker `Predictor` for the endpoint.
4. Sets:
- `CSVSerializer` for requests
- `JSONDeserializer` for responses
5. Extracts the `Average` column and reshapes it for prediction.
6. Sends the full batch to the endpoint.
7. Parses the returned scores into a flat Python list.
8. Pads missing scores with `0.0` if the returned length is short.
9. Saves the result to `rcf_scores.csv`.
10. Computes score summaries for the whole dataset, then separately for normal and anomaly labels.
11. Estimates a threshold using the midpoint between the highest normal score and lowest anomaly score.
12. Returns the scores as a NumPy array.

## Why it matters in the workflow

This file is the first place where the trained model is actually exercised against data. It generates the anomaly scores that are later validated and monitored.

## Inputs and outputs

Input:
- `cpu_time_series_realistic.csv`
- `endpoint_info.json`

Output:
- `rcf_scores.csv`

## Notable implementation details

- The code compares returned scores against the original dataset labels, even though the model itself was trained unsupervised.
- The threshold is not fixed in advance; it is derived from the observed separation in the current scored dataset.
- The file imports `re`, but `re` is not used anywhere.
- Returning `0.0` on parsing failure makes the script resilient, but it can also hide malformed responses.

## Assumptions and limitations

- The script assumes the endpoint is alive and reachable.
- It assumes the endpoint can accept the full input batch at once.
- If the endpoint response is incomplete, zero-padding may distort the evaluation results instead of failing fast.
