# Scripts

CI and ModelOps scripts.

Model workflow:

- `train_cpu_model.sh` runs the legacy CPU RCF creation/training flow.
- `train_log_model.sh` runs the legacy Nginx BERT dataset/tuning flow.
- `package_model_artifacts.sh` creates `metadata.json`, `evaluation.json`, and handoff files.
- `upload_model_artifacts.sh` publishes immutable artifacts to S3.
- `write_model_tfvars.sh` writes Terraform model artifact variables.
- `package_lambda.sh` creates the deterministic Lambda zip and hashes.
- `smoke_test.sh` validates applied AWS resources, dashboards, alarms, and optional synthetic anomalies from Terraform outputs.
- `cleanup_ephemeral.sh` removes transient local build and plan artifacts.

These scripts are intended for Jenkins. Terraform must not train models.
