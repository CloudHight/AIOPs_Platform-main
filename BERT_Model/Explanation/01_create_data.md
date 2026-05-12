# `BERT_Model/01_create_data.py` Explanation

## Purpose

This script creates a synthetic labeled dataset for log anomaly detection. It generates normal and anomalous log lines, adds harder negative examples and multi-line context windows, splits the data into train/validation/test sets, and can optionally upload the results to S3.

## Main responsibilities

- Generate realistic access logs and error logs.
- Normalize noisy fields like IP addresses, timestamps, request IDs, and numbers.
- Create both normal and anomalous examples.
- Create context-window samples by joining multiple log lines with `[SEP]`.
- Split the full dataset into stratified train, validation, and test subsets.
- Save the results as JSON files.
- Optionally upload the dataset directory to S3.

## Key components

### `Sample`

A dataclass representing one training example with:

- `text`
- `label`
- `source`
- `difficulty`

### Log generation helpers

- `random_ip`
- `random_trace_id`
- `random_timestamp`
- `random_error_timestamp`
- `generate_access_log`
- `generate_error_log`

These functions create synthetic nginx-style access and error log entries with randomized fields.

### Normalization and labeling

- `normalize_log(line)`
- `label_line(line)`

`normalize_log` masks variable tokens so the model learns patterns instead of memorizing exact IDs or timestamps. `label_line` checks for anomaly-related keywords, although in the current file it is defined but not used in the main dataset construction path.

### Sample builders

- `build_normal_samples(count)`
- `build_anomaly_samples(count)`
- `build_context_windows(normal_samples, anomaly_samples, count, ...)`

These functions create the base dataset. Normal samples include access, error, and hard-negative cases. Anomaly samples include access, error, and burst-style events. Context windows combine multiple samples into one training example.

### Dataset assembly

- `to_records(samples)`
- `write_json(path, payload)`
- `upload_directory_to_s3(local_root, bucket, prefix)`
- `stratified_split(records, train_ratio, validation_ratio)`
- `create_dataset(output_dir, bucket="", s3_prefix="")`

`create_dataset` is the main entry point. It generates:

- 4,000 normal base samples
- 1,400 anomaly base samples
- 2,200 context-window samples

Then it writes:

- `train/train.json`
- `validation/validation.json`
- `test/test.json`
- `dataset_summary.json`

## Why it matters in the workflow

This is the data foundation for the BERT pipeline. Every downstream stage depends on the JSON records it writes, especially `train.py` and `02_train_model.py`.

## Inputs and outputs

Input:

- No required input files.
- Optional S3 destination through `--bucket` and `--s3-prefix`.

Output:

- Dataset directory with JSON files.
- Optional S3 upload of those files.

## Notable implementation details

- Hard negatives are intentionally designed to look suspicious while still being labeled normal.
- Context windows let the model learn from short sequences of related log lines rather than only single lines.
- The dataset is stratified by label, which helps preserve class balance across splits.
- The default CLI output path is `BERT_UPDATE/data`, which does not match the folder name `BERT_Model`. That is a small naming inconsistency.

## Assumptions and limitations

- The data is synthetic, not collected from a real system.
- Log behavior is simplified and only approximates real anomaly patterns.
- Optional S3 upload depends on `boto3` being installed and configured.
