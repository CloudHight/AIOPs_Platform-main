# ModelOps

ModelOps turns legacy CPU and log model workflows into deployable, versioned SageMaker artifacts.

## Principles

- Jenkins trains, validates, packages, and uploads model artifacts.
- Terraform never trains models.
- Terraform consumes approved immutable S3 URIs and image URIs.
- Every model artifact should have metadata, evaluation metrics, threshold, container image URI, git commit, and Jenkins build number.

## Source Workflows

CPU RCF model:

```text
RCF_Model/
```

Nginx/log BERT model:

```text
BERT_Model/
```

Wrapper scripts live in `scripts/`.

## Jenkins Flow

```bash
export MODEL_VERSION="${BUILD_NUMBER}"
export MODEL_ARTIFACT_BUCKET="<artifact-bucket>"
export CPU_MODEL_IMAGE_URI="<sagemaker-cpu-image-uri>"
export LOG_MODEL_IMAGE_URI="<sagemaker-log-image-uri>"

scripts/train_cpu_model.sh
scripts/train_log_model.sh
scripts/package_model_artifacts.sh
scripts/upload_model_artifacts.sh
scripts/write_model_tfvars.sh infra/envs/dev/model-artifacts.auto.tfvars.json
```

In Jenkins, set both parameters for endpoint deployment:

```text
TRAIN_MODELS=true
DEPLOY_SAGEMAKER_ENDPOINTS=true
```

`TRAIN_MODELS` creates the approved artifact handoff. `DEPLOY_SAGEMAKER_ENDPOINTS` tells Terraform to create or update the SageMaker endpoint resources from that handoff.

To deploy a previously approved version without retraining:

```text
TRAIN_MODELS=false
DEPLOY_SAGEMAKER_ENDPOINTS=true
USE_EXISTING_MODEL_ARTIFACTS=true
APPROVED_MODEL_VERSION=release-v1.0.0-26
```

In that mode Jenkins runs `scripts/write_existing_model_tfvars.sh`, verifies these objects exist for both models, and then writes `infra/envs/<env>/model-artifacts.auto.tfvars.json`:

```text
models/<model-name>/<model-version>/model.tar.gz
models/<model-name>/<model-version>/metadata.json
models/<model-name>/<model-version>/evaluation.json
```

## Jenkins Readiness Note

The RCF and BERT launchers now support Jenkins-driven training through the `SAGEMAKER_EXECUTION_ROLE_ARN` environment variable. Store that role ARN in the Jenkins `sagemaker-execution-role-arn` secret text credential.

Model launchers should continue to accept explicit runtime inputs rather than Notebook/Studio role discovery:

```text
SAGEMAKER_EXECUTION_ROLE_ARN
--bucket
--output-prefix
--region
--wait
```

The Jenkins deploy/training role must be allowed to pass the SageMaker execution role with `iam:PassRole`.

## Artifact Layout

Published artifacts:

```text
s3://<bucket>/models/cpu-rcf/<model-version>/model.tar.gz
s3://<bucket>/models/cpu-rcf/<model-version>/metadata.json
s3://<bucket>/models/cpu-rcf/<model-version>/evaluation.json
s3://<bucket>/models/nginx-bert/<model-version>/model.tar.gz
s3://<bucket>/models/nginx-bert/<model-version>/metadata.json
s3://<bucket>/models/nginx-bert/<model-version>/evaluation.json
```

Local handoff files:

```text
dist/modelops/cpu-rcf/metadata.json
dist/modelops/cpu-rcf/evaluation.json
dist/modelops/cpu-rcf/handoff.json
dist/modelops/nginx-bert/metadata.json
dist/modelops/nginx-bert/evaluation.json
dist/modelops/nginx-bert/handoff.json
dist/modelops/model-artifacts.auto.tfvars.json
```

## Terraform Handoff

The generated tfvars file contains:

```json
{
  "model_version": "123",
  "cpu_model_artifact_s3_uri": "s3://bucket/models/cpu-rcf/123/model.tar.gz",
  "log_model_artifact_s3_uri": "s3://bucket/models/nginx-bert/123/model.tar.gz",
  "cpu_model_image_uri": "123456789012.dkr.ecr.us-east-1.amazonaws.com/cpu-inference:sha",
  "log_model_image_uri": "123456789012.dkr.ecr.us-east-1.amazonaws.com/log-inference:sha"
}
```

Terraform deploys endpoints through `infra/modules/sagemaker-endpoint`.

The endpoint switch is stored separately in `infra/envs/<env>/jenkins.auto.tfvars.json`:

```json
{
  "enable_sagemaker_endpoints": true
}
```

## Validation Expectations

Before upload:

- training job succeeded
- evaluation metrics meet threshold
- inference payload contract is unchanged or Lambda was updated
- model artifact URI is immutable
- metadata includes git commit and Jenkins build number

Smoke tests invoke deployed endpoints with sample payloads after apply.

## Rollback

Model rollback is a Terraform input rollback:

1. Pick the previous artifact version from S3 metadata.
2. Set `cpu_model_artifact_s3_uri` or `log_model_artifact_s3_uri` to the previous URI.
3. Run Jenkins plan/apply.
4. Smoke-test endpoint responses.

Do not overwrite existing S3 model prefixes. Publish a new version for every build.
