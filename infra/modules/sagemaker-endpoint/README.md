# sagemaker-endpoint

Deploys a SageMaker real-time endpoint from an approved immutable model artifact.

This module does not train models. Jenkins/model scripts must publish:

- `model.tar.gz`
- `metadata.json`
- `evaluation.json`

Then pass the artifact URI and inference image URI into Terraform.

Resource names are sanitized inside the module before creating SageMaker resources. Branch or model versions such as `release-v1.0.0-24` are converted to SageMaker-safe names by replacing unsupported characters with hyphens and truncating long names with a stable hash suffix.
