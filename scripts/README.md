# Scripts

CI and ModelOps scripts.

Model workflow:

- `train_cpu_model.sh` runs the legacy CPU RCF creation/training flow.
- `train_log_model.sh` runs the legacy Nginx BERT dataset/tuning flow.
- `package_model_artifacts.sh` creates `metadata.json`, `evaluation.json`, and handoff files.
- `upload_model_artifacts.sh` publishes immutable artifacts to S3.
- `write_model_tfvars.sh` writes Terraform model artifact variables.
- `write_existing_model_tfvars.sh` verifies a previously approved model version in S3 and writes Terraform model artifact variables without retraining.
- `package_lambda.sh` creates the deterministic Lambda zip and hashes.
- `smoke_test.sh` validates applied AWS resources, dashboards, alarms, and optional synthetic anomalies from Terraform outputs.
- `validate_terraform_backend.sh` verifies the S3/DynamoDB remote-state backend before `terraform init`.
- `validate_runtime_kms_state.sh` verifies existing runtime SSM SecureString parameters can still be decrypted before Terraform refresh/plan.
- `recover_kms_key.sh` cancels deletion and restores `alias/aiops-<env>` when the old KMS key is still the correct environment key.
- `repair_ssm_runtime_parameters.sh` deletes only known broken runtime SSM parameters after explicit confirmation so Terraform can recreate them.
- `cleanup_ephemeral.sh` removes transient local build and plan artifacts.

These scripts are intended for Jenkins. Terraform must not train models.

Runtime SSM/KMS repair:

```bash
# Recover the old key if it is still the intended environment key.
scripts/recover_kms_key.sh arn:aws:kms:us-east-1:123456789012:key/example stage

# Or delete only broken runtime parameters when the old key is obsolete.
scripts/repair_ssm_runtime_parameters.sh stage --confirm-delete-broken
```
