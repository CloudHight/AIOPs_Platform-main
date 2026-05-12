resource "aws_dynamodb_table" "anomaly_results" {
  name         = "${var.name_prefix}-anomaly-results-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "anomaly_id"

  attribute {
    name = "anomaly_id"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  attribute {
    name = "instance_id"
    type = "S"
  }

  attribute {
    name = "model_type"
    type = "S"
  }

  attribute {
    name = "status"
    type = "S"
  }

  global_secondary_index {
    name            = "InstanceTimestampIndex"
    hash_key        = "instance_id"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "ModelTypeTimestampIndex"
    hash_key        = "model_type"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "StatusTimestampIndex"
    hash_key        = "status"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }

  tags = var.common_tags
}
