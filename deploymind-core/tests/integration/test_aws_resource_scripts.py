"""
Integration tests for AWS resource pause/resume scripts.

Tests the pause_aws_resources.py and resume_aws_resources.py scripts
with mocked AWS API calls to ensure functionality without affecting real resources.
"""

import json
import pytest
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'scripts'))

from pause_aws_resources import AWSResourcePauser
from resume_aws_resources import AWSResourceResumer


@pytest.fixture
def mock_ec2_client():
    """Mock EC2 client for testing."""
    client = Mock()
    return client


@pytest.fixture
def sample_instances():
    """Sample instance data for testing."""
    return [
        {
            'instance_id': 'i-1234567890abcdef0',
            'instance_type': 't3.micro',
            'launch_time': '2026-02-13T10:00:00',
            'private_ip': '172.31.0.100',
            'public_ip': '52.66.207.208',
            'tags': {'Name': 'DeployMind-Test', 'Environment': 'production'}
        },
        {
            'instance_id': 'i-0fedcba9876543210',
            'instance_type': 't3.small',
            'launch_time': '2026-02-13T11:00:00',
            'private_ip': '172.31.0.101',
            'public_ip': '52.66.207.209',
            'tags': {'Name': 'DeployMind-API', 'Environment': 'staging'}
        }
    ]


@pytest.fixture
def sample_state_data(sample_instances):
    """Sample state file data."""
    return {
        'paused_at': '2026-02-13T12:00:00',
        'region': 'us-east-1',
        'instances': sample_instances
    }


