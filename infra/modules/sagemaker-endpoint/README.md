# sagemaker-endpoint

Deploys a SageMaker real-time endpoint from an approved immutable model artifact.

This module does not train models. Jenkins/model scripts must publish:

- `model.tar.gz`
- `metadata.json`
- `evaluation.json`

Then pass the artifact URI and inference image URI into Terraform.
