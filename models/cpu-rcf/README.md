# CPU RCF Model

CPU Random Cut Forest model workflow for SageMaker.

This directory is the active source for CPU model data generation, training, validation, and temporary endpoint testing.

## Inference Contract

- Content type: `text/csv`
- Payload: newline-separated CPU values
- Expected response: `{"scores":[{"score":0.0}]}`

## Files

- `01_create.py` - generate synthetic time-series CPU data with anomaly labels
- `02_train.py` - train the SageMaker Random Cut Forest model
- `03_deploy.py` - deploy a trained model to a temporary SageMaker endpoint for validation
- `04_test.py` - test a deployed endpoint with batch scoring
- `05_validate.py` - validate model performance against labeled data
- `06_monitor.py` - analyze anomaly scores and produce monitoring output
- `Explanation/` - reference notes for each workflow step

## Jenkins Workflow

The supported CI/CD path is the repository wrapper:

```bash
scripts/train_cpu_model.sh
```

The wrapper runs dataset creation and training from this directory and writes handoff files under:

```text
dist/modelops/cpu-rcf/
```

Endpoint validation is optional and remains disabled by default to avoid unmanaged endpoint cost:

```bash
CPU_RUN_ENDPOINT_VALIDATION=true scripts/train_cpu_model.sh
```

## Local SageMaker Notebook Workflow

For experimentation only, run individual stages from this directory:

```python
%run 01_create.py
%run 02_train.py
%run 03_deploy.py
%run 04_test.py
%run 05_validate.py
%run 06_monitor.py
```

Production delivery should publish immutable artifacts through Jenkins and let Terraform deploy SageMaker endpoints.

## Migration History

This workflow was migrated from `RCF_Model/`. The legacy path is no longer used by Jenkins, Terraform, or the supported local workflow.

## Outputs

- `cpu_time_series_realistic.csv` - generated dataset
- `model_info.json` - trained model information
- `endpoint_info.json` - temporary endpoint information, when endpoint validation is enabled
- `rcf_scores.csv` - anomaly scores from endpoint testing
- `validation_results.csv` - validation metrics
- `analyzed_results.csv` - monitoring analysis output
