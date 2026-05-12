def resolveTargetEnvironment() {
  if (params.TARGET_ENV != 'auto') {
    return params.TARGET_ENV
  }

  if (env.BRANCH_NAME == 'main') {
    return 'prod'
  }
  if (env.BRANCH_NAME == 'develop') {
    return 'dev'
  }
  if (env.BRANCH_NAME?.startsWith('release/')) {
    return 'stage'
  }
  return 'dev'
}

def assertBranchPolicy(String targetEnv) {
  if (targetEnv == 'prod' && env.BRANCH_NAME != 'main') {
    error("prod deployment is only allowed from main; current branch is ${env.BRANCH_NAME}")
  }
  if (targetEnv == 'stage' && !(env.BRANCH_NAME == 'main' || env.BRANCH_NAME?.startsWith('release/'))) {
    error("stage deployment is only allowed from release/* or main; current branch is ${env.BRANCH_NAME}")
  }
}

pipeline {
  agent any

  options {
    timestamps()
    ansiColor('xterm')
    buildDiscarder(logRotator(numToKeepStr: '30', artifactNumToKeepStr: '30'))
    disableConcurrentBuilds()
    skipDefaultCheckout(true)
  }

  parameters {
    choice(name: 'TARGET_ENV', choices: ['auto', 'dev', 'stage', 'prod'], description: 'Deployment environment. auto maps branch to environment.')
    booleanParam(name: 'APPLY', defaultValue: false, description: 'Apply the saved Terraform plan.')
    booleanParam(name: 'TRAIN_MODELS', defaultValue: true, description: 'Train, package, and publish model artifacts.')
    booleanParam(name: 'RUN_SMOKE_TESTS', defaultValue: true, description: 'Run smoke tests after apply.')
  }

  environment {
    AWS_REGION = 'us-east-1'
    TF_IN_AUTOMATION = 'true'
    PYTHONUNBUFFERED = '1'
    AIOPS_PYTHON = 'python3.12'
    PIP_DISABLE_PIP_VERSION_CHECK = '1'
    DIST_DIR = 'dist'
    REPORTS_DIR = 'reports'
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
      }
    }

    stage('Resolve Environment') {
      steps {
        script {
          env.TARGET_ENV_RESOLVED = resolveTargetEnvironment()
          assertBranchPolicy(env.TARGET_ENV_RESOLVED)
          env.TF_ROOT = "infra/envs/${env.TARGET_ENV_RESOLVED}"
          env.MODEL_VERSION = "${env.BRANCH_NAME ?: 'local'}-${env.BUILD_NUMBER}".replaceAll('[^A-Za-z0-9_.-]', '-')
          env.AWS_DEPLOY_ROLE_CREDENTIAL_ID = "aws-deploy-role-arn-${env.TARGET_ENV_RESOLVED}"
        }
        sh '''
          set -eu
          test -d "${TF_ROOT}"
          mkdir -p "${DIST_DIR}" "${REPORTS_DIR}"
          printf 'Target environment: %s\n' "${TARGET_ENV_RESOLVED}"
          printf 'Terraform root: %s\n' "${TF_ROOT}"
          printf 'Model version: %s\n' "${MODEL_VERSION}"
        '''
      }
    }

    stage('Tooling Preflight') {
      steps {
        sh '''
          set -eu
          command -v "${AIOPS_PYTHON}"
          "${AIOPS_PYTHON}" --version
          terraform version
          aws --version
          java -version
          jq --version
          zip -v | head -n 2
          tflint --version
          git --version
        '''
      }
    }

    stage('Secret Scan') {
      steps {
        sh '''
          set -eu
          scripts/secret_scan.sh
        '''
      }
      post {
        always {
          archiveArtifacts allowEmptyArchive: true, artifacts: 'reports/gitleaks.json,reports/secret-scan.txt'
        }
      }
    }

    stage('Python Install') {
      steps {
        sh '''
          set -eu
          rm -rf .venv .iac-venv
          "${AIOPS_PYTHON}" -m venv .venv
          . .venv/bin/activate
          python - <<'PY'
import sys
if sys.version_info < (3, 12):
    raise SystemExit(f"Python 3.12+ is required for audited dependency resolution; got {sys.version}")
PY
          python -m pip install --upgrade pip
          if [ -s lambda/requirements.txt ]; then
            pip install -r lambda/requirements.txt
          fi
          if [ -s models/requirements-dev.txt ]; then
            pip install -r models/requirements-dev.txt
          else
            pip install -r models/requirements.txt
            pip install pytest ruff mypy pip-audit bandit
          fi
          "${AIOPS_PYTHON}" -m venv .iac-venv
          . .iac-venv/bin/activate
          python -m pip install --upgrade pip
          pip install checkov
        '''
      }
    }

    stage('Python Quality') {
      steps {
        sh '''
          set -eu
          . .venv/bin/activate
          python -m compileall -q lambda/src scripts
          ruff check lambda/src scripts
          mypy --config-file lambda/pyproject.toml lambda/src
          bandit -q -r lambda/src -f json -o reports/bandit.json
          pip-audit --cache-dir reports/.pip-audit-cache -r lambda/requirements.txt -r models/requirements.txt -f json -o reports/pip-audit.json
          TEST_PATHS=""
          for path in lambda/tests models/tests; do
            if [ -d "${path}" ]; then
              TEST_PATHS="${TEST_PATHS} ${path}"
            fi
          done
          if [ -n "${TEST_PATHS}" ]; then
            pytest ${TEST_PATHS} --junitxml=reports/pytest.xml
          else
            echo "No test directories found; failing because senior delivery requires tests." >&2
            exit 1
          fi
        '''
      }
      post {
        always {
          junit allowEmptyResults: true, testResults: 'reports/pytest.xml'
          archiveArtifacts allowEmptyArchive: true, artifacts: 'reports/bandit.json,reports/pip-audit.json'
        }
      }
    }

    stage('Model Build and Validation') {
      when {
        expression { return params.TRAIN_MODELS }
      }
      steps {
        withCredentials([
          string(credentialsId: 'model-artifact-bucket', variable: 'MODEL_ARTIFACT_BUCKET'),
          string(credentialsId: 'sagemaker-execution-role-arn', variable: 'SAGEMAKER_EXECUTION_ROLE_ARN'),
          string(credentialsId: 'cpu-model-image-uri', variable: 'CPU_MODEL_IMAGE_URI'),
          string(credentialsId: 'log-model-image-uri', variable: 'LOG_MODEL_IMAGE_URI'),
          string(credentialsId: "${env.AWS_DEPLOY_ROLE_CREDENTIAL_ID}", variable: 'AWS_DEPLOY_ROLE_ARN')
        ]) {
          sh '''
            set -eu
            set +x
            CREDS="$(aws sts assume-role --role-arn "${AWS_DEPLOY_ROLE_ARN}" --role-session-name "jenkins-aiops-models-${BUILD_NUMBER}")"
            export AWS_ACCESS_KEY_ID="$(printf '%s' "${CREDS}" | jq -r '.Credentials.AccessKeyId')"
            export AWS_SECRET_ACCESS_KEY="$(printf '%s' "${CREDS}" | jq -r '.Credentials.SecretAccessKey')"
            export AWS_SESSION_TOKEN="$(printf '%s' "${CREDS}" | jq -r '.Credentials.SessionToken')"
            export AWS_DEFAULT_REGION="${AWS_REGION}"
            export MODEL_VERSION="${MODEL_VERSION}"
            export CPU_MODEL_IMAGE_URI
            export LOG_MODEL_IMAGE_URI
            export LOG_TRAIN_WAIT=true
            if [ -z "${SAGEMAKER_EXECUTION_ROLE_ARN:-}" ]; then
              echo "SAGEMAKER_EXECUTION_ROLE_ARN is required when TRAIN_MODELS=true."
              exit 1
            fi
            export SAGEMAKER_EXECUTION_ROLE_ARN

            . .venv/bin/activate
            scripts/train_cpu_model.sh
            scripts/train_log_model.sh
            scripts/package_model_artifacts.sh
            scripts/validate_model_handoff.sh
            scripts/upload_model_artifacts.sh
            scripts/write_model_tfvars.sh "${TF_ROOT}/model-artifacts.auto.tfvars.json"
          '''
        }
      }
      post {
        always {
          archiveArtifacts allowEmptyArchive: true, artifacts: 'dist/modelops/**/*'
        }
      }
    }

    stage('Package Lambda') {
      steps {
        withCredentials([
          string(credentialsId: 'lambda-artifact-bucket', variable: 'LAMBDA_ARTIFACT_BUCKET'),
          string(credentialsId: "${env.AWS_DEPLOY_ROLE_CREDENTIAL_ID}", variable: 'AWS_DEPLOY_ROLE_ARN')
        ]) {
          sh '''
            set -eu
            set +x
            CREDS="$(aws sts assume-role --role-arn "${AWS_DEPLOY_ROLE_ARN}" --role-session-name "jenkins-aiops-lambda-${BUILD_NUMBER}")"
            export AWS_ACCESS_KEY_ID="$(printf '%s' "${CREDS}" | jq -r '.Credentials.AccessKeyId')"
            export AWS_SECRET_ACCESS_KEY="$(printf '%s' "${CREDS}" | jq -r '.Credentials.SecretAccessKey')"
            export AWS_SESSION_TOKEN="$(printf '%s' "${CREDS}" | jq -r '.Credentials.SessionToken')"
            export AWS_DEFAULT_REGION="${AWS_REGION}"

            scripts/package_lambda.sh
            aws s3 cp "dist/lambda/aiops-lambda.zip" "s3://${LAMBDA_ARTIFACT_BUCKET}/lambda/${TARGET_ENV_RESOLVED}/${BUILD_NUMBER}/aiops-lambda.zip"
            jq -n \
              --arg bucket "${LAMBDA_ARTIFACT_BUCKET}" \
              --arg key "lambda/${TARGET_ENV_RESOLVED}/${BUILD_NUMBER}/aiops-lambda.zip" \
              --arg hash "$(cat dist/lambda/aiops-lambda.zip.base64sha256)" \
              '{
                lambda_artifact_bucket: $bucket,
                lambda_artifact_key: $key,
                lambda_source_code_hash: $hash,
                enable_aiops_control_plane: true
              }' > "${TF_ROOT}/jenkins.auto.tfvars.json"
          '''
        }
      }
      post {
        always {
          archiveArtifacts allowEmptyArchive: true, fingerprint: true, artifacts: 'dist/lambda/**/*'
        }
      }
    }

    stage('Terraform Init') {
      steps {
        withCredentials([string(credentialsId: "${env.AWS_DEPLOY_ROLE_CREDENTIAL_ID}", variable: 'AWS_DEPLOY_ROLE_ARN')]) {
          dir("${env.TF_ROOT}") {
            sh '''
              set -eu
              set +x
              CREDS="$(aws sts assume-role --role-arn "${AWS_DEPLOY_ROLE_ARN}" --role-session-name "jenkins-aiops-tf-init-${BUILD_NUMBER}")"
              export AWS_ACCESS_KEY_ID="$(printf '%s' "${CREDS}" | jq -r '.Credentials.AccessKeyId')"
              export AWS_SECRET_ACCESS_KEY="$(printf '%s' "${CREDS}" | jq -r '.Credentials.SecretAccessKey')"
              export AWS_SESSION_TOKEN="$(printf '%s' "${CREDS}" | jq -r '.Credentials.SessionToken')"
              export AWS_DEFAULT_REGION="${AWS_REGION}"
              terraform init -input=false
            '''
          }
        }
      }
    }

    stage('Terraform Quality') {
      steps {
        dir("${env.TF_ROOT}") {
          sh '''
            set -eu
            terraform fmt -check -recursive ../..
            terraform validate
            tflint --init
            tflint --recursive
            ../../../.iac-venv/bin/checkov -d ../.. -o cli -o json --output-file-path ../../../reports/checkov
          '''
        }
      }
      post {
        always {
          archiveArtifacts allowEmptyArchive: true, artifacts: 'reports/checkov*'
        }
      }
    }

    stage('Terraform Plan') {
      steps {
        withCredentials([string(credentialsId: "${env.AWS_DEPLOY_ROLE_CREDENTIAL_ID}", variable: 'AWS_DEPLOY_ROLE_ARN')]) {
          dir("${env.TF_ROOT}") {
            sh '''
              set -eu
              set +x
              CREDS="$(aws sts assume-role --role-arn "${AWS_DEPLOY_ROLE_ARN}" --role-session-name "jenkins-aiops-tf-plan-${BUILD_NUMBER}")"
              export AWS_ACCESS_KEY_ID="$(printf '%s' "${CREDS}" | jq -r '.Credentials.AccessKeyId')"
              export AWS_SECRET_ACCESS_KEY="$(printf '%s' "${CREDS}" | jq -r '.Credentials.SecretAccessKey')"
              export AWS_SESSION_TOKEN="$(printf '%s' "${CREDS}" | jq -r '.Credentials.SessionToken')"
              export AWS_DEFAULT_REGION="${AWS_REGION}"
              terraform plan -input=false -out=tfplan -var-file=jenkins.auto.tfvars.json
              terraform show -no-color tfplan > tfplan.txt
            '''
          }
        }
      }
      post {
        always {
          archiveArtifacts allowEmptyArchive: false, fingerprint: true, artifacts: 'infra/envs/*/tfplan.txt'
        }
      }
    }

    stage('Approval') {
      when {
        expression { return params.APPLY && env.TARGET_ENV_RESOLVED in ['stage', 'prod'] }
      }
      steps {
        input message: "Apply saved Terraform plan to ${env.TARGET_ENV_RESOLVED}?", ok: 'Apply'
      }
    }

    stage('Terraform Apply') {
      when {
        expression { return params.APPLY }
      }
      steps {
        withCredentials([string(credentialsId: "${env.AWS_DEPLOY_ROLE_CREDENTIAL_ID}", variable: 'AWS_DEPLOY_ROLE_ARN')]) {
          dir("${env.TF_ROOT}") {
            sh '''
              set -eu
              set +x
              CREDS="$(aws sts assume-role --role-arn "${AWS_DEPLOY_ROLE_ARN}" --role-session-name "jenkins-aiops-tf-apply-${BUILD_NUMBER}")"
              export AWS_ACCESS_KEY_ID="$(printf '%s' "${CREDS}" | jq -r '.Credentials.AccessKeyId')"
              export AWS_SECRET_ACCESS_KEY="$(printf '%s' "${CREDS}" | jq -r '.Credentials.SecretAccessKey')"
              export AWS_SESSION_TOKEN="$(printf '%s' "${CREDS}" | jq -r '.Credentials.SessionToken')"
              export AWS_DEFAULT_REGION="${AWS_REGION}"
              terraform apply -input=false tfplan
            '''
          }
        }
      }
    }

    stage('Smoke Tests') {
      when {
        expression { return params.APPLY && params.RUN_SMOKE_TESTS }
      }
      steps {
        withCredentials([string(credentialsId: "${env.AWS_DEPLOY_ROLE_CREDENTIAL_ID}", variable: 'AWS_DEPLOY_ROLE_ARN')]) {
          sh '''
            set -eu
            set +x
            CREDS="$(aws sts assume-role --role-arn "${AWS_DEPLOY_ROLE_ARN}" --role-session-name "jenkins-aiops-smoke-${BUILD_NUMBER}")"
            export AWS_ACCESS_KEY_ID="$(printf '%s' "${CREDS}" | jq -r '.Credentials.AccessKeyId')"
            export AWS_SECRET_ACCESS_KEY="$(printf '%s' "${CREDS}" | jq -r '.Credentials.SecretAccessKey')"
            export AWS_SESSION_TOKEN="$(printf '%s' "${CREDS}" | jq -r '.Credentials.SessionToken')"
            export AWS_DEFAULT_REGION="${AWS_REGION}"
            scripts/smoke_test.sh "${TARGET_ENV_RESOLVED}"
          '''
        }
      }
    }
  }

  post {
    always {
      archiveArtifacts allowEmptyArchive: true, fingerprint: true, artifacts: 'dist/**/*,reports/**/*,infra/envs/*/tfplan.txt'
      sh 'scripts/cleanup_ephemeral.sh || true'
    }
    failure {
      echo 'Pipeline failed. Review Jenkins logs, archived quality reports, and the Terraform plan output.'
    }
  }
}
