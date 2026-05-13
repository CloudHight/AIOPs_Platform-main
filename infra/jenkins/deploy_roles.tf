data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

locals {
  jenkins_instance_role_arn = "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:role/${local.jenkins_instance_role_name}"

  created_deploy_role_arns = var.create_deploy_roles ? [
    for role in aws_iam_role.jenkins_deploy : role.arn
  ] : []

  deploy_role_policy_attachments = var.create_deploy_roles ? {
    for pair in setproduct(var.deploy_role_environments, var.deploy_role_extra_policy_arns) :
    "${pair[0]}:${pair[1]}" => {
      environment = pair[0]
      policy_arn  = pair[1]
    }
  } : {}
}

resource "aws_iam_role" "jenkins_deploy" {
  for_each = var.create_deploy_roles ? var.deploy_role_environments : toset([])

  name                 = "${var.name_prefix}-jenkins-deploy-${each.key}"
  description          = "Deploy role assumed by Jenkins for the AIOps ${each.key} environment."
  max_session_duration = var.deploy_role_max_session_duration

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowJenkinsControllerAssumeRole"
        Effect = "Allow"
        Principal = {
          AWS = local.jenkins_instance_role_arn
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(local.common_tags, {
    Environment = each.key
    Role        = "JenkinsDeploy"
  })
}

resource "aws_iam_role_policy" "jenkins_deploy" {
  for_each = aws_iam_role.jenkins_deploy

  name = "${var.name_prefix}-jenkins-deploy-${each.key}-policy"
  role = each.value.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "TerraformStateAndArtifactAccess"
        Effect = "Allow"
        Action = [
          "s3:AbortMultipartUpload",
          "s3:CreateBucket",
          "s3:DeleteObject",
          "s3:GetBucketLocation",
          "s3:GetBucketPolicy",
          "s3:GetBucketPublicAccessBlock",
          "s3:GetBucketTagging",
          "s3:GetBucketVersioning",
          "s3:GetEncryptionConfiguration",
          "s3:GetLifecycleConfiguration",
          "s3:GetObject",
          "s3:GetObjectVersion",
          "s3:ListBucket",
          "s3:ListBucketVersions",
          "s3:ListMultipartUploadParts",
          "s3:PutBucketPolicy",
          "s3:PutBucketPublicAccessBlock",
          "s3:PutBucketTagging",
          "s3:PutBucketVersioning",
          "s3:PutEncryptionConfiguration",
          "s3:PutLifecycleConfiguration",
          "s3:PutObject",
          "s3:PutObjectTagging"
        ]
        Resource = "*"
      },
      {
        Sid    = "TerraformLockAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:CreateTable",
          "dynamodb:DeleteItem",
          "dynamodb:DescribeContinuousBackups",
          "dynamodb:DescribeTable",
          "dynamodb:DescribeTimeToLive",
          "dynamodb:GetItem",
          "dynamodb:ListTagsOfResource",
          "dynamodb:PutItem",
          "dynamodb:TagResource",
          "dynamodb:UpdateContinuousBackups",
          "dynamodb:UpdateTable",
          "dynamodb:UpdateTimeToLive"
        ]
        Resource = "*"
      },
      {
        Sid    = "AIOpsInfrastructureDeployment"
        Effect = "Allow"
        Action = [
          "application-autoscaling:*",
          "autoscaling:*",
          "cloudwatch:*",
          "ec2:*",
          "events:*",
          "lambda:*",
          "logs:*",
          "sagemaker:*",
          "secretsmanager:*",
          "sns:*",
          "sqs:*",
          "ssm:*"
        ]
        Resource = "*"
      },
      {
        Sid    = "KmsForStateLogsAndServiceEncryption"
        Effect = "Allow"
        Action = [
          "kms:CreateAlias",
          "kms:CreateGrant",
          "kms:CreateKey",
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:EnableKeyRotation",
          "kms:Encrypt",
          "kms:GenerateDataKey",
          "kms:GetKeyPolicy",
          "kms:GetKeyRotationStatus",
          "kms:ListAliases",
          "kms:ListResourceTags",
          "kms:PutKeyPolicy",
          "kms:RetireGrant",
          "kms:ScheduleKeyDeletion",
          "kms:TagResource",
          "kms:UpdateAlias"
        ]
        Resource = "*"
      },
      {
        Sid    = "IamForProjectRoles"
        Effect = "Allow"
        Action = [
          "iam:AddRoleToInstanceProfile",
          "iam:AttachRolePolicy",
          "iam:CreateInstanceProfile",
          "iam:CreatePolicy",
          "iam:CreatePolicyVersion",
          "iam:CreateRole",
          "iam:DeleteInstanceProfile",
          "iam:DeletePolicy",
          "iam:DeletePolicyVersion",
          "iam:DeleteRole",
          "iam:DeleteRolePolicy",
          "iam:DetachRolePolicy",
          "iam:GetInstanceProfile",
          "iam:GetPolicy",
          "iam:GetPolicyVersion",
          "iam:GetRole",
          "iam:GetRolePolicy",
          "iam:ListAttachedRolePolicies",
          "iam:ListInstanceProfilesForRole",
          "iam:ListPolicyVersions",
          "iam:ListRolePolicies",
          "iam:PutRolePolicy",
          "iam:RemoveRoleFromInstanceProfile",
          "iam:TagInstanceProfile",
          "iam:TagPolicy",
          "iam:TagRole",
          "iam:UntagInstanceProfile",
          "iam:UntagPolicy",
          "iam:UntagRole",
          "iam:UpdateAssumeRolePolicy"
        ]
        Resource = [
          "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:instance-profile/${var.name_prefix}-*",
          "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:policy/${var.name_prefix}-*",
          "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:role/${var.name_prefix}-*"
        ]
      },
      {
        Sid      = "PassAIOpsRolesToAwsServices"
        Effect   = "Allow"
        Action   = "iam:PassRole"
        Resource = "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:role/${var.name_prefix}-*"
        Condition = {
          StringEquals = {
            "iam:PassedToService" = [
              "ec2.amazonaws.com",
              "lambda.amazonaws.com",
              "sagemaker.amazonaws.com"
            ]
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "jenkins_deploy_extra" {
  for_each = local.deploy_role_policy_attachments

  role       = aws_iam_role.jenkins_deploy[each.value.environment].name
  policy_arn = each.value.policy_arn
}
