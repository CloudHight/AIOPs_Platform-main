# Models

ModelOps integration for the AIOps platform.

This directory is the active source for model training, validation, packaging inputs, and SageMaker inference helper code.

The model source code lives in:

- `cpu-rcf/`
- `nginx-bert/`

Jenkins should use the wrapper scripts in `../scripts/`:

1. `train_cpu_model.sh`
2. `train_log_model.sh`
3. `package_model_artifacts.sh`
4. `upload_model_artifacts.sh`
5. `write_model_tfvars.sh`

Terraform consumes only approved artifact URIs and image URIs through `infra/modules/sagemaker-endpoint`.

## Migration History

The CPU workflow was migrated from `RCF_Model/` into `cpu-rcf/`. The Nginx/log workflow was migrated from `BERT_Model/` into `nginx-bert/`. Those legacy paths are not used by Jenkins or Terraform.

## Artifact Layout

Published artifacts follow:

```text
s3://<artifact-bucket>/models/<model-name>/<model-version>/model.tar.gz
s3://<artifact-bucket>/models/<model-name>/<model-version>/metadata.json
s3://<artifact-bucket>/models/<model-name>/<model-version>/evaluation.json
```

## Terraform Handoff

The upload flow writes:

```text
dist/modelops/model-artifacts.auto.tfvars.json
```

with values such as:

- `model_version`
- `cpu_model_artifact_s3_uri`
- `log_model_artifact_s3_uri`
- `cpu_model_image_uri`
- `log_model_image_uri`
