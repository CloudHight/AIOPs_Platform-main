# Nginx BERT Model

Nginx/log anomaly classifier workflow for SageMaker Hugging Face training and inference.

This directory is the active source for log dataset generation, SageMaker tuning, validation, inference code, and temporary endpoint testing.

## Inference Contract

- Content type: `application/json`
- Payload: `{"inputs":"<normalized log line>"}`
- Expected response: list of label/score/threshold dictionaries

## Files

- `01_create_data.py` - generate normalized synthetic log datasets for training, validation, and testing
- `02_train_model.py` - launch a SageMaker Hugging Face hyperparameter tuning job
- `03_validate_model.py` - inspect a SageMaker training or tuning job and export validation metrics
- `04_deploy_model.py` - deploy a trained model to a temporary SageMaker endpoint for validation
- `05_test_model.py` - test a local saved model or deployed endpoint
- `train.py` - Hugging Face training entry point used by SageMaker
- `inference.py` - SageMaker inference entry point with threshold-aware prediction logic
- `Explanation/` - reference notes for each workflow step

## Jenkins Workflow

The supported CI/CD path is the repository wrapper:

```bash
MODEL_ARTIFACT_BUCKET=<artifact-bucket> scripts/train_log_model.sh
```

The wrapper creates datasets from this directory, uploads them to S3, launches SageMaker tuning, and writes handoff files under:

```text
dist/modelops/nginx-bert/
```

Set `LOG_TRAIN_WAIT=true` when Jenkins should wait for training completion and export evaluation metrics:

```bash
MODEL_ARTIFACT_BUCKET=<artifact-bucket> LOG_TRAIN_WAIT=true scripts/train_log_model.sh
```

## Local SageMaker Notebook Workflow

For experimentation only, run individual stages from this directory:

```python
%run 01_create_data.py --output-dir data --bucket <your-bucket> --s3-prefix <your-prefix>/
%run 02_train_model.py --bucket <your-bucket> --prefix <your-prefix> --train-script train.py --wait
%run 03_validate_model.py --tuning-job-name <your-tuning-job-name>
%run 04_deploy_model.py --tuning-job-name <your-tuning-job-name> --endpoint-name nginx-anomaly-detector-prod
%run 05_test_model.py --endpoint-name nginx-anomaly-detector-prod
```

Production delivery should publish immutable artifacts through Jenkins and let Terraform deploy SageMaker endpoints.

## Migration History

This workflow was migrated from `BERT_Model/`. The legacy path is no longer used by Jenkins, Terraform, or the supported local workflow.
