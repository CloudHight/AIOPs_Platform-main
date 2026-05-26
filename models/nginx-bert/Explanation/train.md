# `models/nginx-bert/train.py` Explanation

## Purpose

This file is the core Hugging Face training entry point used by SageMaker. It loads the dataset, normalizes the text, tokenizes inputs, trains a sequence-classification model with class weighting, evaluates it, tunes a decision threshold, and saves training artifacts.

## Main responsibilities

- Parse training arguments and SageMaker environment paths.
- Load JSON datasets from train, validation, and optional test channels.
- Normalize log text consistently.
- Tokenize text for a transformer classifier.
- Train a model with class-weighted loss.
- Evaluate the model on validation and test data.
- Choose an anomaly threshold from validation probabilities.
- Save model files and training metadata.

## Key components

### `parse_args()`

Defines hyperparameters and data/model paths, including:

- learning rate
- batch sizes
- epochs
- model name
- max sequence length
- threshold objective
- SageMaker channel and output directories
- optional `fp16` and `bf16`

### `normalize_text(text)`

Performs the same masking strategy used elsewhere in the project so the model learns structure rather than memorizing exact values.

### `load_dataset(path)`

Loads one JSON file or a directory of JSON files into a pandas DataFrame, validates that records exist, normalizes the `text` field, and ensures labels are integers.

### `LogDataset`

A PyTorch dataset wrapper around tokenized inputs and labels.

### `WeightedTrainer`

A custom Hugging Face `Trainer` subclass that overrides loss computation to use class-weighted cross-entropy. This helps compensate for label imbalance.

### `compute_metrics(eval_pred)`

Computes:

- macro F1
- anomaly-class F1
- precision
- recall
- accuracy

### `pick_threshold(labels, anomaly_probs, objective)`

Computes precision-recall-based threshold candidates and selects the best threshold according to the requested objective:

- `f1`
- `precision`
- `recall`

### `save_json(path, payload)`

Writes structured outputs like summaries and threshold configuration.

## Training flow in `main()`

1. Parse arguments.
2. Resolve numeric precision mode for GPU execution.
3. Load train, validation, and optional test datasets.
4. Load the tokenizer and model.
5. Tokenize all text.
6. Compute class weights from training label distribution.
7. Configure `TrainingArguments`.
8. Train with early stopping.
9. Save the best model and tokenizer.
10. Evaluate on validation data.
11. Predict validation probabilities and choose the best anomaly threshold.
12. Optionally score the test set using that threshold.
13. Save:
- `training_summary.json`
- `threshold_config.json`
14. Print threshold metrics so SageMaker can capture them as training metrics.

## Why it matters in the workflow

This is the real model-building logic behind the SageMaker tuning job launched by `02_train_model.py`.

## Inputs and outputs

Input:

- Train, validation, and optional test JSON datasets
- Hugging Face model name
- Hyperparameters from CLI or SageMaker

Output:

- Saved model weights
- tokenizer files
- `training_summary.json`
- `threshold_config.json`
- printed metrics for SageMaker log parsing

## Notable implementation details

- Class weighting is built from the observed label distribution rather than fixed manually.
- Early stopping is enabled with patience of 2 epochs.
- The best checkpoint is selected by `eval_f1_anomaly`, not overall accuracy.
- Threshold tuning happens after validation scoring, which separates ranking quality from final binary labeling.

## Assumptions and limitations

- The script expects JSON records with at least `text` and `label`.
- The threshold is tuned on validation data and then reused for testing and deployment.
- It depends on the Hugging Face and PyTorch stacks being available in the runtime environment.
