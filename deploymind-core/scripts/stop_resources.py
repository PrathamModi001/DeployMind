"""
Stop AWS resources for DeployMind without deleting them.

This script stops:
- EC2 instances (keeps data)
- Containers on EC2 (if accessible)

Resources can be restarted later without losing data.
"""
import sys
sys.path.insert(0, '.')

import boto3
from deploymind.config.settings import Settings

# Load settings
settings = Settings.load()

# Initialize AWS clients
ec2 = boto3.client('ec2', region_name=settings.aws_region)

print("=" * 70)
print("STOP DEPLOYMIND RESOURCES")
print("=" * 70)
print()

try:
    # Find DeployMind EC2 instances
    print("1. Finding DeployMind EC2 instances...")
    response = ec2.describe_instances(
        Filters=[
            {'Name': 'tag:Project', 'Values': ['DeployMind']},
            {'Name': 'instance-state-name', 'Values': ['running']}
        ]
    )

    instances = []
    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            instances.append(instance['InstanceId'])

    if not instances:
        print("   No running instances found")
    else:
        print(f"   Found {len(instances)} running instance(s): {', '.join(instances)}")

        # Stop EC2 instances
        print("\n2. Stopping EC2 instances...")
        ec2.stop_instances(InstanceIds=instances)
        print(f"   Stopped {len(instances)} instance(s)")

        # Wait for instances to stop
        print("\n3. Waiting for instances to stop...")
        waiter = ec2.get_waiter('instance_stopped')
        waiter.wait(InstanceIds=instances)
        print("   All instances stopped successfully")

    print()
    print("=" * 70)
    print("RESOURCES STOPPED")
    print("=" * 70)
    print()
    print("Stopped resources:")
    for instance_id in instances:
        print(f"  - EC2 Instance: {instance_id}")
    print()
    print("To restart:")
    print("  aws ec2 start-instances --instance-ids " + " ".join(instances))
    print()

except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