class TestAWSResourcePauser:
    """Test AWSResourcePauser class."""

    @patch('boto3.client')
    def test_init_success(self, mock_boto3_client):
        """Test successful initialization."""
        mock_client = Mock()
        mock_boto3_client.return_value = mock_client

        pauser = AWSResourcePauser(region='us-west-2', dry_run=True)

        assert pauser.region == 'us-west-2'
        assert pauser.dry_run is True
        assert pauser.ec2_client == mock_client
        mock_boto3_client.assert_called_once_with('ec2', region_name='us-west-2')

    @patch('boto3.client')
    def test_init_no_credentials(self, mock_boto3_client):
        """Test initialization fails without credentials."""
        from botocore.exceptions import NoCredentialsError
        mock_boto3_client.side_effect = NoCredentialsError()

        with pytest.raises(NoCredentialsError):
            AWSResourcePauser()

    @patch('boto3.client')
    def test_get_running_instances_success(self, mock_boto3_client):
        """Test getting running instances."""
        mock_client = Mock()
        mock_boto3_client.return_value = mock_client

        # Mock describe_instances response
        mock_client.describe_instances.return_value = {
            'Reservations': [
                {
                    'Instances': [
                        {
                            'InstanceId': 'i-1234567890abcdef0',
                            'InstanceType': 't3.micro',
                            'LaunchTime': datetime(2026, 2, 13, 10, 0, 0),
                            'PrivateIpAddress': '172.31.0.100',
                            'PublicIpAddress': '52.66.207.208',
                            'Tags': [
                                {'Key': 'Name', 'Value': 'DeployMind-Test'},
                                {'Key': 'Environment', 'Value': 'production'}
                            ]
                        }
                    ]
                }
            ]
        }

        pauser = AWSResourcePauser(dry_run=True)
        instances = pauser.get_running_instances()

        assert len(instances) == 1
        assert instances[0]['instance_id'] == 'i-1234567890abcdef0'
        assert instances[0]['instance_type'] == 't3.micro'
        assert instances[0]['public_ip'] == '52.66.207.208'
        assert instances[0]['tags']['Name'] == 'DeployMind-Test'

    @patch('boto3.client')
    def test_get_running_instances_empty(self, mock_boto3_client):
        """Test getting running instances when none exist."""
        mock_client = Mock()
        mock_boto3_client.return_value = mock_client
        mock_client.describe_instances.return_value = {'Reservations': []}

        pauser = AWSResourcePauser(dry_run=True)
        instances = pauser.get_running_instances()

        assert instances == []

    @patch('boto3.client')
    def test_stop_instances_dry_run(self, mock_boto3_client):
        """Test stopping instances in dry-run mode."""
        mock_client = Mock()
        mock_boto3_client.return_value = mock_client

        pauser = AWSResourcePauser(dry_run=True)
        result = pauser.stop_instances(['i-1234567890abcdef0'])

        assert result is True
        # Should NOT call AWS API in dry-run mode
        mock_client.stop_instances.assert_not_called()

    @patch('boto3.client')
    def test_stop_instances_success(self, mock_boto3_client):
        """Test successfully stopping instances."""
        mock_client = Mock()
        mock_boto3_client.return_value = mock_client

        # Mock stop_instances response
        mock_client.stop_instances.return_value = {
            'StoppingInstances': [
                {
                    'InstanceId': 'i-1234567890abcdef0',
                    'PreviousState': {'Name': 'running'},
                    'CurrentState': {'Name': 'stopping'}
                }
            ]
        }

        pauser = AWSResourcePauser(dry_run=False)
        result = pauser.stop_instances(['i-1234567890abcdef0'])

        assert result is True
        mock_client.stop_instances.assert_called_once_with(
            InstanceIds=['i-1234567890abcdef0']
        )

    @patch('boto3.client')
    def test_stop_instances_empty_list(self, mock_boto3_client):
        """Test stopping empty list of instances."""
        mock_client = Mock()
        mock_boto3_client.return_value = mock_client

        pauser = AWSResourcePauser(dry_run=False)
        result = pauser.stop_instances([])

        assert result is True
        mock_client.stop_instances.assert_not_called()

    @patch('boto3.client')
    def test_save_state_dry_run(self, mock_boto3_client, sample_instances):
        """Test saving state in dry-run mode."""
        mock_client = Mock()
        mock_boto3_client.return_value = mock_client

        pauser = AWSResourcePauser(dry_run=True)

        # Should not create file in dry-run mode
        with patch('builtins.open', mock_open()) as mock_file:
            pauser.save_state(sample_instances)
            mock_file.assert_not_called()

    @patch('boto3.client')
    def test_save_state_success(self, mock_boto3_client, sample_instances):
        """Test successfully saving state."""
        mock_client = Mock()
        mock_boto3_client.return_value = mock_client

        pauser = AWSResourcePauser(dry_run=False)

        with patch('builtins.open', mock_open()) as mock_file:
            pauser.save_state(sample_instances)

            # Verify file was opened for writing
            mock_file.assert_called_once()
            assert 'w' in str(mock_file.call_args)

    @patch('boto3.client')
    def test_create_snapshots_dry_run(self, mock_boto3_client, sample_instances):
        """Test creating snapshots in dry-run mode."""
        mock_client = Mock()
        mock_boto3_client.return_value = mock_client

        pauser = AWSResourcePauser(dry_run=True)
        snapshots = pauser.create_snapshots(sample_instances)

        # Should return empty dict in dry-run mode
        assert snapshots == {}
        mock_client.describe_volumes.assert_not_called()
        mock_client.create_snapshot.assert_not_called()

    @patch('boto3.client')
    def test_create_snapshots_success(self, mock_boto3_client):
        """Test successfully creating snapshots."""
        mock_client = Mock()
        mock_boto3_client.return_value = mock_client

        # Mock describe_volumes response
        mock_client.describe_volumes.return_value = {
            'Volumes': [
                {'VolumeId': 'vol-1234567890abcdef0'}
            ]
        }

        # Mock create_snapshot response
        mock_client.create_snapshot.return_value = {
            'SnapshotId': 'snap-1234567890abcdef0'
        }

        pauser = AWSResourcePauser(dry_run=False)
        instances = [{'instance_id': 'i-1234567890abcdef0', 'tags': {}}]
        snapshots = pauser.create_snapshots(instances)

        assert 'i-1234567890abcdef0' in snapshots
        assert snapshots['i-1234567890abcdef0'] == 'snap-1234567890abcdef0'
        mock_client.describe_volumes.assert_called_once()
        mock_client.create_snapshot.assert_called_once()


