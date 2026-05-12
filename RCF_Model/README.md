# ML Workflow for Anomaly Detection

This repository contains a modular ML workflow for anomaly detection using Amazon SageMaker's Random Cut Forest algorithm.

## Files

- `01_create.py` - Generate synthetic time series data with anomalies
- `02_train.py` - Train Random Cut Forest model
- `03_deploy.py` - Deploy model to SageMaker endpoint
- `04_test.py` - Test deployed model with batch scoring
- `05_validate.py` - Validate model performance against ground truth
- `06_monitor.py` - Monitor performance and analyze results

## Usage

### Individual Stages (SageMaker Jupyter)

```python
%run 01_create.py    # Creates cpu_time_series_with_anomalies.csv
%run 02_train.py     # Creates model_info.json
%run 03_deploy.py    # Creates endpoint_info.json
%run 04_test.py      # Creates rcf_scores.csv
%run 05_validate.py  # Creates validation_results.csv
%run 06_monitor.py   # Creates analyzed_results.csv
```

## Output Files

- `cpu_time_series_with_anomalies.csv` - Synthetic dataset
- `model_info.json` - Trained model information
- `endpoint_info.json` - Deployed endpoint details
- `rcf_scores.csv` - Anomaly scores from model
- `validation_results.csv` - Performance metrics
- `analyzed_results.csv` - Final analysis results

## Requirements

- Amazon SageMaker environment
- pandas, numpy, scikit-learn
- Appropriate IAM permissions for SageMaker

## Cleanup

Remember to delete endpoints to avoid charges:

```python
from 05_deploy import cleanup_endpoint
cleanup_endpoint()
```