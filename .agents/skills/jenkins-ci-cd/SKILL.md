---
description: Use when creating or modifying Jenkins CI/CD for the Terraform and AWS AIOps platform, including model training, Lambda packaging, Terraform plan/apply, and smoke testing.
---

# Jenkins CI/CD Skill

## Goal
Create a senior-level Jenkins pipeline that turns the AIOps repo into a repeatable delivery system.

## Use this skill when
- Writing or updating `Jenkinsfile`.
- Designing branch-to-environment promotion.
- Adding quality gates, security gates, or smoke tests.
- Packaging Lambda artifacts.
- Running model training/validation before Terraform deployment.
- Configuring Jenkins credentials and AWS role assumption.

## Pipeline principles
- Jenkins orchestrates delivery; Terraform owns infrastructure resources.
- Do not train models inside Terraform.
- Do not store secrets in the repo or Jenkinsfile.
- Use Jenkins credentials binding for AWS role ARN, Jira test credentials, notification webhooks, and artifact bucket names.
- Use a saved Terraform plan for apply.
- Require manual approval for stage/prod.
- Archive artifacts and logs for auditability.

## Branch/environment mapping
Recommended mapping:

| Branch | Environment | Apply behavior |
|---|---|---|
| feature/* | dev plan only | no automatic apply |
| develop | dev | automatic apply after checks |
| release/* | stage | approval required |
| main | prod | approval required |

## Required Jenkins credentials
Define these in Jenkins, not in source code:

- `aws-deploy-role-arn-dev`
- `aws-deploy-role-arn-stage`
- `aws-deploy-role-arn-prod`
- `terraform-state-bucket`
- `model-artifact-bucket`
- `lambda-artifact-bucket`
- `jira-test-secret-arn` or environment-specific secret ARN
- `slack-webhook` or email notification config

## Required stages
Implement these stages in order:

1. `Checkout`
2. `Resolve Environment`
   - Determine target environment from branch or parameter.
   - Fail if branch is not allowed to deploy target environment.
3. `Tooling Preflight`
   - Print versions for Python, Terraform, AWS CLI, Java, jq, zip, tflint, checkov/tfsec.
4. `Python Install`
   - Create virtualenv.
   - Install Lambda and model requirements.
5. `Python Quality`
   - Run formatting checks if configured.
   - Run linting.
   - Run unit tests.
6. `Model Build`
   - Train/generate CPU anomaly model artifact.
   - Train/generate log anomaly model artifact.
   - Save metrics and thresholds.
7. `Model Validation`
   - Run inference contract tests.
   - Fail if metrics are below agreed threshold.
8. `Publish Model Artifacts`
   - Upload model artifacts and metadata to immutable S3 prefixes.
9. `Package Lambda`
   - Build deterministic Lambda zip.
   - Compute hash.
   - Upload artifact to S3.
10. `Terraform Init`
11. `Terraform Quality`
12. `Terraform Plan`
    - Save plan to file.
    - Archive human-readable output.
13. `Approval`
    - Required for stage/prod.
14. `Terraform Apply`
    - Apply saved plan file only.
15. `Smoke Tests`
16. `Notify`

## Jenkinsfile skeleton
Use this as the baseline and adapt names to the final repo layout:

```groovy
pipeline {
  agent any

  options {
    timestamps()
    ansiColor('xterm')
    buildDiscarder(logRotator(numToKeepStr: '30'))
    disableConcurrentBuilds()
  }

  parameters {
    choice(name: 'TARGET_ENV', choices: ['auto', 'dev', 'stage', 'prod'], description: 'Deployment environment')
    booleanParam(name: 'APPLY', defaultValue: false, description: 'Apply Terraform plan')
    booleanParam(name: 'TRAIN_MODELS', defaultValue: true, description: 'Train and publish model artifacts')
  }

  environment {
    AWS_REGION = 'eu-west-1'
    TF_IN_AUTOMATION = 'true'
    PYTHONUNBUFFERED = '1'
  }

  stages {
    stage('Checkout') {
      steps { checkout scm }
    }

    stage('Resolve Environment') {
      steps {
        sh 'scripts/ci/resolve_environment.sh'
      }
    }

    stage('Tooling Preflight') {
      steps {
        sh '''
          python3 --version
          terraform version
          aws --version
          jq --version
        '''
      }
    }

    stage('Python Quality') {
      steps {
        sh '''
          python3 -m venv .venv
          . .venv/bin/activate
          pip install -U pip
          pip install -r lambda/requirements.txt
          pip install -r models/requirements-dev.txt || true
          pytest lambda/tests models/tests --junitxml=reports/pytest.xml
        '''
      }
      post { always { junit 'reports/pytest.xml' } }
    }

    stage('Model Build and Validation') {
      when { expression { return params.TRAIN_MODELS } }
      steps {
        sh '''
          . .venv/bin/activate
          scripts/train_cpu_model.sh
          scripts/train_log_model.sh
          scripts/upload_model_artifacts.sh
        '''
      }
    }

    stage('Package Lambda') {
      steps {
        sh 'scripts/package_lambda.sh'
        archiveArtifacts artifacts: 'dist/*.zip,dist/*.sha256', fingerprint: true
      }
    }

    stage('Terraform Init and Quality') {
      steps {
        dir('infra/envs/${TARGET_ENV_RESOLVED}') {
          sh '''
            terraform fmt -check -recursive ../..
            terraform init -input=false
            terraform validate
            tflint --init || true
            tflint || true
            checkov -d ../.. || true
          '''
        }
      }
    }

    stage('Terraform Plan') {
      steps {
        dir('infra/envs/${TARGET_ENV_RESOLVED}') {
          sh '''
            terraform plan -input=false -out=tfplan \
              -var="model_version=${BUILD_NUMBER}" \
              -var-file="terraform.tfvars"
            terraform show -no-color tfplan > tfplan.txt
          '''
          archiveArtifacts artifacts: 'infra/envs/${TARGET_ENV_RESOLVED}/tfplan.txt', fingerprint: true
        }
      }
    }

    stage('Approval') {
      when { expression { return params.APPLY && env.TARGET_ENV_RESOLVED != 'dev' } }
      steps {
        input message: "Apply Terraform to ${env.TARGET_ENV_RESOLVED}?", ok: 'Apply'
      }
    }

    stage('Terraform Apply') {
      when { expression { return params.APPLY } }
      steps {
        dir('infra/envs/${TARGET_ENV_RESOLVED}') {
          sh 'terraform apply -input=false tfplan'
        }
      }
    }

    stage('Smoke Tests') {
      when { expression { return params.APPLY } }
      steps {
        sh 'scripts/smoke_test.sh ${TARGET_ENV_RESOLVED}'
      }
    }
  }

  post {
    always {
      archiveArtifacts artifacts: 'reports/**/*,dist/**/*', allowEmptyArchive: true
    }
    failure {
      echo 'Pipeline failed. Review logs, archived plan, and test reports.'
    }
  }
}
```

## Smoke test checklist
The smoke test script should verify:

- Terraform outputs are readable.
- Monitored EC2 instance exists with `AnomalyMonitoring=enabled`.
- CloudWatch has recent CPU datapoints.
- Nginx log group has recent streams.
- SageMaker CPU endpoint returns a valid anomaly response for sample CSV.
- SageMaker log endpoint returns a valid anomaly response for sample JSON.
- Lambda test invocation succeeds.
- DynamoDB table accepts a test anomaly item or Lambda writes one in test mode.
- SQS queue and DLQ exist.
- SNS topic exists.
- EventBridge bus/rule exists.

## Anti-patterns to avoid
- Applying Terraform without saving and reviewing a plan.
- Passing AWS static keys in the Jenkinsfile.
- Training model artifacts with non-reproducible names.
- Using `latest` Docker image tags for production.
- Ignoring failing tests to force deployment.
- Allowing prod applies from non-main branches.