class TestAWSResourceResumer:
    """Test AWSResourceResumer class."""

    @patch('boto3.client')
    def test_init(self, mock_boto3_client):
        """Test initialization."""
        resumer = AWSResourceResumer(region='us-west-2', dry_run=True)

        assert resumer.region == 'us-west-2'
        assert resumer.dry_run is True
        assert resumer.ec2_client is None  # Not initialized yet

    def test_load_state_file_not_found(self):
        """Test loading state when file doesn't exist."""
        resumer = AWSResourceResumer(dry_run=True)

        with pytest.raises(FileNotFoundError) as exc_info:
            resumer.load_state()

        assert "No paused resources found" in str(exc_info.value)

    def test_load_state_success(self, sample_state_data):
        """Test successfully loading state."""
        resumer = AWSResourceResumer(dry_run=True)

        mock_file = mock_open(read_data=json.dumps(sample_state_data))
        with patch('builtins.open', mock_file):
            with patch.object(Path, 'exists', return_value=True):
                state = resumer.load_state()

        assert state['region'] == 'us-east-1'
        assert len(state['instances']) == 2
        assert state['instances'][0]['instance_id'] == 'i-1234567890abcdef0'

    def test_load_state_invalid_json(self):
        """Test loading state with invalid JSON."""
        resumer = AWSResourceResumer(dry_run=True)

        mock_file = mock_open(read_data="invalid json {")
        with patch('builtins.open', mock_file):
            with patch.object(Path, 'exists', return_value=True):
                with pytest.raises(ValueError) as exc_info:
                    resumer.load_state()

        assert "Invalid state file" in str(exc_info.value)

    @patch('boto3.client')
    def test_init_ec2_client_success(self, mock_boto3_client):
        """Test EC2 client initialization."""
        mock_client = Mock()
        mock_boto3_client.return_value = mock_client

        resumer = AWSResourceResumer(dry_run=True)
        resumer.init_ec2_client('us-west-2')

        assert resumer.ec2_client == mock_client
        mock_boto3_client.assert_called_once_with('ec2', region_name='us-west-2')

    @patch('boto3.client')
    def test_get_instance_state_success(self, mock_boto3_client):
        """Test getting instance state."""
        mock_client = Mock()
        mock_boto3_client.return_value = mock_client

        mock_client.describe_instances.return_value = {
            'Reservations': [
                {
                    'Instances': [
                        {'State': {'Name': 'stopped'}}
                    ]
                }
            ]
        }

        resumer = AWSResourceResumer(dry_run=True)
        resumer.ec2_client = mock_client

        state = resumer.get_instance_state('i-1234567890abcdef0')

        assert state == 'stopped'

    @patch('boto3.client')
    def test_get_instance_state_not_found(self, mock_boto3_client):
        """Test getting state of non-existent instance."""
        mock_client = Mock()
        mock_boto3_client.return_value = mock_client

        mock_client.describe_instances.return_value = {'Reservations': []}

        resumer = AWSResourceResumer(dry_run=True)
        resumer.ec2_client = mock_client

        state = resumer.get_instance_state('i-nonexistent')

        assert state == 'not-found'

    @patch('boto3.client')
    def test_start_instances_dry_run(self, mock_boto3_client):
        """Test starting instances in dry-run mode."""
        mock_client = Mock()
        mock_boto3_client.return_value = mock_client

        resumer = AWSResourceResumer(dry_run=True)
        resumer.ec2_client = mock_client

        result = resumer.start_instances(['i-1234567890abcdef0'])

        assert result is True
        mock_client.start_instances.assert_not_called()

    @patch('boto3.client')
    def test_start_instances_success(self, mock_boto3_client):
        """Test successfully starting instances."""
        mock_client = Mock()
        mock_boto3_client.return_value = mock_client

        mock_client.start_instances.return_value = {
            'StartingInstances': [
                {
                    'InstanceId': 'i-1234567890abcdef0',
                    'PreviousState': {'Name': 'stopped'},
                    'CurrentState': {'Name': 'pending'}
                }
            ]
        }

        resumer = AWSResourceResumer(dry_run=False)
        resumer.ec2_client = mock_client

        result = resumer.start_instances(['i-1234567890abcdef0'])

        assert result is True
        mock_client.start_instances.assert_called_once_with(
            InstanceIds=['i-1234567890abcdef0']
        )

    @patch('boto3.client')
    def test_verify_instances_all_stopped(self, mock_boto3_client, sample_instances):
        """Test verifying instances that are all stopped."""
        mock_client = Mock()
        mock_boto3_client.return_value = mock_client

        # All instances are stopped
        mock_client.describe_instances.side_effect = [
            {'Reservations': [{'Instances': [{'State': {'Name': 'stopped'}}]}]},
            {'Reservations': [{'Instances': [{'State': {'Name': 'stopped'}}]}]}
        ]

        resumer = AWSResourceResumer(dry_run=True)
        resumer.ec2_client = mock_client

        startable = resumer.verify_instances(sample_instances)

        assert len(startable) == 2
        assert 'i-1234567890abcdef0' in startable
        assert 'i-0fedcba9876543210' in startable

    @patch('boto3.client')
    def test_verify_instances_mixed_states(self, mock_boto3_client, sample_instances):
        """Test verifying instances with mixed states."""
        mock_client = Mock()
        mock_boto3_client.return_value = mock_client

        # First stopped, second running
        mock_client.describe_instances.side_effect = [
            {'Reservations': [{'Instances': [{'State': {'Name': 'stopped'}}]}]},
            {'Reservations': [{'Instances': [{'State': {'Name': 'running'}}]}]}
        ]

        resumer = AWSResourceResumer(dry_run=True)
        resumer.ec2_client = mock_client

        startable = resumer.verify_instances(sample_instances)

        # Only the stopped instance should be startable
        assert len(startable) == 1
        assert 'i-1234567890abcdef0' in startable

    @patch('boto3.client')
    def test_clear_state_file_dry_run(self, mock_boto3_client):
        """Test clearing state file in dry-run mode."""
        mock_client = Mock()
        mock_boto3_client.return_value = mock_client

        resumer = AWSResourceResumer(dry_run=True)

        with patch.object(Path, 'unlink') as mock_unlink:
            resumer.clear_state_file()
            mock_unlink.assert_not_called()

    @patch('boto3.client')
    def test_clear_state_file_success(self, mock_boto3_client):
        """Test successfully clearing state file."""
        mock_client = Mock()
        mock_boto3_client.return_value = mock_client

        resumer = AWSResourceResumer(dry_run=False)

        with patch.object(Path, 'unlink') as mock_unlink:
            resumer.clear_state_file()
            mock_unlink.assert_called_once()


