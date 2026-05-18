def normalizeBranchName(String branchName) {
  if (!branchName) {
    return ''
  }

  return branchName.replaceFirst('^refs/heads/', '')
    .replaceFirst('^refs/remotes/origin/', '')
    .replaceFirst('^remotes/origin/', '')
    .replaceFirst('^origin/', '')
    .replaceFirst('\\^0$', '')
}

def resolveTargetEnvironment(String sourceBranch) {
  if (params.TARGET_ENV != 'auto') {
    return params.TARGET_ENV
  }

  if (sourceBranch == 'main') {
    return 'prod'
  }
  if (sourceBranch == 'develop') {
    return 'dev'
  }
  if (sourceBranch?.startsWith('release/')) {
    return 'stage'
  }
  return 'dev'
}

def assertBranchPolicy(String targetEnv, String sourceBranch) {
  if (targetEnv == 'prod' && sourceBranch != 'main') {
    error("prod deployment is only allowed from main; resolved source branch is ${sourceBranch ?: 'unknown'}")
  }
  if (targetEnv == 'stage' && !(sourceBranch == 'main' || sourceBranch?.startsWith('release/'))) {
    error("stage deployment is only allowed from release/* or main; resolved source branch is ${sourceBranch ?: 'unknown'}")
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
    booleanParam(name: 'DESTROY', defaultValue: false, description: 'Destroy the selected Terraform environment.')
    string(name: 'DESTROY_CONFIRM', defaultValue: '', description: 'Type destroy-<env> to confirm destroy.')
    booleanParam(name: 'TRAIN_MODELS', defaultValue: true, description: 'Train, package, and publish model artifacts.')
    booleanParam(name: 'DEPLOY_SAGEMAKER_ENDPOINTS', defaultValue: true, description: 'Deploy SageMaker endpoints from the model artifact handoff. Disable only when using existing endpoint names.')
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
        sh '''
          set -eu
          scripts/cleanup_ephemeral.sh
        '''
      }
    }

    stage('Resolve Environment') {
      steps {
        script {
          String sourceBranch = normalizeBranchName(env.BRANCH_NAME ?: env.GIT_BRANCH ?: '')
          if (!sourceBranch) {
            sourceBranch = normalizeBranchName(sh(
              returnStdout: true,
              script: '''
                set +e
                branch="$(git branch --show-current 2>/dev/null)"
                if [ -z "${branch}" ]; then
                  branch="$(git name-rev --name-only HEAD 2>/dev/null)"
                fi
                printf '%s' "${branch}"
              '''
            ).trim())
          }
          if (!sourceBranch || sourceBranch == 'undefined') {
            error('Unable to resolve source branch from Jenkins or Git checkout metadata.')
          }
          env.SOURCE_BRANCH_RESOLVED = sourceBranch
          env.TARGET_ENV_RESOLVED = resolveTargetEnvironment(env.SOURCE_BRANCH_RESOLVED)
          assertBranchPolicy(env.TARGET_ENV_RESOLVED, env.SOURCE_BRANCH_RESOLVED)
          if (params.APPLY && params.DESTROY) {
            error('APPLY and DESTROY are mutually exclusive.')
          }
          if (!params.DESTROY && params.DEPLOY_SAGEMAKER_ENDPOINTS && !params.TRAIN_MODELS) {
            error('DEPLOY_SAGEMAKER_ENDPOINTS=true requires TRAIN_MODELS=true so Terraform receives fresh approved model artifacts.')
          }
          if (params.DESTROY && params.DESTROY_CONFIRM != "destroy-${env.TARGET_ENV_RESOLVED}") {
            error("DESTROY_CONFIRM must exactly equal destroy-${env.TARGET_ENV_RESOLVED}.")
          }
          env.TF_ROOT = "infra/envs/${env.TARGET_ENV_RESOLVED}"
          env.MODEL_VERSION = "${env.SOURCE_BRANCH_RESOLVED}-${env.BUILD_NUMBER}".replaceAll('[^A-Za-z0-9_.-]', '-')
          env.AWS_DEPLOY_ROLE_CREDENTIAL_ID = "aws-deploy-role-arn-${env.TARGET_ENV_RESOLVED}"
          env.DEPLOY_SAGEMAKER_ENDPOINTS_RESOLVED = (!params.DESTROY && params.DEPLOY_SAGEMAKER_ENDPOINTS).toString()
        }
        sh '''
          set -eu
          test -d "${TF_ROOT}"
          mkdir -p "${DIST_DIR}" "${REPORTS_DIR}"
          printf 'Source branch: %s\n' "${SOURCE_BRANCH_RESOLVED}"
          printf 'Target environment: %s\n' "${TARGET_ENV_RESOLVED}"
          printf 'Terraform root: %s\n' "${TF_ROOT}"
          printf 'Model version: %s\n' "${MODEL_VERSION}"
          printf 'Deploy SageMaker endpoints: %s\n' "${DEPLOY_SAGEMAKER_ENDPOINTS_RESOLVED}"
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
        expression { return params.TRAIN_MODELS && !params.DESTROY }
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
      when {
        expression { return !params.DESTROY }
      }
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
            AWS_ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"

            scripts/package_lambda.sh
            aws s3 cp "dist/lambda/aiops-lambda.zip" "s3://${LAMBDA_ARTIFACT_BUCKET}/lambda/${TARGET_ENV_RESOLVED}/${BUILD_NUMBER}/aiops-lambda.zip"
            jq -n \
              --arg account_id "${AWS_ACCOUNT_ID}" \
              --arg region "${AWS_REGION}" \
              --arg bucket "${LAMBDA_ARTIFACT_BUCKET}" \
              --arg key "lambda/${TARGET_ENV_RESOLVED}/${BUILD_NUMBER}/aiops-lambda.zip" \
              --arg hash "$(cat dist/lambda/aiops-lambda.zip.base64sha256)" \
              --argjson enable_sagemaker_endpoints "${DEPLOY_SAGEMAKER_ENDPOINTS_RESOLVED}" \
              '{
                aws_account_id: $account_id,
                aws_region: $region,
                lambda_artifact_bucket: $bucket,
                lambda_artifact_key: $key,
                lambda_source_code_hash: $hash,
                enable_aiops_control_plane: true,
                enable_sagemaker_endpoints: $enable_sagemaker_endpoints
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

    stage('Validate Terraform Handoff') {
      when {
        expression { return !params.DESTROY }
      }
      steps {
        sh '''
          set -eu
          test -s "${TF_ROOT}/jenkins.auto.tfvars.json"
          jq -e '.aws_account_id and .aws_region and .lambda_artifact_bucket and .lambda_artifact_key and .lambda_source_code_hash and (.enable_aiops_control_plane == true) and (.enable_sagemaker_endpoints | type == "boolean")' \
            "${TF_ROOT}/jenkins.auto.tfvars.json" >/dev/null

          if [ "${DEPLOY_SAGEMAKER_ENDPOINTS_RESOLVED}" = "true" ]; then
            test -s "${TF_ROOT}/model-artifacts.auto.tfvars.json"
            jq -e '
              (.model_version | type == "string" and length > 0) and
              (.cpu_model_artifact_s3_uri | test("^s3://")) and
              (.log_model_artifact_s3_uri | test("^s3://")) and
              (.cpu_model_image_uri | type == "string" and length > 0) and
              (.log_model_image_uri | type == "string" and length > 0)
            ' "${TF_ROOT}/model-artifacts.auto.tfvars.json" >/dev/null
          fi
        '''
      }
      post {
        always {
          archiveArtifacts allowEmptyArchive: true, artifacts: 'infra/envs/*/jenkins.auto.tfvars.json,infra/envs/*/model-artifacts.auto.tfvars.json'
        }
      }
    }

    stage('Prepare Destroy Variables') {
      when {
        expression { return params.DESTROY }
      }
      steps {
        withCredentials([string(credentialsId: "${env.AWS_DEPLOY_ROLE_CREDENTIAL_ID}", variable: 'AWS_DEPLOY_ROLE_ARN')]) {
          sh '''
            set -eu
            set +x
            CREDS="$(aws sts assume-role --role-arn "${AWS_DEPLOY_ROLE_ARN}" --role-session-name "jenkins-aiops-destroy-vars-${BUILD_NUMBER}")"
            export AWS_ACCESS_KEY_ID="$(printf '%s' "${CREDS}" | jq -r '.Credentials.AccessKeyId')"
            export AWS_SECRET_ACCESS_KEY="$(printf '%s' "${CREDS}" | jq -r '.Credentials.SecretAccessKey')"
            export AWS_SESSION_TOKEN="$(printf '%s' "${CREDS}" | jq -r '.Credentials.SessionToken')"
            export AWS_DEFAULT_REGION="${AWS_REGION}"
            AWS_ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"

            jq -n \
              --arg account_id "${AWS_ACCOUNT_ID}" \
              --arg region "${AWS_REGION}" \
              '{
                aws_account_id: $account_id,
                aws_region: $region
              }' > "${TF_ROOT}/jenkins.auto.tfvars.json"
          '''
        }
      }
    }

    stage('Terraform Init') {
      steps {
        withCredentials([string(credentialsId: "${env.AWS_DEPLOY_ROLE_CREDENTIAL_ID}", variable: 'AWS_DEPLOY_ROLE_ARN')]) {
          sh '''
            set -eu
            set +x
            CREDS="$(aws sts assume-role --role-arn "${AWS_DEPLOY_ROLE_ARN}" --role-session-name "jenkins-aiops-backend-${BUILD_NUMBER}")"
            export AWS_ACCESS_KEY_ID="$(printf '%s' "${CREDS}" | jq -r '.Credentials.AccessKeyId')"
            export AWS_SECRET_ACCESS_KEY="$(printf '%s' "${CREDS}" | jq -r '.Credentials.SecretAccessKey')"
            export AWS_SESSION_TOKEN="$(printf '%s' "${CREDS}" | jq -r '.Credentials.SessionToken')"
            export AWS_DEFAULT_REGION="${AWS_REGION}"
            scripts/validate_terraform_backend.sh "${TF_ROOT}"
            scripts/validate_runtime_kms_state.sh "${TARGET_ENV_RESOLVED}"
          '''
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
      post {
        always {
          archiveArtifacts allowEmptyArchive: true, artifacts: 'reports/terraform-backend-*.txt,reports/runtime-kms-*.txt'
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
          '''
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
              if [ "${DESTROY}" = "true" ]; then
                terraform plan -destroy -input=false -out=destroy.tfplan -var-file=jenkins.auto.tfvars.json
                terraform show -no-color destroy.tfplan > destroy.tfplan.txt
                terraform show -json destroy.tfplan > tfplan.json
              else
                terraform plan -input=false -out=tfplan -var-file=jenkins.auto.tfvars.json
                terraform show -no-color tfplan > tfplan.txt
                terraform show -json tfplan > tfplan.json
              fi
              ../../../.iac-venv/bin/checkov -f tfplan.json \
                --skip-check CKV_AWS_2,CKV_AWS_46,CKV_AWS_91,CKV_AWS_103,CKV_AWS_117,CKV_AWS_131,CKV_AWS_150,CKV_AWS_173,CKV_AWS_260,CKV_AWS_272,CKV_AWS_378,CKV2_AWS_20,CKV2_AWS_28,CKV2_AWS_57 \
                -o cli -o json --output-file-path ../../../reports/checkov
            '''
          }
        }
      }
      post {
        always {
          archiveArtifacts allowEmptyArchive: false, fingerprint: true, artifacts: 'infra/envs/*/tfplan.txt,infra/envs/*/destroy.tfplan.txt,reports/checkov*'
        }
      }
    }

    stage('Approval') {
      when {
        expression { return params.DESTROY || (params.APPLY && env.TARGET_ENV_RESOLVED in ['stage', 'prod']) }
      }
      steps {
        script {
          if (params.DESTROY) {
            input message: "Destroy Terraform environment ${env.TARGET_ENV_RESOLVED}?", ok: 'Destroy'
          } else {
            input message: "Apply saved Terraform plan to ${env.TARGET_ENV_RESOLVED}?", ok: 'Apply'
          }
        }
      }
    }

    stage('Terraform Apply') {
      when {
        expression { return params.APPLY || params.DESTROY }
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
              if [ "${DESTROY}" = "true" ]; then
                terraform apply -input=false destroy.tfplan
              else
                terraform apply -input=false tfplan
              fi
            '''
          }
        }
      }
    }

    stage('Smoke Tests') {
      when {
        expression { return params.APPLY && !params.DESTROY && params.RUN_SMOKE_TESTS }
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
      archiveArtifacts allowEmptyArchive: true, fingerprint: true, artifacts: 'dist/**/*,reports/**/*,infra/envs/*/tfplan.txt,infra/envs/*/destroy.tfplan.txt'
      sh 'scripts/cleanup_ephemeral.sh || true'
    }
    failure {
      echo 'Pipeline failed. Review Jenkins logs, archived quality reports, and the Terraform plan output.'
    }
  }
}
