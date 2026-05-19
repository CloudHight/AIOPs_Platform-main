import unittest
from io import BytesIO

from aiops.inference import extract_score, invoke_csv, invoke_json


class FakeRuntimeClient:
    def __init__(self, response_body=b'{"scores":[{"score":0.77}]}'):
        self.response_body = response_body
        self.calls = []

    def invoke_endpoint(self, **kwargs):
        self.calls.append(kwargs)
        return {"Body": BytesIO(self.response_body)}


class InferenceTests(unittest.TestCase):
    def test_extract_score_from_direct_score(self):
        self.assertEqual(extract_score({"score": 0.42}), 0.42)

    def test_extract_score_from_sagemaker_scores_list(self):
        self.assertEqual(extract_score({"scores": [{"score": 0.91}]}), 0.91)

    def test_extract_score_from_bert_list_response(self):
        self.assertEqual(extract_score([{"label": "LABEL_1", "score": 0.88, "threshold": 0.5}]), 0.88)

    def test_extract_score_uses_fallback_for_unknown_shape(self):
        self.assertEqual(extract_score({"unexpected": True}, fallback=0.12), 0.12)

    def test_invoke_csv_uses_cpu_model_contract(self):
        client = FakeRuntimeClient()
        response = invoke_csv("cpu-endpoint", [75.0], client=client)

        self.assertEqual(response, {"scores": [{"score": 0.77}]})
        self.assertEqual(client.calls[0]["EndpointName"], "cpu-endpoint")
        self.assertEqual(client.calls[0]["ContentType"], "text/csv")
        self.assertEqual(client.calls[0]["Body"], b"75.0\n")

    def test_invoke_json_uses_application_json_contract(self):
        client = FakeRuntimeClient(response_body=b'[{"label":"LABEL_0","score":0.1,"threshold":0.5}]')
        response = invoke_json("log-endpoint", {"inputs": "GET / HTTP/1.1 200"}, client=client)

        self.assertEqual(response, [{"label": "LABEL_0", "score": 0.1, "threshold": 0.5}])
        self.assertEqual(client.calls[0]["EndpointName"], "log-endpoint")
        self.assertEqual(client.calls[0]["ContentType"], "application/json")
        self.assertEqual(client.calls[0]["Body"], b'{"inputs": "GET / HTTP/1.1 200"}')
