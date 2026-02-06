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

    # Deployment-specific operations (Day 4)

    def deploy_container(
        self,
        instance_id: str,
        image_tag: str,
        container_name: str = "app",
        port: int = 8080,
        env_vars: dict[str, str] | None = None,
        stop_existing: bool = True
    ) -> dict:
        """Deploy Docker container to EC2 instance.

        Performs rolling deployment:
        1. Pull new Docker image
        2. Stop existing container (if requested)
        3. Start new container
        4. Verify container is running

        Args:
            instance_id: EC2 instance ID
            image_tag: Docker image tag (e.g., "myrepo/myapp:v1.0")
            container_name: Container name (default: "app")
            port: Port to expose (default: 8080)
            env_vars: Environment variables dict
            stop_existing: Stop existing container before starting new (default: True)

        Returns:
            dict with deployment details (container_id, status, etc.)

        Raises:
            DeploymentError: If deployment fails
        """
        logger.info(
            f"Deploying container to {instance_id}",
            extra={
                "instance_id": instance_id,
                "image_tag": image_tag,
                "container_name": container_name,
                "port": port
            }
        )

        try:
            # Step 1: Pull Docker image
            pull_result = self.pull_docker_image(instance_id, image_tag)
            if pull_result.get("exit_code") != 0:
                raise DeploymentError(
                    f"Failed to pull image {image_tag}: {pull_result.get('stderr')}"
                )

            # Step 2: Stop existing container (if requested)
            if stop_existing:
                self.stop_container(instance_id, container_name, force=True)

            # Step 3: Build docker run command
            env_flags = []
            if env_vars:
                for key, value in env_vars.items():
                    env_flags.extend(["-e", f"{key}={value}"])

            run_command = [
                "docker", "run", "-d",
                "--name", container_name,
                "-p", f"{port}:{port}",
                *env_flags,
                "--restart", "unless-stopped",
                image_tag
            ]

            # Step 4: Start new container
            start_result = self.run_command(
                instance_id=instance_id,
                commands=[" ".join(run_command)],
                timeout_seconds=120
            )

            if start_result.get("exit_code") != 0:
                raise DeploymentError(
                    f"Failed to start container: {start_result.get('stderr')}"
                )

            container_id = start_result.get("stdout", "").strip()

            # Step 5: Verify container is running
            status_result = self.get_container_status(instance_id, container_name)

            logger.info(
                f"Container deployed successfully",
                extra={
                    "instance_id": instance_id,
                    "container_id": container_id,
                    "container_name": container_name,
                    "status": status_result.get("status")
                }
            )

            return {
                "container_id": container_id,
                "container_name": container_name,
                "image_tag": image_tag,
                "port": port,
                "status": status_result.get("status"),
                "running": status_result.get("running", False)
            }

        except Exception as e:
            logger.error(
                f"Container deployment failed",
                extra={"instance_id": instance_id, "error": str(e)}
            )
            raise DeploymentError(f"Failed to deploy container: {str(e)}") from e

    def pull_docker_image(self, instance_id: str, image_tag: str) -> dict:
        """Pull Docker image on EC2 instance.

        Args:
            instance_id: EC2 instance ID
            image_tag: Docker image tag to pull

        Returns:
            Command execution result
        """
        logger.info(f"Pulling Docker image", extra={"instance_id": instance_id, "image_tag": image_tag})

        return self.run_command(
            instance_id=instance_id,
            commands=[f"docker pull {image_tag}"],
            timeout_seconds=600  # 10 minutes for large images
        )

    def stop_container(
        self,
        instance_id: str,
        container_name: str,
        timeout: int = 30,
        force: bool = False
    ) -> dict:
        """Stop Docker container on EC2 instance.

        Args:
            instance_id: EC2 instance ID
            container_name: Name of container to stop
            timeout: Graceful shutdown timeout (default: 30s)
            force: Force kill if graceful stop fails (default: False)

        Returns:
            Command execution result
        """
        logger.info(
            f"Stopping container",
            extra={
                "instance_id": instance_id,
                "container_name": container_name,
                "force": force
            }
        )

        # Try graceful stop first
        stop_command = f"docker stop -t {timeout} {container_name} 2>/dev/null || true"
        result = self.run_command(
            instance_id=instance_id,
            commands=[stop_command],
            timeout_seconds=timeout + 10
        )

        # Remove container
        rm_command = f"docker rm {container_name} 2>/dev/null || true"
        self.run_command(
            instance_id=instance_id,
            commands=[rm_command],
            timeout_seconds=30
        )

        logger.info(f"Container stopped", extra={"container_name": container_name})
        return result

    def get_container_status(self, instance_id: str, container_name: str) -> dict:
        """Get Docker container status on EC2 instance.

        Args:
            instance_id: EC2 instance ID
            container_name: Name of container to check

        Returns:
            dict with container status:
                - running: bool (is container running)
                - status: str (container status)
                - container_id: str (container ID if exists)
                - uptime: str (how long container has been running)
        """
        # Check if container exists and get status
        inspect_command = f"docker inspect --format '{{{{.State.Status}}}}' {container_name} 2>/dev/null || echo 'not_found'"
        result = self.run_command(
            instance_id=instance_id,
            commands=[inspect_command],
            timeout_seconds=30
        )

        status = result.get("stdout", "").strip()
        running = status == "running"

        container_info = {
            "running": running,
            "status": status,
            "container_name": container_name
        }

        if running:
            # Get container ID and uptime
            id_command = f"docker ps -q -f name={container_name}"
            id_result = self.run_command(
                instance_id=instance_id,
                commands=[id_command],
                timeout_seconds=30
            )
            container_info["container_id"] = id_result.get("stdout", "").strip()

            # Get uptime
            uptime_command = f"docker inspect --format '{{{{.State.StartedAt}}}}' {container_name} 2>/dev/null"
            uptime_result = self.run_command(
                instance_id=instance_id,
                commands=[uptime_command],
                timeout_seconds=30
            )
            container_info["started_at"] = uptime_result.get("stdout", "").strip()

        return container_info

    def list_containers(self, instance_id: str, all_containers: bool = False) -> list[dict]:
        """List Docker containers on EC2 instance.

        Args:
            instance_id: EC2 instance ID
            all_containers: Include stopped containers (default: False)

        Returns:
            List of container info dicts
        """
        flag = "-a" if all_containers else ""
        command = f"docker ps {flag} --format '{{{{.ID}}}}|{{{{.Names}}}}|{{{{.Status}}}}|{{{{.Image}}}}'"

        result = self.run_command(
            instance_id=instance_id,
            commands=[command],
            timeout_seconds=30
        )

        containers = []
        if result.get("exit_code") == 0 and result.get("stdout"):
            for line in result["stdout"].strip().split("\n"):
                if line:
                    parts = line.split("|")
                    if len(parts) >= 4:
                        containers.append({
                            "container_id": parts[0],
                            "name": parts[1],
                            "status": parts[2],
                            "image": parts[3]
                        })

        return containers
