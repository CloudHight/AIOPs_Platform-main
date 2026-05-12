import unittest

from botocore.exceptions import ClientError

from aiops.logs_reader import recent_nginx_errors


class FailingLogsClient:
    def filter_log_events(self, **kwargs):
        raise ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "log group missing"}},
            "FilterLogEvents",
        )


class LogsReaderTests(unittest.TestCase):
    def test_recent_nginx_errors_logs_expected_cloudwatch_failures(self):
        with self.assertLogs("aiops.logs_reader", level="WARNING") as captured:
            result = recent_nginx_errors("i-1234567890abcdef0", client=FailingLogsClient())

        self.assertEqual(result, {"error_count": 0, "samples": []})
        self.assertTrue(any("cloudwatch_log_read_failed" in message for message in captured.output))

