import os
import unittest
from unittest.mock import patch

from aiops.config import RuntimeConfig


class ConfigTests(unittest.TestCase):
    def test_runtime_config_parses_boolean_flags(self):
        required = {
            "DYNAMODB_TABLE": "table",
            "SNS_TOPIC_ARN": "arn:aws:sns:us-east-1:123:topic",
            "PROCESSING_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123/q",
            "EVENT_BUS_NAME": "bus",
            "CPU_MODEL_ENDPOINT": "cpu",
            "LOG_MODEL_ENDPOINT": "log",
            "JIRA_PROJECT_KEY": "AIOPS",
            "JIRA_CREDENTIALS_SECRET": "secret",
            "AUTO_REMEDIATION_ENABLED": "true",
            "DRY_RUN": "false",
        }

        with patch.dict(os.environ, required, clear=False):
            config = RuntimeConfig.from_environment()

        self.assertTrue(config.auto_remediation_enabled)
        self.assertFalse(config.dry_run)
        self.assertEqual(config.dynamodb_table, "table")

    def test_runtime_config_defaults_to_safe_remediation(self):
        required = {
            "DYNAMODB_TABLE": "table",
            "SNS_TOPIC_ARN": "topic",
            "PROCESSING_QUEUE_URL": "queue",
            "EVENT_BUS_NAME": "bus",
            "CPU_MODEL_ENDPOINT": "cpu",
            "LOG_MODEL_ENDPOINT": "log",
            "JIRA_PROJECT_KEY": "AIOPS",
            "JIRA_CREDENTIALS_SECRET": "secret",
        }
        environment = {
            key: value
            for key, value in os.environ.items()
            if key not in {"AUTO_REMEDIATION_ENABLED", "DRY_RUN"}
        }
        environment.update(required)

        with patch.dict(os.environ, environment, clear=True):
            config = RuntimeConfig.from_environment()

        self.assertFalse(config.auto_remediation_enabled)
        self.assertTrue(config.dry_run)
