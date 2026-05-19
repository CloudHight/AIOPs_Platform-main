# sagemaker-endpoint

Deploys a SageMaker real-time endpoint from an approved immutable model artifact.

This module does not train models. Jenkins/model scripts must publish:

- `model.tar.gz`
- `metadata.json`
- `evaluation.json`

Then pass the artifact URI and inference image URI into Terraform.

Resource names are sanitized inside the module before creating SageMaker resources. Branch or model versions such as `release-v1.0.0-24` are converted to SageMaker-safe names by replacing unsupported characters with hyphens and truncating long names with a stable hash suffix.

## Endpoint Storage Encryption

Set `encrypt_endpoint_storage = true` to pass `kms_key_arn` into the SageMaker endpoint configuration. Keep this enabled for standard endpoint instance families.

Some GPU instance families with NVMe instance storage, such as `g4dn` and `g5`, do not support endpoint configuration KMS keys. For those instance types, set `encrypt_endpoint_storage = false`; model artifacts and CloudWatch logs should still use KMS-backed storage through their own resources.

## ECR Image Access

When this module creates the SageMaker execution role, it grants the role scoped ECR pull permissions for the configured `model_image_uri` repository. This is required for AWS-managed framework images such as the Hugging Face inference containers.
