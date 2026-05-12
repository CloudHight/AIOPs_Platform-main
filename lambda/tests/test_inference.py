import unittest

from aiops.inference import extract_score


class InferenceTests(unittest.TestCase):
    def test_extract_score_from_direct_score(self):
        self.assertEqual(extract_score({"score": 0.42}), 0.42)

    def test_extract_score_from_sagemaker_scores_list(self):
        self.assertEqual(extract_score({"scores": [{"score": 0.91}]}), 0.91)

    def test_extract_score_uses_fallback_for_unknown_shape(self):
        self.assertEqual(extract_score({"unexpected": True}, fallback=0.12), 0.12)
