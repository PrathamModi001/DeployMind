#!/usr/bin/env python3
"""
Pause AWS Resources Script

Stops all DeployMind-related EC2 instances to avoid charges.
Saves state information for later resumption.

Usage:
    python scripts/pause_aws_resources.py [--dry-run] [--region REGION]
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables from .env file
load_dotenv()

from shared.secure_logging import get_logger

logger = get_logger(__name__)


class AWSResourcePauser:
    """Pause AWS resources to avoid charges."""

    def __init__(self, region: str = "us-east-1", dry_run: bool = False):
        """
        Initialize AWS resource pauser.

        Args:
            region: AWS region to operate in
            dry_run: If True, only show what would be done without actually doing it
        """
        self.region = region
        self.dry_run = dry_run
        self.state_file = Path(__file__).parent.parent / ".aws_paused_resources.json"

        try:
            self.ec2_client = boto3.client('ec2', region_name=region)
            logger.info(f"Connected to AWS EC2 in region {region}")
        except NoCredentialsError:
            logger.error("AWS credentials not found. Please configure AWS CLI.")
            raise

    def get_running_instances(self) -> List[Dict[str, Any]]:
        """
        Get all running EC2 instances.

        Returns:
            List of instance information dictionaries
        """
        try:
            response = self.ec2_client.describe_instances(
                Filters=[
                    {'Name': 'instance-state-name', 'Values': ['running']}
                ]
            )

            instances = []
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    instance_info = {
                        'instance_id': instance['InstanceId'],
                        'instance_type': instance['InstanceType'],
                        'launch_time': instance['LaunchTime'].isoformat(),
                        'private_ip': instance.get('PrivateIpAddress', 'N/A'),
                        'public_ip': instance.get('PublicIpAddress', 'N/A'),
                        'tags': {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
                    }
                    instances.append(instance_info)

            logger.info(f"Found {len(instances)} running instances")
            return instances

        except ClientError as e:
            logger.error(f"Error getting instances: {e}")
            raise

    def stop_instances(self, instance_ids: List[str]) -> bool:
        """
        Stop EC2 instances.

        Args:
            instance_ids: List of instance IDs to stop

        Returns:
            True if successful, False otherwise
        """
        if not instance_ids:
            logger.info("No instances to stop")
            return True

        if self.dry_run:
            logger.info(f"[DRY RUN] Would stop instances: {instance_ids}")
            return True

        try:
            response = self.ec2_client.stop_instances(InstanceIds=instance_ids)

            stopped = []
            for instance in response['StoppingInstances']:
                stopped.append({
                    'instance_id': instance['InstanceId'],
                    'previous_state': instance['PreviousState']['Name'],
                    'current_state': instance['CurrentState']['Name']
                })

            logger.info(f"Successfully stopped {len(stopped)} instances")
            for inst in stopped:
                logger.info(f"  - {inst['instance_id']}: {inst['previous_state']} → {inst['current_state']}")

            return True

        except ClientError as e:
            logger.error(f"Error stopping instances: {e}")
            return False

    def save_state(self, instances: List[Dict[str, Any]]) -> None:
        """
        Save paused instance state to file for later resumption.

        Args:
            instances: List of instance information to save
        """
        state = {
            'paused_at': datetime.utcnow().isoformat(),
            'region': self.region,
            'instances': instances
        }

        if self.dry_run:
            logger.info(f"[DRY RUN] Would save state to {self.state_file}")
            logger.info(f"State: {json.dumps(state, indent=2)}")
            return

        try:
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
            logger.info(f"Saved state to {self.state_file}")
        except Exception as e:
            logger.error(f"Error saving state: {e}")
            raise

    def create_snapshots(self, instances: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        Create EBS volume snapshots for instances (optional, for safety).

        Args:
            instances: List of instances to snapshot

        Returns:
            Dictionary mapping instance IDs to snapshot IDs
        """
        snapshots = {}

        for instance in instances:
            instance_id = instance['instance_id']

            if self.dry_run:
                logger.info(f"[DRY RUN] Would create snapshot for {instance_id}")
                continue

            try:
                # Get volumes attached to instance
                response = self.ec2_client.describe_volumes(
                    Filters=[
                        {'Name': 'attachment.instance-id', 'Values': [instance_id]}
                    ]
                )

                for volume in response['Volumes']:
                    volume_id = volume['VolumeId']

                    snapshot = self.ec2_client.create_snapshot(
                        VolumeId=volume_id,
                        Description=f"DeployMind pause snapshot for {instance_id} at {datetime.utcnow().isoformat()}",
                        TagSpecifications=[
                            {
                                'ResourceType': 'snapshot',
                                'Tags': [
                                    {'Key': 'DeployMind', 'Value': 'pause-snapshot'},
                                    {'Key': 'InstanceId', 'Value': instance_id},
                                    {'Key': 'CreatedAt', 'Value': datetime.utcnow().isoformat()}
                                ]
                            }
                        ]
                    )

                    snapshots[instance_id] = snapshot['SnapshotId']
                    logger.info(f"Created snapshot {snapshot['SnapshotId']} for instance {instance_id}")

            except ClientError as e:
                logger.warning(f"Error creating snapshot for {instance_id}: {e}")

        return snapshots

    def pause_all(self, create_snapshots: bool = False) -> bool:
        """
        Pause all AWS resources.

        Args:
            create_snapshots: If True, create EBS snapshots before stopping

        Returns:
            True if successful, False otherwise
        """
        logger.info("=" * 60)
        logger.info("AWS Resource Pauser")
        logger.info("=" * 60)
        logger.info(f"Region: {self.region}")
        logger.info(f"Dry Run: {self.dry_run}")
        logger.info("")

        # Get running instances
        instances = self.get_running_instances()

        if not instances:
            logger.info("No running instances found. Nothing to pause.")
            return True

        # Display instances
        logger.info(f"Found {len(instances)} running instances:")
        for i, inst in enumerate(instances, 1):
            tags_str = ', '.join(f"{k}={v}" for k, v in inst['tags'].items()) if inst['tags'] else 'No tags'
            logger.info(f"{i}. {inst['instance_id']} ({inst['instance_type']})")
            logger.info(f"   Public IP: {inst['public_ip']}, Private IP: {inst['private_ip']}")
            logger.info(f"   Tags: {tags_str}")
            logger.info("")

        # Confirm action
        if not self.dry_run:
            logger.warning("⚠️  This will STOP all listed instances!")
            logger.warning("⚠️  Any running applications will be interrupted!")
            response = input("\nType 'YES' to confirm: ")

            if response != 'YES':
                logger.info("Operation cancelled by user")
                return False

        # Create snapshots if requested
        snapshots = {}
        if create_snapshots:
            logger.info("Creating EBS snapshots...")
            snapshots = self.create_snapshots(instances)
            if snapshots:
                logger.info(f"Created {len(snapshots)} snapshots")

        # Stop instances
        instance_ids = [inst['instance_id'] for inst in instances]
        success = self.stop_instances(instance_ids)

        if not success:
            logger.error("Failed to stop instances")
            return False

        # Add snapshot info to instances
        for inst in instances:
            if inst['instance_id'] in snapshots:
                inst['snapshot_id'] = snapshots[inst['instance_id']]

        # Save state
        self.save_state(instances)

        logger.info("")
        logger.info("=" * 60)
        logger.info("✅ AWS resources paused successfully!")
        logger.info("=" * 60)
        logger.info(f"State saved to: {self.state_file}")
        logger.info("To resume resources, run: python scripts/resume_aws_resources.py")

        return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Pause AWS resources to avoid charges",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--region',
        default='us-east-1',
        help='AWS region (default: us-east-1)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without actually doing it'
    )
    parser.add_argument(
        '--snapshot',
        action='store_true',
        help='Create EBS snapshots before stopping (safety backup)'
    )

    args = parser.parse_args()

    try:
        pauser = AWSResourcePauser(region=args.region, dry_run=args.dry_run)
        success = pauser.pause_all(create_snapshots=args.snapshot)
        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        logger.info("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
