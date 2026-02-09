"""
Reset DeployMind environment for fresh testing.

This script:
1. Cleans up all existing resources
2. Creates fresh EC2 instance
3. Sets up IAM roles and SSM
4. Prepares environment for deployment testing

Use this to start from a clean slate.
"""
import sys
sys.path.insert(0, '.')

import subprocess
import time

print("=" * 70)
print("RESET DEPLOYMIND FOR TESTING")
print("=" * 70)
print()

# Confirm reset
confirm = input("This will cleanup and recreate all resources. Continue? (y/n): ")
if confirm.lower() != 'y':
    print("Cancelled.")
    sys.exit(0)

print()

try:
    # Step 1: Cleanup existing resources
    print("Step 1: Cleaning up existing resources...")
    print("-" * 70)
    result = subprocess.run(
        ["python", "scripts/cleanup_resources.py"],
        input="DELETE\n",
        text=True,
        capture_output=False
    )

    if result.returncode != 0:
        print("Warning: Cleanup had issues, continuing...")

    print()
    time.sleep(5)

    # Step 2: Create fresh EC2 instance
    print("Step 2: Creating fresh EC2 instance...")
    print("-" * 70)
    from config.settings import Settings
    import boto3

    settings = Settings.load()
    ec2 = boto3.client('ec2', region_name=settings.aws_region)
    iam = boto3.client('iam', region_name=settings.aws_region)

    # Get or create security group
    vpcs = ec2.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['true']}])
    vpc_id = vpcs['Vpcs'][0]['VpcId']

    try:
        sg_response = ec2.describe_security_groups(
            Filters=[
                {'Name': 'group-name', 'Values': ['deploymind-sg']},
                {'Name': 'vpc-id', 'Values': [vpc_id]}
            ]
        )
        if sg_response['SecurityGroups']:
            sg_id = sg_response['SecurityGroups'][0]['GroupId']
            print(f"   Using existing security group: {sg_id}")
        else:
            raise Exception("Need to create SG")
    except:
        # Create security group
        sg = ec2.create_security_group(
            GroupName='deploymind-sg',
            Description='Security group for DeployMind server',
            VpcId=vpc_id
        )
        sg_id = sg['GroupId']

        # Allow SSH (22) and application port (8080)
        ec2.authorize_security_group_ingress(
            GroupId=sg_id,
            IpPermissions=[
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 22,
                    'ToPort': 22,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': 'SSH'}]
                },
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 8080,
                    'ToPort': 8080,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': 'Application'}]
                }
            ]
        )
        print(f"   Created security group: {sg_id}")

    # User data for EC2 setup
    user_data = """#!/bin/bash
set -e

# Update system
apt-get update
apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Start Docker
systemctl start docker
systemctl enable docker

# Add ubuntu user to docker group
usermod -aG docker ubuntu

# Install docker-compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Install Python 3
apt-get install -y python3 python3-pip python3-venv git

echo "DeployMind EC2 setup complete!"
"""

    # Launch instance
    print("   Launching EC2 instance...")
    response = ec2.run_instances(
        ImageId='ami-0e670eb768a5fc3d4',  # Ubuntu 24.04 LTS in ap-south-1
        InstanceType='t2.micro',
        KeyName='',  # No key pair needed for SSM
        SecurityGroupIds=[sg_id],
        MinCount=1,
        MaxCount=1,
        UserData=user_data,
        IamInstanceProfile={'Name': 'DeployMindEC2InstanceProfile'},
        TagSpecifications=[
            {
                'ResourceType': 'instance',
                'Tags': [
                    {'Key': 'Name', 'Value': 'deploymind-server'},
                    {'Key': 'Project', 'Value': 'DeployMind'},
                    {'Key': 'ManagedBy', 'Value': 'DeployMind'}
                ]
            }
        ]
    )

    instance_id = response['Instances'][0]['InstanceId']
    print(f"   Instance created: {instance_id}")

    # Wait for instance to be running
    print("   Waiting for instance to be running...")
    waiter = ec2.get_waiter('instance_running')
    waiter.wait(InstanceIds=[instance_id])

    # Get public IP
    instance_info = ec2.describe_instances(InstanceIds=[instance_id])
    public_ip = instance_info['Reservations'][0]['Instances'][0].get('PublicIpAddress')

    print(f"   Instance running with IP: {public_ip}")

    # Step 3: Setup IAM roles (if needed)
    print("\nStep 3: Setting up IAM roles...")
    print("-" * 70)
    result = subprocess.run(
        ["python", "scripts/fix_ssm_setup.py"],
        capture_output=False
    )

    print()
    print("=" * 70)
    print("RESET COMPLETE!")
    print("=" * 70)
    print()
    print(f"New EC2 Instance: {instance_id}")
    print(f"Public IP: {public_ip}")
    print()
    print("Wait 2-3 minutes for SSM agent to register, then test deployment:")
    print(f"  python scripts/deploy_deploymind_to_ec2.py")
    print()
    print("To stop (without deleting):")
    print("  python scripts/stop_resources.py")
    print()
    print("To cleanup everything:")
    print("  python scripts/cleanup_resources.py")
    print()

except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
