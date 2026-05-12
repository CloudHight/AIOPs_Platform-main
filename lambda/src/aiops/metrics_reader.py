"""CloudWatch metric readers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from . import aws_clients


def average_cpu_utilization(instance_id: str, minutes: int = 5, client=None) -> float | None:
    cloudwatch = client or aws_clients.cloudwatch()
    end = datetime.now(timezone.utc)
    start = end - timedelta(minutes=minutes)
    response = cloudwatch.get_metric_statistics(
        Namespace="AWS/EC2",
        MetricName="CPUUtilization",
        Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
        StartTime=start,
        EndTime=end,
        Period=max(60, minutes * 60),
        Statistics=["Average"],
    )
    datapoints = response.get("Datapoints", [])
    if not datapoints:
        return None
    return float(max(datapoints, key=lambda item: item["Timestamp"])["Average"])
