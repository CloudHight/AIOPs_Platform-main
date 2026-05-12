# Terraform Modules

Reusable Terraform modules for the AIOps platform:

- `aiops-control-plane`
- `cloudwatch-observability`
- `dynamodb`
- `ec2-workload`
- `eventbridge`
- `jenkins-controller`
- `lambda-function`
- `sagemaker-endpoint`
- `secrets-manager`
- `sns`
- `sqs`
- `ssm-parameters`

The `jenkins-controller` module bootstraps the Jenkins EC2 controller used to run the repository Jenkinsfile. The `iam` and `networking` modules are reserved for future extraction as the platform moves from a compact demo VPC/workload shape to a fuller multi-network deployment.
