# `models/nginx-bert/inference.py` Explanation

## Purpose

This file defines the custom SageMaker inference entry point used by deployed endpoints. It loads the trained transformer model, applies the same text normalization used in training, runs prediction, and formats the output response.

## Main functions

- `normalize_text(text)`
- `model_fn(model_dir)`
- `input_fn(request_body, request_content_type)`
- `predict_fn(inputs, model_assets)`
- `output_fn(prediction, accept)`

## What each function does

### `normalize_text(text)`

Masks IP addresses, timestamps, request IDs, IDs, floats, and numbers so deployed inference receives text in the same representation used during training.

### `model_fn(model_dir)`

Loads:

- the tokenizer
- the sequence-classification model
- the anomaly threshold from `threshold_config.json` when available

It also moves the model to GPU if one is available and returns all loaded assets in a dictionary.

### `input_fn(request_body, request_content_type)`

Accepts only `application/json` requests. It supports either:

- a single string input
- a list of string inputs

It normalizes all inputs before returning them for prediction.

### `predict_fn(inputs, model_assets)`

1. Tokenizes the input texts.
2. Moves tensors to the same device as the model.
3. Runs the model without gradients.
4. Converts logits into anomaly probabilities.
5. Applies the stored threshold to assign:
- `LABEL_1` for anomaly
- `LABEL_0` for normal
6. Returns a list of dictionaries containing `label`, `score`, and `threshold`.

### `output_fn(prediction, accept)`

Serializes prediction results to JSON and only accepts `application/json` or `*/*`.

## Why it matters in the workflow

This file is the runtime contract for production inference. `04_deploy_model.py` explicitly deploys the model with this script, so endpoint behavior depends on the logic here.

## Inputs and outputs

Input:

- JSON request body containing `inputs`

Output:

- JSON response with predicted labels, scores, and threshold

## Notable implementation details

- The threshold is loaded from the trained model artifact rather than hard-coded, which keeps deployment behavior aligned with training-time validation.
- Input normalization is duplicated here instead of being imported from `train.py`, which keeps deployment self-contained.
- The maximum sequence length during inference is fixed at `192`, matching the default training configuration.

## Assumptions and limitations

- Requests must use JSON.
- The payload format must contain strings or lists of strings.
- If `threshold_config.json` is missing, the endpoint falls back to `0.5`.
