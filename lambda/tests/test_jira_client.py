import json
import unittest

from aiops.errors import JiraError
from aiops.jira_client import JiraClient, JiraCredentials, load_jira_credentials


class SecretClient:
    def __init__(self, secret: dict[str, str]) -> None:
        self.secret = secret

    def get_secret_value(self, SecretId: str) -> dict[str, str]:  # noqa: N803 - boto3 parameter name
        return {"SecretString": json.dumps(self.secret)}


class JiraClientTests(unittest.TestCase):
    def test_load_credentials_requires_https_url(self):
        client = SecretClient(
            {
                "JIRA_API_URL": "http://jira.example.com",
                "JIRA_USER_EMAIL": "ops@example.com",
                "JIRA_API_TOKEN": "token",
            }
        )

        with self.assertRaisesRegex(JiraError, "HTTPS"):
            load_jira_credentials("jira-secret", client=client)

    def test_load_credentials_rejects_embedded_url_credentials(self):
        client = SecretClient(
            {
                "JIRA_API_URL": "https://user:pass@jira.example.com",
                "JIRA_USER_EMAIL": "ops@example.com",
                "JIRA_API_TOKEN": "token",
            }
        )

        with self.assertRaisesRegex(JiraError, "embedded credentials"):
            load_jira_credentials("jira-secret", client=client)

    def test_client_rejects_external_request_url(self):
        client = JiraClient(
            JiraCredentials(
                api_url="https://jira.example.com",
                user_email="ops@example.com",
                api_token="token",
            ),
            project_key="AIOPS",
        )

        with self.assertRaisesRegex(JiraError, "must start"):
            client._request("POST", "https://attacker.example.com/rest/api/2/issue", {})

