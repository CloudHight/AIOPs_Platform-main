"""Monitored EC2 resource discovery."""

from __future__ import annotations

from . import aws_clients


def monitored_instance_ids(tag_key: str, tag_value: str, client=None) -> list[str]:
    ec2 = client or aws_clients.ec2()
    response = ec2.describe_instances(
        Filters=[
            {"Name": f"tag:{tag_key}", "Values": [tag_value]},
            {"Name": "tag:Project", "Values": ["AIOps"]},
            {"Name": "instance-state-name", "Values": ["running"]},
        ]
    )
    ids: list[str] = []
    for reservation in response.get("Reservations", []):
        for instance in reservation.get("Instances", []):
            ids.append(instance["InstanceId"])
    return ids


def instance_has_required_tags(instance_id: str, tag_key: str, tag_value: str, client=None) -> bool:
    ec2 = client or aws_clients.ec2()
    response = ec2.describe_instances(InstanceIds=[instance_id])
    for reservation in response.get("Reservations", []):
        for instance in reservation.get("Instances", []):
            tags = {tag["Key"]: tag["Value"] for tag in instance.get("Tags", [])}
            return (
                instance.get("State", {}).get("Name") == "running"
                and tags.get(tag_key) == tag_value
                and tags.get("Project") == "AIOps"
            )
    return False
