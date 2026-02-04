"""AWS EC2 client implementation.

Migrated from core/aws_client.py to follow Clean Architecture.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from config.settings import Settings
from config.logging import get_logger
from shared.exceptions import DeploymentError

if TYPE_CHECKING:
    from mypy_boto3_ec2.client import EC2Client as BotoEC2Client

logger = get_logger(__name__)


class EC2Client:
    """AWS EC2 client for deployment operations."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._ec2: BotoEC2Client | None = None

    @property
    def ec2(self) -> BotoEC2Client:
        """Lazy-initialize EC2 client."""
        if self._ec2 is None:
            self._ec2 = boto3.client(
                "ec2",
                region_name=self.settings.aws_region,
                aws_access_key_id=self.settings.aws_access_key_id,
                aws_secret_access_key=self.settings.aws_secret_access_key,
            )
        return self._ec2

    def validate_credentials(self) -> bool:
        """Check if AWS credentials are valid."""
        try:
            sts = boto3.client(
                "sts",
                aws_access_key_id=self.settings.aws_access_key_id,
                aws_secret_access_key=self.settings.aws_secret_access_key,
            )
            identity = sts.get_caller_identity()
            logger.info("AWS credentials valid", extra={"account": identity["Account"]})
            return True
        except (ClientError, NoCredentialsError) as e:
            logger.error("AWS credential validation failed", extra={"error": str(e)})
            return False

    def describe_instance(self, instance_id: str) -> dict:
        """Get EC2 instance details."""
        try:
            response = self.ec2.describe_instances(InstanceIds=[instance_id])
            if response['Reservations'] and response['Reservations'][0]['Instances']:
                return response['Reservations'][0]['Instances'][0]
            raise DeploymentError(f"Instance {instance_id} not found")
        except ClientError as e:
            logger.error(f"Failed to describe instance: {e}")
            raise DeploymentError(f"Failed to describe instance {instance_id}") from e

    def get_instance_status(self, instance_id: str) -> dict:
        """Get instance status."""
        try:
            response = self.ec2.describe_instance_status(
                InstanceIds=[instance_id],
                IncludeAllInstances=True
            )
            return response['InstanceStatuses'][0] if response['InstanceStatuses'] else {}
        except ClientError as e:
            logger.error(f"Failed to get instance status: {e}")
            raise DeploymentError(f"Failed to get status for {instance_id}") from e

    def get_instance_public_ip(self, instance_id: str) -> str | None:
        """Get instance public IP."""
        instance = self.describe_instance(instance_id)
        return instance.get('PublicIpAddress')
