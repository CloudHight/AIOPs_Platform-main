# BERT_Model

This folder contains a BERT-based log anomaly detection workflow designed for Amazon SageMaker. The pipeline covers synthetic dataset generation, SageMaker hyperparameter tuning, validation through SageMaker metadata, deployment to a real-time endpoint, and inference testing.

## Files

- `01_create_data.py`: generates normalized synthetic log datasets for training, validation, and testing, with hard negatives and context-window samples
- `02_train_model.py`: launches a SageMaker Hugging Face hyperparameter tuning job for the classifier
- `03_validate_model.py`: inspects a SageMaker training job or tuning job and prints the final metrics and model artifact location
- `04_deploy_model.py`: deploys a trained model to a SageMaker endpoint from an artifact URI, training job, or tuning job
- `05_test_model.py`: tests either a local saved model directory or a deployed SageMaker endpoint with sample log lines
- `train.py`: Hugging Face training entry point used by SageMaker during model training
- `inference.py`: SageMaker inference entry point for deployed endpoints, including threshold-aware prediction logic
- `README.md`: this overview of the folder and workflow

## Recommended Workflow

### 1. Create the dataset

```bash
%run 01_create_data.py --output-dir BERT_Model/data --bucket <your-bucket> --s3-prefix <your-bucket-prefix>/
```

This creates:

- `train/train.json`
- `validation/validation.json`
- `test/test.json`
- `dataset_summary.json`

If `--bucket` and `--s3-prefix` are provided, the JSON files are also uploaded to S3.

### 2. Launch SageMaker tuning

```bash
%run 02_train_model.py --bucket <your-bucket> --prefix <your-bucket-prefix> --train-script train.py --wait
```

This script:

- configures a SageMaker Hugging Face estimator
- launches a hyperparameter tuning job
- optionally monitors the tuning job until it finishes

### 3. Validate the result

For a tuning job:

```bash
%run 03_validate_model.py --tuning-job-name <your-tuning-job-name>
```

For a single training job:

```bash
%run 03_validate_model.py --training-job-name <your-training-job-name>
```

This prints:

- tuning or training status
- best training job
- model artifact S3 URI
- reported metrics such as F1, precision, recall, accuracy, and threshold-related values when available

### 4. Deploy the model

Deploy from a tuning job:

```bash
%run 04_deploy_model.py --tuning-job-name <your-tuning-job-name> --endpoint-name nginx-anomaly-detector-prod
```

Deploy from a training job:

```bash
%run 04_deploy_model.py --training-job-name <your-training-job-name> --endpoint-name nginx-anomaly-detector-prod
```

Deploy from a direct model artifact URI:

```bash
%run 04_deploy_model.py --model-artifacts-uri s3://<your-bucket>/<path>/model.tar.gz --endpoint-name nginx-anomaly-detector-prod
```

The deployment uses `inference.py` as the SageMaker entry point.

### 5. Test the model

Test a local saved model directory:

```bash
%run 05_test_model.py --model-dir model
```

Test a deployed endpoint:

```bash
%run 05_test_model.py --endpoint-name nginx-anomaly-detector-prod
```

## Outputs and Artifacts

### Dataset generation

- `train/train.json`
- `validation/validation.json`
- `test/test.json`
- `dataset_summary.json`

### Training

Artifacts saved by `train.py` into the model directory include:

- Hugging Face model files
- tokenizer files
- `training_summary.json`
- `threshold_config.json`

### Deployment and inference

- SageMaker model artifact in S3, typically `model.tar.gz`
- a deployed endpoint if `04_deploy_model.py` is used

## Notes

- The training and inference code both normalize logs by masking IPs, timestamps, numeric values, and request IDs.
- `train.py` computes class weights to handle label imbalance and tunes a decision threshold from validation predictions.
- `inference.py` loads `threshold_config.json` when present and uses it to convert anomaly scores into labels.
- `02_train_model.py` defaults to GPU-backed SageMaker instances such as `ml.g5.xlarge`, so quota and cost should be checked before running.
