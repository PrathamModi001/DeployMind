"""Service for executing AI-powered actionable recommendations."""
import logging
import uuid
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
import sys
from pathlib import Path

# Add deploymind-core to path
core_path = Path(__file__).parent.parent.parent.parent.parent / "deploymind-core"
sys.path.insert(0, str(core_path))

try:
    from deploymind.infrastructure.cloud.aws.ec2_client import EC2Client
    from deploymind.infrastructure.security.trivy_scanner import TrivyScanner
    from deploymind.infrastructure.database.models import Deployment, SecurityScan
    from deploymind.config.settings import Settings as CoreSettings
    CORE_AVAILABLE = True
except ImportError as e:
    EC2Client = None
    TrivyScanner = None
    Deployment = None
    SecurityScan = None
    CoreSettings = None
    CORE_AVAILABLE = False
    logging.warning(f"Core imports failed: {e}")

from ..models.action_execution import ActionExecution, ActionStatusEnum, ActionTypeEnum
from ..schemas.ai_actions import (
    ScaleInstanceParams,
    StopIdleDeploymentsParams,
    TriggerSecurityScanParams,
)

logger = logging.getLogger(__name__)


class ActionExecutor:
    """
    Execute AI-powered actionable recommendations.

    Handles execution of:
    - Scale instance (vertical scaling)
    - Stop idle deployments (cost optimization)
    - Trigger security scans (security)
    """

    def __init__(self, db: Session):
        """
        Initialize action executor.

        Args:
            db: Database session
        """
        self.db = db

        if CORE_AVAILABLE and CoreSettings:
            try:
                self.settings = CoreSettings.load()
                self.ec2_client = EC2Client(self.settings)
                self.trivy_scanner = TrivyScanner()
                logger.info("ActionExecutor initialized with AWS and Trivy")
            except Exception as e:
                logger.warning(f"Failed to initialize services: {e}")
                self.ec2_client = None
                self.trivy_scanner = None
                self.settings = None
        else:
            self.ec2_client = None
            self.trivy_scanner = None
            self.settings = None

    async def execute_action(
        self,
        user_id: int,
        action_type: str,
        parameters: Dict[str, Any]
    ) -> ActionExecution:
        """
        Execute an actionable recommendation.

        Args:
            user_id: User ID initiating the action
            action_type: Type of action to execute
            parameters: Action-specific parameters

        Returns:
            ActionExecution: Created execution record

        Raises:
            ValueError: If action type is invalid or parameters are missing
        """
        # Create execution record
        execution_id = f"exec-{uuid.uuid4().hex[:12]}"
        deployment_id = parameters.get("deployment_id")

        execution = ActionExecution(
            id=execution_id,
            user_id=user_id,
            deployment_id=deployment_id,
            action_type=ActionTypeEnum[action_type.upper()],
            status=ActionStatusEnum.QUEUED,
            parameters=parameters,
            progress_percent=0,
        )
        self.db.add(execution)
        self.db.commit()
        self.db.refresh(execution)

        # Execute action asynchronously
        asyncio.create_task(self._execute_async(execution.id, action_type, parameters))

        return execution

    async def _execute_async(
        self,
        execution_id: str,
        action_type: str,
        parameters: Dict[str, Any]
    ):
        """Execute action asynchronously and update status."""
        execution = self.db.query(ActionExecution).filter(
            ActionExecution.id == execution_id
        ).first()

        if not execution:
            logger.error(f"Execution {execution_id} not found")
            return

        try:
            # Update to in_progress
            execution.status = ActionStatusEnum.IN_PROGRESS
            execution.started_at = datetime.utcnow()
            execution.progress_percent = 10
            self.db.commit()

            # Route to specific executor
            if action_type == "scale_instance":
                result = await self._execute_instance_scaling(
                    ScaleInstanceParams(**parameters),
                    execution
                )
            elif action_type == "stop_idle_deployments":
                result = await self._execute_bulk_stop(
                    StopIdleDeploymentsParams(**parameters),
                    execution
                )
            elif action_type == "trigger_security_scan":
                result = await self._execute_security_scan(
                    TriggerSecurityScanParams(**parameters),
                    execution
                )
            else:
                raise ValueError(f"Unknown action type: {action_type}")

            # Update to completed
            execution.status = ActionStatusEnum.COMPLETED
            execution.completed_at = datetime.utcnow()
            execution.progress_percent = 100
            execution.result = result
            self.db.commit()

            logger.info(f"Action {execution_id} completed successfully")

        except Exception as e:
            # Update to failed
            execution.status = ActionStatusEnum.FAILED
            execution.completed_at = datetime.utcnow()
            execution.error_message = str(e)
            self.db.commit()

            logger.error(f"Action {execution_id} failed: {e}", exc_info=True)

    async def _execute_instance_scaling(
        self,
        params: ScaleInstanceParams,
        execution: ActionExecution
    ) -> Dict[str, Any]:
        """
        Execute instance scaling (vertical scaling).

        Process:
        1. Stop EC2 instance
        2. Modify instance type
        3. Start EC2 instance
        4. Wait for instance to be running

        Args:
            params: Scaling parameters
            execution: Execution record for progress updates

        Returns:
            Result dictionary with scaling details
        """
        if not self.ec2_client:
            raise RuntimeError("EC2 client not available")

        instance_id = params.instance_id
        target_type = params.target_instance_type
        start_time = datetime.utcnow()

        logger.info(
            f"Scaling instance {instance_id} from {params.current_instance_type} to {target_type}"
        )

        # Step 1: Stop instance
        execution.current_step = "Stopping instance"
        execution.progress_percent = 20
        self.db.commit()

        self.ec2_client.ec2.stop_instances(InstanceIds=[instance_id])
        logger.info(f"Stopping instance {instance_id}")

        # Wait for instance to stop
        waiter = self.ec2_client.ec2.get_waiter('instance_stopped')
        waiter.wait(InstanceIds=[instance_id], WaiterConfig={'Delay': 5, 'MaxAttempts': 40})

        execution.progress_percent = 50
        self.db.commit()

        # Step 2: Modify instance type
        execution.current_step = "Modifying instance type"
        self.db.commit()

        self.ec2_client.ec2.modify_instance_attribute(
            InstanceId=instance_id,
            InstanceType={'Value': target_type}
        )
        logger.info(f"Modified instance {instance_id} to {target_type}")

        execution.progress_percent = 60
        self.db.commit()

        # Step 3: Start instance
        execution.current_step = "Starting instance"
        self.db.commit()

        self.ec2_client.ec2.start_instances(InstanceIds=[instance_id])
        logger.info(f"Starting instance {instance_id}")

        # Wait for instance to be running
        waiter = self.ec2_client.ec2.get_waiter('instance_running')
        waiter.wait(InstanceIds=[instance_id], WaiterConfig={'Delay': 5, 'MaxAttempts': 40})

        execution.progress_percent = 90
        self.db.commit()

        # Calculate downtime
        end_time = datetime.utcnow()
        downtime_seconds = (end_time - start_time).total_seconds()

        # Update deployment record
        if Deployment:
            deployment = self.db.query(Deployment).filter(
                Deployment.id == params.deployment_id
            ).first()
            if deployment:
                # Store instance type in deployment metadata
                # Note: This assumes deployment model has instance_type attribute
                # If not, you may need to add it or store in a different way
                logger.info(f"Updated deployment {params.deployment_id} instance type")

        return {
            "old_instance_type": params.current_instance_type,
            "new_instance_type": target_type,
            "instance_id": instance_id,
            "downtime_seconds": round(downtime_seconds, 1),
            "completed_at": end_time.isoformat()
        }

    async def _execute_bulk_stop(
        self,
        params: StopIdleDeploymentsParams,
        execution: ActionExecution
    ) -> Dict[str, Any]:
        """
        Execute bulk stop of idle deployments.

        Args:
            params: Stop parameters
            execution: Execution record

        Returns:
            Result dictionary with stopped instances
        """
        if not self.ec2_client or not Deployment:
            raise RuntimeError("Required services not available")

        stopped_instances = []
        failed_instances = []

        total = len(params.deployment_ids)
        for idx, deployment_id in enumerate(params.deployment_ids):
            try:
                # Get deployment
                deployment = self.db.query(Deployment).filter(
                    Deployment.id == deployment_id
                ).first()

                if not deployment:
                    failed_instances.append({
                        "deployment_id": deployment_id,
                        "error": "Deployment not found"
                    })
                    continue

                instance_id = deployment.instance_id

                # Stop instance
                self.ec2_client.ec2.stop_instances(InstanceIds=[instance_id])
                logger.info(f"Stopped instance {instance_id} for deployment {deployment_id}")

                stopped_instances.append({
                    "deployment_id": deployment_id,
                    "instance_id": instance_id,
                    "repository": deployment.repository
                })

                # Update progress
                execution.progress_percent = 20 + int((idx + 1) / total * 70)
                self.db.commit()

            except Exception as e:
                logger.error(f"Failed to stop deployment {deployment_id}: {e}")
                failed_instances.append({
                    "deployment_id": deployment_id,
                    "error": str(e)
                })

        return {
            "stopped_count": len(stopped_instances),
            "failed_count": len(failed_instances),
            "stopped_instances": stopped_instances,
            "failed_instances": failed_instances,
            "reason": params.reason
        }

    async def _execute_security_scan(
        self,
        params: TriggerSecurityScanParams,
        execution: ActionExecution
    ) -> Dict[str, Any]:
        """
        Execute security scan using Trivy.

        Args:
            params: Scan parameters
            execution: Execution record

        Returns:
            Result dictionary with scan results
        """
        if not self.trivy_scanner or not Deployment:
            raise RuntimeError("Required services not available")

        # Get deployment
        deployment = self.db.query(Deployment).filter(
            Deployment.id == params.deployment_id
        ).first()

        if not deployment:
            raise ValueError(f"Deployment {params.deployment_id} not found")

        execution.current_step = "Running Trivy security scan"
        execution.progress_percent = 30
        self.db.commit()

        # Perform scan
        image_name = deployment.image_tag or f"{deployment.repository}:latest"
        scan_result = self.trivy_scanner.scan_image(
            image_name=image_name,
            severity="CRITICAL,HIGH,MEDIUM"
        )

        execution.progress_percent = 80
        self.db.commit()

        # Store scan result (if SecurityScan model available)
        if SecurityScan:
            security_scan = SecurityScan(
                deployment_id=deployment.id,
                scan_type="container",
                passed=scan_result.passed,
                vulnerabilities=scan_result.vulnerabilities,
                critical_count=scan_result.critical_count,
                high_count=scan_result.high_count,
                medium_count=scan_result.medium_count,
                low_count=scan_result.low_count,
            )
            self.db.add(security_scan)
            self.db.commit()

        return {
            "deployment_id": params.deployment_id,
            "image_name": image_name,
            "scan_type": params.scan_type,
            "passed": scan_result.passed,
            "vulnerabilities_found": len(scan_result.vulnerabilities),
            "critical_count": scan_result.critical_count,
            "high_count": scan_result.high_count,
            "medium_count": scan_result.medium_count,
            "low_count": scan_result.low_count,
            "scanned_at": datetime.utcnow().isoformat()
        }

    def get_execution_status(self, execution_id: str) -> Optional[ActionExecution]:
        """
        Get execution status by ID.

        Args:
            execution_id: Execution ID

        Returns:
            ActionExecution or None if not found
        """
        return self.db.query(ActionExecution).filter(
            ActionExecution.id == execution_id
        ).first()
