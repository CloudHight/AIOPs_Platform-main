"""Boto3 client and resource factories.

Keeping client creation here makes the runtime code easier to stub in tests.
"""

from __future__ import annotations

import boto3
from botocore.config import Config

_SAGEMAKER_CONFIG = Config(read_timeout=60, retries={"max_attempts": 3, "mode": "standard"})


def cloudwatch():
    return boto3.client("cloudwatch")


def logs():
    return boto3.client("logs")


def sagemaker_runtime():
    return boto3.client("runtime.sagemaker", config=_SAGEMAKER_CONFIG)


def dynamodb_resource():
    return boto3.resource("dynamodb")


def sns():
    return boto3.client("sns")


def sqs():
    return boto3.client("sqs")


def ssm():
    return boto3.client("ssm")


def events():
    return boto3.client("events")


def ec2():
    return boto3.client("ec2")


def secretsmanager():
    return boto3.client("secretsmanager")
