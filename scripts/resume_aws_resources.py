#!/usr/bin/env python3
"""
Resume AWS Resources Script

Resumes previously paused EC2 instances from saved state.

Usage:
    python scripts/resume_aws_resources.py [--dry-run] [--region REGION]
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.secure_logging import get_logger

logger = get_logger(__name__)


class AWSResourceResumer:
    """Resume previously paused AWS resources."""

    def __init__(self, region: Optional[str] = None, dry_run: bool = False):
        """
        Initialize AWS resource resumer.

        Args:
            region: AWS region (if None, will use region from saved state)
            dry_run: If True, only show what would be done without actually doing it
        """
        self.region = region
        self.dry_run = dry_run
        self.state_file = Path(__file__).parent.parent / ".aws_paused_resources.json"

        # EC2 client will be initialized after loading state
        self.ec2_client = None

    def load_state(self) -> Dict[str, Any]:
        """
        Load paused instance state from file.

        Returns:
            State dictionary with paused instances

        Raises:
            FileNotFoundError: If state file doesn't exist
            ValueError: If state file is invalid
        """
        if not self.state_file.exists():
            raise FileNotFoundError(
                f"No paused resources found. State file not found: {self.state_file}\n"
                f"Have you run pause_aws_resources.py first?"
            )

        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)

            logger.info(f"Loaded state from {self.state_file}")
            logger.info(f"Paused at: {state['paused_at']}")
            logger.info(f"Region: {state['region']}")
            logger.info(f"Instances: {len(state['instances'])}")

            return state

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid state file: {e}")

    def init_ec2_client(self, region: str) -> None:
        """Initialize EC2 client for the specified region."""
        try:
            self.ec2_client = boto3.client('ec2', region_name=region)
            logger.info(f"Connected to AWS EC2 in region {region}")
        except NoCredentialsError:
            logger.error("AWS credentials not found. Please configure AWS CLI.")
            raise

    def get_instance_state(self, instance_id: str) -> str:
        """
        Get current state of an EC2 instance.

        Args:
            instance_id: EC2 instance ID

        Returns:
            Instance state (e.g., 'stopped', 'running', 'terminated')
        """
        try:
            response = self.ec2_client.describe_instances(InstanceIds=[instance_id])

            if response['Reservations'] and response['Reservations'][0]['Instances']:
                return response['Reservations'][0]['Instances'][0]['State']['Name']
            else:
                return 'not-found'

        except ClientError as e:
            logger.error(f"Error getting instance state for {instance_id}: {e}")
            return 'error'

    def start_instances(self, instance_ids: List[str]) -> bool:
        """
        Start EC2 instances.

        Args:
            instance_ids: List of instance IDs to start

        Returns:
            True if successful, False otherwise
        """
        if not instance_ids:
            logger.info("No instances to start")
            return True

        if self.dry_run:
            logger.info(f"[DRY RUN] Would start instances: {instance_ids}")
            return True

        try:
            response = self.ec2_client.start_instances(InstanceIds=instance_ids)

            started = []
            for instance in response['StartingInstances']:
                started.append({
                    'instance_id': instance['InstanceId'],
                    'previous_state': instance['PreviousState']['Name'],
                    'current_state': instance['CurrentState']['Name']
                })

            logger.info(f"Successfully started {len(started)} instances")
            for inst in started:
                logger.info(f"  - {inst['instance_id']}: {inst['previous_state']} → {inst['current_state']}")

            return True

        except ClientError as e:
            logger.error(f"Error starting instances: {e}")
            return False

    def wait_for_running(self, instance_ids: List[str], timeout: int = 300) -> bool:
        """
        Wait for instances to reach 'running' state.

        Args:
            instance_ids: List of instance IDs to wait for
            timeout: Maximum wait time in seconds

        Returns:
            True if all instances are running, False on timeout
        """
        if self.dry_run:
            logger.info(f"[DRY RUN] Would wait for instances to start: {instance_ids}")
            return True

        logger.info(f"Waiting for instances to start (timeout: {timeout}s)...")

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = self.ec2_client.describe_instances(InstanceIds=instance_ids)

                all_running = True
                for reservation in response['Reservations']:
                    for instance in reservation['Instances']:
                        state = instance['State']['Name']
                        instance_id = instance['InstanceId']

                        if state == 'pending':
                            all_running = False
                            logger.info(f"  {instance_id}: pending...")
                        elif state == 'running':
                            logger.info(f"  {instance_id}: running ✓")
                        else:
                            logger.warning(f"  {instance_id}: {state}")
                            all_running = False

                if all_running:
                    logger.info("All instances are running!")
                    return True

                time.sleep(10)

            except ClientError as e:
                logger.error(f"Error checking instance state: {e}")
                return False

        logger.error(f"Timeout waiting for instances to start after {timeout}s")
        return False

    def verify_instances(self, instances: List[Dict[str, Any]]) -> List[str]:
        """
        Verify which instances can be resumed.

        Args:
            instances: List of instance information from saved state

        Returns:
            List of instance IDs that can be started
        """
        startable = []
        issues = []

        for inst in instances:
            instance_id = inst['instance_id']
            state = self.get_instance_state(instance_id)

            if state == 'stopped':
                startable.append(instance_id)
                logger.info(f"✓ {instance_id}: stopped (can be started)")
            elif state == 'running':
                logger.info(f"⚠ {instance_id}: already running (skipping)")
            elif state == 'terminated':
                issues.append(f"✗ {instance_id}: terminated (cannot be started)")
            elif state == 'not-found':
                issues.append(f"✗ {instance_id}: not found (may have been deleted)")
            else:
                issues.append(f"⚠ {instance_id}: {state} (unexpected state)")

        if issues:
            logger.warning("\nIssues found:")
            for issue in issues:
                logger.warning(f"  {issue}")

        return startable

    def clear_state_file(self) -> None:
        """Remove state file after successful resume."""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would remove state file: {self.state_file}")
            return

        try:
            self.state_file.unlink()
            logger.info(f"Removed state file: {self.state_file}")
        except Exception as e:
            logger.warning(f"Could not remove state file: {e}")

    def resume_all(self, keep_state: bool = False) -> bool:
        """
        Resume all paused AWS resources.

        Args:
            keep_state: If True, don't delete state file after resume

        Returns:
            True if successful, False otherwise
        """
        logger.info("=" * 60)
        logger.info("AWS Resource Resumer")
        logger.info("=" * 60)
        logger.info(f"Dry Run: {self.dry_run}")
        logger.info("")

        # Load saved state
        try:
            state = self.load_state()
        except (FileNotFoundError, ValueError) as e:
            logger.error(str(e))
            return False

        # Use region from state if not specified
        region = self.region or state['region']
        self.init_ec2_client(region)

        instances = state['instances']

        # Display instances
        logger.info(f"\nInstances to resume ({len(instances)}):")
        for i, inst in enumerate(instances, 1):
            tags_str = ', '.join(f"{k}={v}" for k, v in inst['tags'].items()) if inst['tags'] else 'No tags'
            logger.info(f"{i}. {inst['instance_id']} ({inst['instance_type']})")
            logger.info(f"   Previous IPs: Public={inst['public_ip']}, Private={inst['private_ip']}")
            logger.info(f"   Tags: {tags_str}")
            if 'snapshot_id' in inst:
                logger.info(f"   Snapshot: {inst['snapshot_id']}")
            logger.info("")

        # Verify instance states
        logger.info("Verifying instance states...")
        startable_ids = self.verify_instances(instances)

        if not startable_ids:
            logger.warning("No instances to start")
            return True

        # Confirm action
        if not self.dry_run:
            logger.info(f"\nWill start {len(startable_ids)} instance(s)")
            response = input("Type 'YES' to confirm: ")

            if response != 'YES':
                logger.info("Operation cancelled by user")
                return False

        # Start instances
        success = self.start_instances(startable_ids)

        if not success:
            logger.error("Failed to start instances")
            return False

        # Wait for instances to be running
        if not self.dry_run and startable_ids:
            success = self.wait_for_running(startable_ids)
            if not success:
                logger.error("Some instances did not start properly")
                return False

        # Get new IP addresses
        if not self.dry_run and startable_ids:
            logger.info("\nUpdated instance information:")
            try:
                response = self.ec2_client.describe_instances(InstanceIds=startable_ids)
                for reservation in response['Reservations']:
                    for instance in reservation['Instances']:
                        logger.info(f"  {instance['InstanceId']}:")
                        logger.info(f"    Public IP: {instance.get('PublicIpAddress', 'N/A')}")
                        logger.info(f"    Private IP: {instance.get('PrivateIpAddress', 'N/A')}")
            except ClientError as e:
                logger.warning(f"Could not get updated IPs: {e}")

        # Clear state file
        if not keep_state:
            self.clear_state_file()

        logger.info("")
        logger.info("=" * 60)
        logger.info("✅ AWS resources resumed successfully!")
        logger.info("=" * 60)

        return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Resume previously paused AWS resources",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--region',
        help='AWS region (default: use region from saved state)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without actually doing it'
    )
    parser.add_argument(
        '--keep-state',
        action='store_true',
        help='Keep state file after resume (for debugging)'
    )

    args = parser.parse_args()

    try:
        resumer = AWSResourceResumer(region=args.region, dry_run=args.dry_run)
        success = resumer.resume_all(keep_state=args.keep_state)
        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        logger.info("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
