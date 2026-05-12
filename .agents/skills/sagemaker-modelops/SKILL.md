---
description: Use when improving the CPU RCF and Nginx BERT model workflows, creating Jenkins model stages, or integrating SageMaker artifacts with Terraform endpoints.
---

# SageMaker ModelOps Skill

## Goal
Make model delivery reproducible, testable, versioned, and deployable through Jenkins + Terraform.

## Use this skill when
- Working in `RCF_Model/`, `BERT_Model/`, or the target `models/` directory.
- Creating scripts for Jenkins model build stages.
- Packaging model artifacts for SageMaker endpoints.
- Adding model metadata, validation thresholds, or inference contract tests.
- Passing model artifact URIs into Terraform.

## Senior approach
Use this separation of responsibilities:

- Python/SageMaker scripts: generate data, train, evaluate, package, and upload artifacts.
- Jenkins: orchestrates model stages and quality gates.
- Terraform: deploys SageMaker model, endpoint config, endpoint, IAM, monitoring, and autoscaling.

Do not make Terraform run training jobs through `local-exec` except for a temporary demo spike.

## Artifact standard
Every approved model build must publish:

```text
s3://<artifact-bucket>/models/<model-name>/<git-sha-or-build-number>/model.tar.gz
s3://<artifact-bucket>/models/<model-name>/<git-sha-or-build-number>/metadata.json
s3://<artifact-bucket>/models/<model-name>/<git-sha-or-build-number>/evaluation.json
```

## Metadata schema
Create `metadata.json` with:

```json
{
  "project": "AIOps",
  "model_name": "cpu-rcf",
  "model_version": "<git-sha-or-build-number>",
  "git_commit": "<git-sha>",
  "jenkins_build_number": "<build-number>",
  "training_started_at": "<iso8601>",
  "training_completed_at": "<iso8601>",
  "training_data_version": "<version>",
  "container_image_uri": "<sagemaker-image-uri>",
  "artifact_s3_uri": "s3://.../model.tar.gz",
  "inference_contract": {
    "content_type": "text/csv or application/json",
    "response_shape": "documented response fields"
  },
  "thresholds": {
    "anomaly_score_threshold": 0.0
  },
  "metrics": {}
}
```

## CPU RCF requirements
For the CPU anomaly model:

- Input contract: CSV or the final format expected by the SageMaker endpoint.
- Training data must include realistic normal CPU usage and high-CPU anomalies.
- Validation must include:
  - normal CPU sample
  - sustained high CPU sample
  - empty/malformed input test
  - boundary values such as 0, 80, 85, 100
- Record the chosen anomaly threshold.
- Document whether the model detects only high CPU spikes or broader abnormal CPU patterns.

## Nginx BERT/log model requirements
For the log anomaly model:

- Input contract: JSON payload accepted by the endpoint.
- Training data must include:
  - normal Nginx access logs
  - 4xx hard negatives if they should not always be anomalies
  - 5xx errors
  - timeout/connection/refused/upstream failures
  - malformed lines
  - repeated patterns/context windows
- Validation must report precision, recall, F1, threshold, and confusion matrix where possible.
- Include representative test payloads for Lambda integration.

## Inference contract test
Before publishing a model artifact, run a local or endpoint-level test that confirms:

- Content type is correct.
- Payload shape matches Lambda code.
- Response contains required score/classification fields.
- Error responses are handled predictably.

## Terraform handoff
After successful validation, Jenkins should export or write a Terraform variable file containing:

```hcl
model_version              = "<build-number-or-git-sha>"
cpu_model_artifact_s3_uri  = "s3://.../cpu-rcf/.../model.tar.gz"
log_model_artifact_s3_uri  = "s3://.../nginx-bert/.../model.tar.gz"
cpu_model_image_uri        = "<image-uri>"
log_model_image_uri        = "<image-uri>"
```

## Acceptance criteria
A model workflow is complete when:

- Artifact is immutable and traceable to a Git commit and Jenkins build.
- Evaluation metrics are archived.
- Inference contract tests pass.
- Terraform can deploy/update the endpoint using only the published artifact URI and image URI.
- Rollback can be performed by redeploying a previous artifact version.
