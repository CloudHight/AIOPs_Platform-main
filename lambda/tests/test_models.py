import unittest

from aiops.models import AnomalySignal, correlation_id


class ModelTests(unittest.TestCase):
    def test_correlation_id_is_deterministic(self):
        first = correlation_id("dev", "i-123", "cpu")
        second = correlation_id("dev", "i-123", "cpu")
        self.assertEqual(first, second)
        self.assertEqual(len(first), 24)

    def test_anomaly_signal_threshold_check(self):
        signal = AnomalySignal(
            instance_id="i-123",
            anomaly_type="cpu",
            score=0.9,
            threshold=0.85,
            severity="high",
        )
        self.assertTrue(signal.is_anomalous())
