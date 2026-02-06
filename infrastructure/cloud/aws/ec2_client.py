"""AWS EC2 client implementation.

Migrated from core/aws_client.py to follow Clean Architecture.
"""

from __future__ import annotations
from typing import TYPE_CHECKING
import time

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from config.settings import Settings
from config.logging import get_logger
from shared.exceptions import DeploymentError

if TYPE_CHECKING:
    from mypy_boto3_ec2.client import EC2Client as BotoEC2Client
    from mypy_boto3_ssm.client import SSMClient as BotoSSMClient

logger = get_logger(__name__)


class EC2Client:
    """AWS EC2 client for deployment operations."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._ec2: BotoEC2Client | None = None
        self._ssm: BotoSSMClient | None = None

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

    @property
    def ssm(self) -> BotoSSMClient:
        """Lazy-initialize SSM client for remote command execution."""
        if self._ssm is None:
            self._ssm = boto3.client(
                "ssm",
                region_name=self.settings.aws_region,
                aws_access_key_id=self.settings.aws_access_key_id,
                aws_secret_access_key=self.settings.aws_secret_access_key,
            )
        return self._ssm

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

    def run_command(
        self,
        instance_id: str,
        commands: list[str],
        timeout_seconds: int = 300
    ) -> dict:
        """Execute commands on EC2 instance via SSM.

        Args:
            instance_id: EC2 instance ID
            commands: List of shell commands to execute
            timeout_seconds: Command execution timeout

        Returns:
            dict with keys:
                - command_id: SSM command ID
                - status: Command status (Success, Failed, TimedOut, etc.)
                - stdout: Command output
                - stderr: Command errors
                - exit_code: Command exit code

        Raises:
            DeploymentError: If command execution fails
        """
        try:
            # Send command via SSM
            response = self.ssm.send_command(
                InstanceIds=[instance_id],
                DocumentName="AWS-RunShellScript",
                Parameters={"commands": commands},
                TimeoutSeconds=timeout_seconds
            )

            command_id = response['Command']['CommandId']
            logger.info(f"Executing command on {instance_id}", extra={
                "command_id": command_id,
                "commands": commands
            })

            # Wait for command to complete
            max_attempts = timeout_seconds // 5  # Poll every 5 seconds
            for attempt in range(max_attempts):
                try:
                    invocation = self.ssm.get_command_invocation(
                        CommandId=command_id,
                        InstanceId=instance_id
                    )

                    status = invocation['Status']

                    # Command completed
                    if status in ['Success', 'Failed', 'Cancelled', 'TimedOut']:
                        result = {
                            'command_id': command_id,
                            'status': status,
                            'stdout': invocation.get('StandardOutputContent', ''),
                            'stderr': invocation.get('StandardErrorContent', ''),
                            'exit_code': invocation.get('ResponseCode', -1)
                        }

                        if status == 'Success':
                            logger.info(f"Command succeeded on {instance_id}", extra=result)
                        else:
                            logger.error(f"Command failed on {instance_id}", extra=result)

                        return result

                    # Command still running
                    time.sleep(5)

                except ClientError as e:
                    # Command invocation may not be available immediately
                    if 'InvocationDoesNotExist' in str(e):
                        time.sleep(5)
                        continue
                    raise

            # Timeout waiting for command
            raise DeploymentError(
                f"Command execution timed out after {timeout_seconds} seconds"
            )

        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')

            if error_code == 'InvalidInstanceId':
                raise DeploymentError(
                    f"Instance {instance_id} not found or not managed by SSM"
                ) from e
            elif error_code == 'UnsupportedPlatformType':
                raise DeploymentError(
                    f"Instance {instance_id} platform not supported for SSM"
                ) from e
            else:
                logger.error(f"SSM command execution failed: {e}")
                raise DeploymentError(f"Failed to execute command on {instance_id}") from e

    def check_ssm_agent_status(self, instance_id: str) -> bool:
        """Check if SSM agent is running on instance.

        Args:
            instance_id: EC2 instance ID

        Returns:
            True if SSM agent is online and ready
        """
        try:
            response = self.ssm.describe_instance_information(
                Filters=[
                    {
                        'Key': 'InstanceIds',
                        'Values': [instance_id]
                    }
                ]
            )

            if response['InstanceInformationList']:
                status = response['InstanceInformationList'][0]
                ping_status = status.get('PingStatus', 'Unknown')

                logger.info(f"SSM agent status for {instance_id}: {ping_status}")
                return ping_status == 'Online'

            logger.warning(f"Instance {instance_id} not found in SSM")
            return False

        except ClientError as e:
            logger.error(f"Failed to check SSM agent status: {e}")
            return False
