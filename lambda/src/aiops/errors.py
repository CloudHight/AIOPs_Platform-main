"""Explicit AIOps control-plane errors."""


class AIOpsError(Exception):
    """Base error for the AIOps Lambda package."""


class ConfigError(AIOpsError):
    """Runtime configuration could not be loaded or parsed."""


class InferenceError(AIOpsError):
    """SageMaker inference failed or returned an unexpected payload."""


class MetricsUnavailableError(AIOpsError):
    """Required CloudWatch metrics are missing."""


class JiraError(AIOpsError):
    """Jira integration failed."""


class AlertingError(AIOpsError):
    """SNS notification failed."""


class RemediationError(AIOpsError):
    """Remediation execution failed."""
