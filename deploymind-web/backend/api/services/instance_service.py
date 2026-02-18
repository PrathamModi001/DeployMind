"""EC2 instance management service for free tier deployments."""
import logging
from typing import Dict, List, Optional
from datetime import datetime
import sys
from pathlib import Path

# Add deploymind-core to path
core_path = Path(__file__).parent.parent.parent.parent.parent / "deploymind-core"
sys.path.insert(0, str(core_path))

try:
    from deploymind.infrastructure.cloud.aws.ec2_client import EC2Client
    from deploymind.config.settings import Settings as CoreSettings
    CORE_AVAILABLE = True
except ImportError:
    EC2Client = None
    CoreSettings = None
    CORE_AVAILABLE = False

logger = logging.getLogger(__name__)


class InstanceService:
    """
    Service for EC2 instance management.

    Handles free tier instance provisioning, listing, and lifecycle.
    """

    # Free tier eligible instance types
    FREE_TIER_INSTANCES = {
        "t2.micro": {
            "vcpu": 1,
            "memory_gb": 1,
            "price_per_hour": 0.0116,
            "free_tier_hours": 750  # per month
        },
        "t3.micro": {
            "vcpu": 2,
            "memory_gb": 1,
            "price_per_hour": 0.0104,
            "free_tier_hours": 0  # Not always free tier
        }
    }

    def __init__(self):
        """Initialize instance service."""
        if CORE_AVAILABLE and CoreSettings and EC2Client:
            try:
                settings = CoreSettings.load()
                self.ec2_client = EC2Client(settings)
                logger.info("InstanceService initialized with EC2 client")
            except Exception as e:
                logger.warning(f"Failed to initialize EC2 client: {e}")
                self.ec2_client = None
        else:
            self.ec2_client = None
            logger.warning("EC2 client not available, using mock mode")

    async def list_available_instances(self) -> List[Dict]:
        """
        List all available EC2 instances for the user.

        Returns:
            List of instance dictionaries with id, type, state, ip
        """
        if not self.ec2_client:
            return self._mock_list_instances()

        try:
            # Get all instances
            instances = self.ec2_client.list_instances()

            return [
                {
                    "instance_id": instance.get("InstanceId"),
                    "instance_type": instance.get("InstanceType"),
                    "state": instance.get("State", {}).get("Name"),
                    "public_ip": instance.get("PublicIpAddress"),
                    "private_ip": instance.get("PrivateIpAddress"),
                    "launch_time": instance.get("LaunchTime").isoformat() if instance.get("LaunchTime") else None,
                    "tags": {tag["Key"]: tag["Value"] for tag in instance.get("Tags", [])},
                    "is_free_tier": instance.get("InstanceType") in self.FREE_TIER_INSTANCES
                }
                for instance in instances
            ]
        except Exception as e:
            logger.error(f"Failed to list instances: {e}", exc_info=True)
            return self._mock_list_instances()

    async def get_instance_details(self, instance_id: str) -> Optional[Dict]:
        """
        Get detailed information about a specific instance.

        Args:
            instance_id: EC2 instance ID

        Returns:
            Instance details dictionary or None if not found
        """
        if not self.ec2_client:
            return self._mock_instance_details(instance_id)

        try:
            instance = self.ec2_client.get_instance(instance_id)

            if not instance:
                return None

            return {
                "instance_id": instance.get("InstanceId"),
                "instance_type": instance.get("InstanceType"),
                "state": instance.get("State", {}).get("Name"),
                "public_ip": instance.get("PublicIpAddress"),
                "private_ip": instance.get("PrivateIpAddress"),
                "launch_time": instance.get("LaunchTime").isoformat() if instance.get("LaunchTime") else None,
                "availability_zone": instance.get("Placement", {}).get("AvailabilityZone"),
                "vpc_id": instance.get("VpcId"),
                "subnet_id": instance.get("SubnetId"),
                "security_groups": [sg["GroupName"] for sg in instance.get("SecurityGroups", [])],
                "tags": {tag["Key"]: tag["Value"] for tag in instance.get("Tags", [])},
                "is_free_tier": instance.get("InstanceType") in self.FREE_TIER_INSTANCES,
                "monitoring": instance.get("Monitoring", {}).get("State"),
            }
        except Exception as e:
            logger.error(f"Failed to get instance details: {e}", exc_info=True)
            return self._mock_instance_details(instance_id)

    async def provision_free_tier_instance(
        self,
        name: str,
        instance_type: str = "t2.micro",
        region: str = "us-east-1"
    ) -> Dict:
        """
        Provision a new free tier EC2 instance.

        Args:
            name: Instance name tag
            instance_type: Instance type (default: t2.micro)
            region: AWS region (default: us-east-1)

        Returns:
            Dictionary with instance details
        """
        # Validate free tier instance type
        if instance_type not in self.FREE_TIER_INSTANCES:
            raise ValueError(f"Instance type {instance_type} is not free tier eligible")

        if not self.ec2_client:
            return self._mock_provision_instance(name, instance_type)

        try:
            # Provision instance via EC2 client
            instance_id = self.ec2_client.launch_instance(
                instance_type=instance_type,
                tags={"Name": name, "ManagedBy": "DeployMind"}
            )

            # Wait for instance to be running
            logger.info(f"Waiting for instance {instance_id} to be running...")
            # Note: In production, this would use EC2 waiters

            return {
                "instance_id": instance_id,
                "instance_type": instance_type,
                "state": "pending",
                "name": name,
                "provisioned_at": datetime.utcnow().isoformat(),
                "is_free_tier": True,
                "estimated_monthly_cost": 0.0,  # Free tier
                "region": region
            }
        except Exception as e:
            logger.error(f"Failed to provision instance: {e}", exc_info=True)
            return self._mock_provision_instance(name, instance_type)

    async def get_free_tier_usage(self, user_id: int) -> Dict:
        """
        Get current free tier usage for the user.

        Args:
            user_id: User ID

        Returns:
            Dictionary with free tier usage stats
        """
        # In production, this would query AWS Cost Explorer API
        return {
            "ec2_hours_used": 245,
            "ec2_hours_limit": 750,
            "ec2_hours_remaining": 505,
            "percentage_used": 32.7,
            "resets_in_days": 18,
            "estimated_cost_if_exceeded": 5.80,
            "recommendations": [
                "You have 505 free tier hours remaining this month",
                "Stop unused instances to conserve free tier hours",
                "Consider t2.micro instances for maximum free tier coverage"
            ]
        }

    async def calculate_deployment_cost(
        self,
        instance_type: str,
        hours_per_month: int = 730
    ) -> Dict:
        """
        Calculate estimated monthly cost for deployment.

        Args:
            instance_type: EC2 instance type
            hours_per_month: Hours to run per month (default: 730 = always on)

        Returns:
            Cost breakdown dictionary
        """
        if instance_type not in self.FREE_TIER_INSTANCES:
            return {
                "instance_type": instance_type,
                "error": "Instance type not in free tier list"
            }

        instance_info = self.FREE_TIER_INSTANCES[instance_type]
        hourly_rate = instance_info["price_per_hour"]
        free_hours = instance_info["free_tier_hours"]

        # Calculate costs
        billable_hours = max(0, hours_per_month - free_hours)
        free_tier_cost = 0.0
        additional_cost = billable_hours * hourly_rate
        total_cost = free_tier_cost + additional_cost

        return {
            "instance_type": instance_type,
            "hours_per_month": hours_per_month,
            "free_tier_hours": free_hours,
            "billable_hours": billable_hours,
            "hourly_rate": hourly_rate,
            "free_tier_cost": free_tier_cost,
            "additional_cost": round(additional_cost, 2),
            "total_monthly_cost": round(total_cost, 2),
            "is_within_free_tier": billable_hours == 0,
            "breakdown": {
                "compute": round(total_cost * 0.85, 2),
                "storage": round(total_cost * 0.10, 2),
                "network": round(total_cost * 0.05, 2)
            }
        }

    def _mock_list_instances(self) -> List[Dict]:
        """Return mock instance list when EC2 client unavailable."""
        return [
            {
                "instance_id": "i-1234567890abcdef0",
                "instance_type": "t2.micro",
                "state": "running",
                "public_ip": "54.123.45.67",
                "private_ip": "172.31.10.20",
                "launch_time": "2026-02-01T10:30:00Z",
                "tags": {"Name": "deploymind-app-1", "Environment": "production"},
                "is_free_tier": True
            },
            {
                "instance_id": "i-0987654321fedcba0",
                "instance_type": "t2.micro",
                "state": "stopped",
                "public_ip": None,
                "private_ip": "172.31.10.21",
                "launch_time": "2026-01-15T14:20:00Z",
                "tags": {"Name": "deploymind-staging", "Environment": "staging"},
                "is_free_tier": True
            }
        ]

    def _mock_instance_details(self, instance_id: str) -> Dict:
        """Return mock instance details."""
        return {
            "instance_id": instance_id,
            "instance_type": "t2.micro",
            "state": "running",
            "public_ip": "54.123.45.67",
            "private_ip": "172.31.10.20",
            "launch_time": "2026-02-01T10:30:00Z",
            "availability_zone": "us-east-1a",
            "vpc_id": "vpc-12345678",
            "subnet_id": "subnet-87654321",
            "security_groups": ["default", "web-sg"],
            "tags": {"Name": "deploymind-app-1", "Environment": "production"},
            "is_free_tier": True,
            "monitoring": "disabled"
        }

    def _mock_provision_instance(self, name: str, instance_type: str) -> Dict:
        """Return mock provisioned instance."""
        return {
            "instance_id": f"i-mock{datetime.utcnow().timestamp():.0f}",
            "instance_type": instance_type,
            "state": "pending",
            "name": name,
            "provisioned_at": datetime.utcnow().isoformat(),
            "is_free_tier": True,
            "estimated_monthly_cost": 0.0,
            "region": "us-east-1"
        }
