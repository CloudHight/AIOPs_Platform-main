# Environments

Environment root modules:

- `dev`: development/demo deployment.
- `stage`: release validation deployment.
- `prod`: production deployment.

Each root composes the EC2 workload, optional SageMaker endpoints, and optional AIOps control plane. Jenkins selects the root from branch mapping and applies only saved Terraform plans.
