import subprocess
from typing import Dict, Optional
import json

from app.mcp.registry import registry


class AWSMCP:
    """AWS MCP adapter for cloud infrastructure operations."""

    async def s3_list_buckets(self, args: dict, context: dict = None) -> dict:
        """List S3 buckets.""" 
        try:
            result = subprocess.run(
                ["aws", "s3api", "list-buckets", "--query", "Buckets[].Name"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                buckets = json.loads(result.stdout)
                return {"status": "completed", "buckets": buckets}
            return {"status": "failed", "error": result.stderr}
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    async def s3_upload_file(self, args: dict, context: dict = None) -> dict:
        """Upload file to S3."""
        bucket = args.get("bucket")
        key = args.get("key")
        file_path = args.get("file_path")

        try:
            result = subprocess.run(
                ["aws", "s3", "cp", file_path, f"s3://{bucket}/{key}"],
                capture_output=True, text=True, timeout=60
            )
            return {"status": "completed" if result.returncode == 0 else "failed", "output": result.stdout}
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    async def ec2_list_instances(self, args: dict, context: dict = None) -> dict:
        """List EC2 instances."""
        try:
            result = subprocess.run(
                ["aws", "ec2", "describe-instances", "--query", "Reservations[].Instances[].{Id:InstanceId,State:State.Name}"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                instances = json.loads(result.stdout)
                return {"status": "completed", "instances": instances}
            return {"status": "failed", "error": result.stderr}
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    async def cloudwatch_get_metrics(self, args: dict, context: dict = None) -> dict:
        """Get CloudWatch metrics."""
        namespace = args.get("namespace", "AWS/EC2")
        metric_name = args.get("metric_name", "CPUUtilization")
        dimensions = args.get("dimensions", [])
        period = args.get("period", 300)

        try:
            cmd = [
                "aws", "cloudwatch", "get-metric-statistics",
                "--namespace", namespace,
                "--metric-name", metric_name,
                "--period", str(period),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return {"status": "completed" if result.returncode == 0 else "failed", "output": result.stdout}
        except Exception as e:
            return {"status": "failed", "error": str(e)}


aws_adapter = AWSMCP()

# Register S3 tools
registry.register(
    "s3_list_buckets",
    "List all S3 buckets",
    {"type": "object", "properties": {}, "required": []},
    aws_adapter.s3_list_buckets,
)

registry.register(
    "s3_upload_file",
    "Upload a file to S3",
    {
        "type": "object",
        "properties": {
            "bucket": {"type": "string"},
            "key": {"type": "string"},
            "file_path": {"type": "string"},
        },
        "required": ["bucket", "key", "file_path"],
    },
    aws_adapter.s3_upload_file,
)

# Register EC2 tools
registry.register(
    "ec2_list_instances",
    "List all EC2 instances",
    {"type": "object", "properties": {}, "required": []},
    aws_adapter.ec2_list_instances,
)

# Register CloudWatch tools
registry.register(
    "cloudwatch_get_metrics",
    "Get CloudWatch metrics",
    {
        "type": "object",
        "properties": {
            "namespace": {"type": "string", "default": "AWS/EC2"},
            "metric_name": {"type": "string", "default": "CPUUtilization"},
        },
        "required": [],
    },
    aws_adapter.cloudwatch_get_metrics,
)


def get_aws_mcp() -> AWSMCP:
    return aws_adapter