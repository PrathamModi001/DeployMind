"""
Delete ALL AWS resources created by DeployMind.

WARNING: This will permanently delete:
- EC2 instances
- Security groups
- IAM roles and instance profiles
- All associated data

Use this to completely clean up after testing.
"""
import sys
sys.path.insert(0, '.')

import boto3
import time
from deploymind.config.settings import Settings

# Load settings
settings = Settings.load()

# Initialize AWS clients
ec2 = boto3.client('ec2', region_name=settings.aws_region)
iam = boto3.client('iam', region_name=settings.aws_region)

print("=" * 70)
print("CLEANUP DEPLOYMIND RESOURCES")
print("WARNING: This will PERMANENTLY DELETE all resources!")
print("=" * 70)
print()

# Confirm deletion
confirm = input("Type 'DELETE' to confirm: ")
if confirm != "DELETE":
    print("Cancelled.")
    sys.exit(0)

print()

try:
    # Step 1: Terminate EC2 instances
    print("1. Terminating EC2 instances...")
    response = ec2.describe_instances(
        Filters=[
            {'Name': 'tag:Project', 'Values': ['DeployMind']},
            {'Name': 'instance-state-name', 'Values': ['running', 'stopped']}
        ]
    )

    instances = []
    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            instances.append(instance['InstanceId'])

    if instances:
        print(f"   Terminating {len(instances)} instance(s)...")
        ec2.terminate_instances(InstanceIds=instances)

        # Wait for termination
        print("   Waiting for instances to terminate...")
        waiter = ec2.get_waiter('instance_terminated')
        waiter.wait(InstanceIds=instances)
        print(f"   Terminated: {', '.join(instances)}")
    else:
        print("   No instances found")

    # Step 2: Delete security groups
    print("\n2. Deleting security groups...")
    try:
        sgs = ec2.describe_security_groups(
            Filters=[
                {'Name': 'group-name', 'Values': ['deploymind-sg']}
            ]
        )

        for sg in sgs['SecurityGroups']:
            sg_id = sg['GroupId']
            print(f"   Deleting security group: {sg_id}")
            time.sleep(5)  # Wait for instances to fully terminate
            ec2.delete_security_group(GroupId=sg_id)
            print(f"   Deleted: {sg_id}")
    except Exception as e:
        print(f"   Note: {e}")

    # Step 3: Detach and delete IAM instance profile
    print("\n3. Cleaning up IAM resources...")
    try:
        # Remove role from instance profile
        try:
            iam.remove_role_from_instance_profile(
                InstanceProfileName='DeployMindEC2InstanceProfile',
                RoleName='DeployMindEC2Role'
            )
            print("   Removed role from instance profile")
        except:
            pass

        # Delete instance profile
        try:
            iam.delete_instance_profile(
                InstanceProfileName='DeployMindEC2InstanceProfile'
            )
            print("   Deleted instance profile: DeployMindEC2InstanceProfile")
        except:
            pass

        # Detach policies from role
        try:
            iam.detach_role_policy(
                RoleName='DeployMindEC2Role',
                PolicyArn='arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore'
            )
            print("   Detached SSM policy from role")
        except:
            pass

        # Delete role
        try:
            iam.delete_role(RoleName='DeployMindEC2Role')
            print("   Deleted role: DeployMindEC2Role")
        except:
            pass

    except Exception as e:
        print(f"   Note: {e}")

    # Step 4: Clean up local Docker images
    print("\n4. Cleaning up local Docker images...")
    try:
        import docker
        client = docker.from_env()
        images = client.images.list(filters={'reference': 'prathammodi001-deploymind:*'})
        for image in images:
            print(f"   Removing image: {image.tags}")
            client.images.remove(image.id, force=True)
        print(f"   Removed {len(images)} image(s)")
    except Exception as e:
        print(f"   Note: {e}")

    print()
    print("=" * 70)
    print("CLEANUP COMPLETE")
    print("=" * 70)
    print()
    print("Deleted resources:")
    print(f"  - EC2 Instances: {len(instances)}")
    print("  - Security Groups: deploymind-sg")
    print("  - IAM Roles: DeployMindEC2Role")
    print("  - IAM Instance Profiles: DeployMindEC2InstanceProfile")
    print()

except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