class TestIntegrationScenarios:
    """End-to-end integration tests for pause/resume workflows."""

    @patch('boto3.client')
    def test_full_pause_resume_cycle_dry_run(self, mock_boto3_client, sample_instances):
        """Test full pause and resume cycle in dry-run mode."""
        mock_client = Mock()
        mock_boto3_client.return_value = mock_client

        # Mock describe_instances for getting running instances
        mock_client.describe_instances.return_value = {
            'Reservations': [
                {
                    'Instances': [
                        {
                            'InstanceId': 'i-1234567890abcdef0',
                            'InstanceType': 't3.micro',
                            'LaunchTime': datetime(2026, 2, 13, 10, 0, 0),
                            'PrivateIpAddress': '172.31.0.100',
                            'PublicIpAddress': '52.66.207.208',
                            'Tags': [
                                {'Key': 'Name', 'Value': 'DeployMind-Test'}
                            ]
                        }
                    ]
                }
            ]
        }

        # Test pause
        pauser = AWSResourcePauser(dry_run=True)
        instances = pauser.get_running_instances()

        assert len(instances) == 1

        result = pauser.stop_instances([inst['instance_id'] for inst in instances])
        assert result is True

        # Simulate saving state (in dry-run, doesn't actually save)
        state_data = {
            'paused_at': datetime.utcnow().isoformat(),
            'region': 'us-east-1',
            'instances': instances
        }

        # Test resume
        resumer = AWSResourceResumer(dry_run=True)

        # Mock state file loading
        with patch.object(resumer, 'load_state', return_value=state_data):
            # Initialize EC2 client
            resumer.init_ec2_client('us-east-1')

            # Mock instance state check (stopped)
            with patch.object(resumer, 'get_instance_state', return_value='stopped'):
                startable = resumer.verify_instances(instances)

                assert len(startable) == 1
                assert startable[0] == 'i-1234567890abcdef0'

                result = resumer.start_instances(startable)
                assert result is True

    @patch('boto3.client')
    def test_pause_with_no_running_instances(self, mock_boto3_client):
        """Test pausing when no instances are running."""
        mock_client = Mock()
        mock_boto3_client.return_value = mock_client

        mock_client.describe_instances.return_value = {'Reservations': []}

        pauser = AWSResourcePauser(dry_run=True)
        instances = pauser.get_running_instances()

        assert len(instances) == 0

    @patch('boto3.client')
    def test_resume_with_terminated_instances(self, mock_boto3_client):
        """Test resuming when some instances were terminated."""
        mock_client = Mock()
        mock_boto3_client.return_value = mock_client

        resumer = AWSResourceResumer(dry_run=True)
        resumer.ec2_client = mock_client

        # Mock instance states: first stopped, second terminated
        mock_client.describe_instances.side_effect = [
            {'Reservations': [{'Instances': [{'State': {'Name': 'stopped'}}]}]},
            {'Reservations': [{'Instances': [{'State': {'Name': 'terminated'}}]}]}
        ]

        instances = [
            {'instance_id': 'i-1234567890abcdef0', 'tags': {}},
            {'instance_id': 'i-0fedcba9876543210', 'tags': {}}
        ]

        startable = resumer.verify_instances(instances)

        # Only the stopped instance should be startable
        assert len(startable) == 1
        assert 'i-1234567890abcdef0' in startable


@pytest.mark.integration
class TestRealAWSCalls:
    """
    Tests that would make real AWS API calls.
    These are marked with @pytest.mark.integration and require:
    - Valid AWS credentials
    - Permission to stop/start EC2 instances
    - Run with: pytest -m integration
    """

    @pytest.mark.skip(reason="Requires real AWS credentials and permissions")
    def test_real_pause_dry_run(self):
        """Test pause script with real AWS API in dry-run mode."""
        pauser = AWSResourcePauser(region='us-east-1', dry_run=True)
        instances = pauser.get_running_instances()

        # Should not throw errors even if no instances
        assert isinstance(instances, list)

    @pytest.mark.skip(reason="Requires real AWS credentials and permissions")
    def test_real_resume_no_state(self):
        """Test resume script with real AWS API when no state file exists."""
        resumer = AWSResourceResumer(dry_run=True)

        with pytest.raises(FileNotFoundError):
            resumer.load_state()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
