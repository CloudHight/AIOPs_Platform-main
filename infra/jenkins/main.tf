module "jenkins_controller" {
  source = "../modules/jenkins-controller"

  environment                 = var.environment
  name_prefix                 = var.name_prefix
  instance_type               = var.instance_type
  vpc_id                      = var.vpc_id
  subnet_id                   = var.subnet_id
  associate_public_ip_address = var.associate_public_ip_address
  allowed_jenkins_cidrs       = var.allowed_jenkins_cidrs
  root_volume_size_gb         = var.root_volume_size_gb
  jenkins_home_volume_size_gb = var.jenkins_home_volume_size_gb
  allowed_deploy_role_arns    = concat(var.allowed_deploy_role_arns, local.created_deploy_role_arns)
  artifact_bucket_arns        = var.artifact_bucket_arns
  common_tags                 = local.common_tags
}
