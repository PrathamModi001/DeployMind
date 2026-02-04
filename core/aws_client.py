"""AWS boto3 wrapper for DeployMind."""

from __future__ import annotations

from typing import TYPE_CHECKING

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from core.config import Config
from core.logger import get_logger

if TYPE_CHECKING:
    from mypy_boto3_ec2.client import EC2Client

logger = get_logger(__name__)


class AWSClient:
    """Wrapper around AWS boto3 for EC2 operations."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self._ec2: EC2Client | None = None

    @property
    def ec2(self) -> EC2Client:
        """Lazy-initialize EC2 client."""
        if self._ec2 is None:
            self._ec2 = boto3.client(
                "ec2",
                region_name=self.config.aws_region,
                aws_access_key_id=self.config.aws_access_key_id,
                aws_secret_access_key=self.config.aws_secret_access_key,
            )
        return self._ec2

    def validate_credentials(self) -> bool:
        """Check if AWS credentials are valid by calling STS."""
        try:
            sts = boto3.client(
                "sts",
                aws_access_key_id=self.config.aws_access_key_id,
                aws_secret_access_key=self.config.aws_secret_access_key,
            )
            identity = sts.get_caller_identity()
            logger.info("AWS credentials valid", extra={"account": identity["Account"]})
            return True
        except (ClientError, NoCredentialsError) as e:
            logger.error("AWS credential validation failed", extra={"error": str(e)})
            return False

    def get_instance_status(self, instance_id: str) -> dict:
        """Get the status of an EC2 instance."""
        raise NotImplementedError("Will be implemented on Day 4")

    def run_command_on_instance(self, instance_id: str, command: str) -> dict:
        """Execute a command on an EC2 instance via SSM."""
        raise NotImplementedError("Will be implemented on Day 4")

    def get_instance_public_ip(self, instance_id: str) -> str | None:
        """Get the public IP address of an EC2 instance."""
        raise NotImplementedError("Will be implemented on Day 4")
