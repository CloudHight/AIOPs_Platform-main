# iam

Reserved module for future extraction of shared IAM roles and policies.

Current deployable IAM resources live close to the resources that use them:

- EC2 workload role in `ec2-workload`
- Lambda execution role in `lambda-function`
- SageMaker execution role in `sagemaker-endpoint`

Keeping IAM local to each module makes the current demo easier to review. Extract shared IAM here only when multiple modules need the same policy contract.
