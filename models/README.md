# Models

ModelOps integration for the AIOps platform.

The legacy training code remains in:

- `../RCF_Model/`
- `../BERT_Model/`

Jenkins should use the wrapper scripts in `../scripts/`:

1. `train_cpu_model.sh`
2. `train_log_model.sh`
3. `package_model_artifacts.sh`
4. `upload_model_artifacts.sh`
5. `write_model_tfvars.sh`

Terraform consumes only approved artifact URIs and image URIs through `infra/modules/sagemaker-endpoint`.

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
