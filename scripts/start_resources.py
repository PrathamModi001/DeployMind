"""
Start/Resume DeployMind AWS resources.

This script:
1. Finds stopped EC2 instances
2. Starts them
3. Waits for SSM agent to be online
4. Displays connection information

Use this after stopping resources to resume work.
"""
import sys
sys.path.insert(0, '.')

import boto3
import time
from config.settings import Settings

# Load settings
settings = Settings.load()

# Initialize AWS clients
ec2 = boto3.client('ec2', region_name=settings.aws_region)

print("=" * 70)
print("START DEPLOYMIND RESOURCES")
print("=" * 70)
print()

try:
    # Step 1: Find stopped instances
    print("1. Finding stopped DeployMind instances...")
    response = ec2.describe_instances(
        Filters=[
            {'Name': 'tag:Project', 'Values': ['DeployMind']},
            {'Name': 'instance-state-name', 'Values': ['stopped']}
        ]
    )

    instances = []
    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            instances.append(instance['InstanceId'])

    if not instances:
        print("   No stopped instances found.")
        print()

        # Check for running instances
        response = ec2.describe_instances(
            Filters=[
                {'Name': 'tag:Project', 'Values': ['DeployMind']},
                {'Name': 'instance-state-name', 'Values': ['running']}
            ]
        )

        running = []
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                instance_id = instance['InstanceId']
                public_ip = instance.get('PublicIpAddress', 'No public IP')
                running.append((instance_id, public_ip))

        if running:
            print("   Already running instances:")
            for inst_id, ip in running:
                print(f"      - {inst_id} (IP: {ip})")
            print()
            print("=" * 70)
            print("RESOURCES ALREADY RUNNING")
            print("=" * 70)
            for inst_id, ip in running:
                print(f"\nInstance: {inst_id}")
                print(f"Public IP: {ip}")
                if ip != 'No public IP':
                    print(f"Application: http://{ip}:8080")
        else:
            print("   No DeployMind instances found.")
            print("   Run: python scripts/reset_for_testing.py")

        sys.exit(0)

    print(f"   Found {len(instances)} stopped instance(s): {', '.join(instances)}")
    print()

    # Step 2: Start instances
    print("2. Starting instances...")
    ec2.start_instances(InstanceIds=instances)
    print(f"   Start command sent for: {', '.join(instances)}")
    print()

    # Step 3: Wait for running state
    print("3. Waiting for instances to be running...")
    waiter = ec2.get_waiter('instance_running')
    waiter.wait(InstanceIds=instances)
    print("   All instances running")
    print()

    # Step 4: Get instance information
    print("4. Getting instance information...")
    response = ec2.describe_instances(InstanceIds=instances)

    instance_info = []
    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            instance_id = instance['InstanceId']
            public_ip = instance.get('PublicIpAddress', 'No public IP')
            private_ip = instance.get('PrivateIpAddress', 'No private IP')
            state = instance['State']['Name']
            instance_info.append({
                'id': instance_id,
                'public_ip': public_ip,
                'private_ip': private_ip,
                'state': state
            })

    print("   Instance information retrieved")
    print()

    # Step 5: Wait for SSM agent
    print("5. Waiting for SSM agent to be online (may take 2-3 minutes)...")
    ssm = boto3.client('ssm', region_name=settings.aws_region)

    max_wait = 180  # 3 minutes
    wait_interval = 10
    elapsed = 0

    all_online = False
    while elapsed < max_wait and not all_online:
        try:
            response = ssm.describe_instance_information(
                Filters=[
                    {'Key': 'InstanceIds', 'Values': instances}
                ]
            )

            online_instances = [info['InstanceId'] for info in response['InstanceInformationList']]

            if len(online_instances) == len(instances):
                all_online = True
                print("   All SSM agents online!")
                break
            else:
                print(f"   Waiting... ({len(online_instances)}/{len(instances)} online, {elapsed}s elapsed)")
                time.sleep(wait_interval)
                elapsed += wait_interval
        except Exception as e:
            print(f"   Checking... ({elapsed}s elapsed)")
            time.sleep(wait_interval)
            elapsed += wait_interval

    if not all_online:
        print("   Warning: SSM agents not yet online. May need a few more minutes.")

    print()

    # Summary
    print("=" * 70)
    print("RESOURCES STARTED")
    print("=" * 70)
    print()

    for info in instance_info:
        print(f"Instance: {info['id']}")
        print(f"State: {info['state']}")
        print(f"Public IP: {info['public_ip']}")
        print(f"Private IP: {info['private_ip']}")

        if info['public_ip'] != 'No public IP':
            print(f"\nApplication URL: http://{info['public_ip']}:8080")
            print(f"Health Check: http://{info['public_ip']}:8080/health")

        print()

    if all_online:
        print("SSM Status: Online (ready for deployments)")
    else:
        print("SSM Status: Connecting... (wait 2-3 minutes, then test)")

    print()
    print("Next steps:")
    print("  - Test deployment: python scripts/test_day4_workflow.py")
    print("  - Stop resources: python scripts/stop_resources.py")
    print("  - Cleanup all: python scripts/cleanup_resources.py")
    print()

except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
