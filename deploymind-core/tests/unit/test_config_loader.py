"""Unit tests for configuration loader."""

import pytest
import tempfile
import os
from pathlib import Path
import yaml

from deploymind.config.config_loader import (
    ConfigLoader,
    DeployMindConfig,
    DeploymentProfile,
    load_config
)


@pytest.fixture
def temp_config_file():
    """Create a temporary config file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        config = {
            'defaults': {
                'repository': 'testuser/testrepo',
                'instance': 'i-1234567890abcdef0',
                'port': 8080,
                'strategy': 'rolling',
                'environment': 'production'
            },
            'profiles': {
                'dev': {
                    'repository': 'testuser/dev-repo',
                    'instance': 'i-dev123',
                    'port': 3000,
                    'environment': 'development',
                    'region': 'us-west-2'
                },
                'staging': {
                    'repository': 'testuser/staging-repo',
                    'instance': 'i-staging456',
                    'port': 4000,
                    'environment': 'staging',
                    'strategy': 'blue-green'
                }
            },
            'retry': {
                'max_retries': 5,
                'delay_seconds': 10,
                'exponential_backoff': True
            },
            'timeouts': {
                'health_check': 180,
                'build': 900,
                'deployment': 600
            },
            'performance': {
                'enable_caching': True,
                'cache_ttl_seconds': 600
            },
            'logging': {
                'level': 'DEBUG',
                'verbose': True
            }
        }
        yaml.dump(config, f)
        temp_path = f.name

    yield temp_path

    # Cleanup
    os.unlink(temp_path)


@pytest.fixture
def minimal_config_file():
    """Create a minimal config file with only defaults."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        config = {
            'defaults': {
                'repository': 'user/repo',
                'instance': 'i-abc123'
            }
        }
        yaml.dump(config, f)
        temp_path = f.name

    yield temp_path

    os.unlink(temp_path)


@pytest.fixture
def empty_config_file():
    """Create an empty config file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        temp_path = f.name

    yield temp_path

    os.unlink(temp_path)


@pytest.fixture
def invalid_yaml_file():
    """Create an invalid YAML file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        f.write("invalid: yaml: content: [")
        temp_path = f.name

    yield temp_path

    os.unlink(temp_path)


class TestConfigLoader:
    """Test ConfigLoader class."""

    def test_load_full_config(self, temp_config_file):
        """Test loading a complete configuration file."""
        loader = ConfigLoader(config_path=temp_config_file)
        config = loader.load()

        # Check defaults
        assert config.default_repository == 'testuser/testrepo'
        assert config.default_instance == 'i-1234567890abcdef0'
        assert config.default_port == 8080
        assert config.default_strategy == 'rolling'
        assert config.default_environment == 'production'

        # Check profiles
        assert len(config.profiles) == 2
        assert 'dev' in config.profiles
        assert 'staging' in config.profiles

        dev_profile = config.profiles['dev']
        assert dev_profile.repository == 'testuser/dev-repo'
        assert dev_profile.instance_id == 'i-dev123'
        assert dev_profile.port == 3000
        assert dev_profile.environment == 'development'
        assert dev_profile.region == 'us-west-2'

        staging_profile = config.profiles['staging']
        assert staging_profile.strategy == 'blue-green'

        # Check retry settings
        assert config.max_retries == 5
        assert config.retry_delay_seconds == 10
        assert config.retry_exponential_backoff is True

        # Check timeouts
        assert config.health_check_timeout == 180
        assert config.build_timeout == 900
        assert config.deployment_timeout == 600

        # Check performance
        assert config.enable_caching is True
        assert config.cache_ttl_seconds == 600

        # Check logging
        assert config.log_level == 'DEBUG'
        assert config.verbose is True

    def test_load_minimal_config(self, minimal_config_file):
        """Test loading minimal configuration with defaults."""
        loader = ConfigLoader(config_path=minimal_config_file)
        config = loader.load()

        assert config.default_repository == 'user/repo'
        assert config.default_instance == 'i-abc123'
        # Should use built-in defaults for other values
        assert config.default_port == 8080
        assert config.default_strategy == 'rolling'
        assert config.max_retries == 3
        assert config.retry_delay_seconds == 5

    def test_load_empty_config(self, empty_config_file):
        """Test loading an empty config file uses defaults."""
        loader = ConfigLoader(config_path=empty_config_file)
        config = loader.load()

        # Should all be defaults
        assert config.default_repository is None
        assert config.default_instance is None
        assert config.default_port == 8080
        assert len(config.profiles) == 0

    def test_load_invalid_yaml(self, invalid_yaml_file):
        """Test loading invalid YAML raises ValueError."""
        loader = ConfigLoader(config_path=invalid_yaml_file)

        with pytest.raises(ValueError, match="Invalid YAML configuration"):
            loader.load()

    def test_load_nonexistent_file(self):
        """Test loading non-existent config file."""
        loader = ConfigLoader(config_path="/nonexistent/path/config.yml")
        config = loader.load()

        # Should return defaults without error
        assert config.default_repository is None

    def test_load_without_config_file(self):
        """Test loading without any config file."""
        # Change to temp directory with no config files
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                loader = ConfigLoader()
                config = loader.load()

                # Should return defaults
                assert config.default_repository is None
                assert config.default_port == 8080
            finally:
                os.chdir(original_cwd)

    def test_get_profile(self, temp_config_file):
        """Test getting a specific profile."""
        loader = ConfigLoader(config_path=temp_config_file)
        config = loader.load()

        dev_profile = loader.get_profile('dev')
        assert dev_profile is not None
        assert dev_profile.repository == 'testuser/dev-repo'
        assert dev_profile.port == 3000

        # Non-existent profile
        none_profile = loader.get_profile('nonexistent')
        assert none_profile is None

    def test_merge_with_cli_args_no_overrides(self, temp_config_file):
        """Test merging config with no CLI overrides."""
        loader = ConfigLoader(config_path=temp_config_file)
        loader.load()

        merged = loader.merge_with_cli_args()

        assert merged['repository'] == 'testuser/testrepo'
        assert merged['instance'] == 'i-1234567890abcdef0'
        assert merged['port'] == 8080
        assert merged['strategy'] == 'rolling'

    def test_merge_with_cli_args_with_overrides(self, temp_config_file):
        """Test merging config with CLI argument overrides."""
        loader = ConfigLoader(config_path=temp_config_file)
        loader.load()

        merged = loader.merge_with_cli_args(
            repository='newuser/newrepo',
            port=9000,
            strategy='canary'
        )

        # CLI args should override defaults
        assert merged['repository'] == 'newuser/newrepo'
        assert merged['port'] == 9000
        assert merged['strategy'] == 'canary'
        # Non-overridden values use defaults
        assert merged['instance'] == 'i-1234567890abcdef0'
        assert merged['environment'] == 'production'

    def test_merge_with_profile(self, temp_config_file):
        """Test merging config with profile selection."""
        loader = ConfigLoader(config_path=temp_config_file)
        loader.load()

        merged = loader.merge_with_cli_args(profile='dev')

        # Profile values should override defaults
        assert merged['repository'] == 'testuser/dev-repo'
        assert merged['instance'] == 'i-dev123'
        assert merged['port'] == 3000
        assert merged['environment'] == 'development'

    def test_merge_with_profile_and_cli_overrides(self, temp_config_file):
        """Test merging with both profile and CLI overrides."""
        loader = ConfigLoader(config_path=temp_config_file)
        loader.load()

        merged = loader.merge_with_cli_args(
            profile='dev',
            port=5000  # CLI arg overrides profile port
        )

        # CLI arg wins
        assert merged['port'] == 5000
        # Other profile values preserved
        assert merged['repository'] == 'testuser/dev-repo'
        assert merged['environment'] == 'development'

    def test_merge_with_nonexistent_profile(self, temp_config_file):
        """Test merging with non-existent profile name."""
        loader = ConfigLoader(config_path=temp_config_file)
        loader.load()

        merged = loader.merge_with_cli_args(profile='nonexistent')

        # Should fall back to defaults
        assert merged['repository'] == 'testuser/testrepo'
        assert merged['port'] == 8080

    def test_environment_variable_override(self, temp_config_file, monkeypatch):
        """Test environment variables override file settings."""
        # Set environment variables
        monkeypatch.setenv('DEPLOYMIND_DEFAULT_REPOSITORY', 'envuser/envrepo')
        monkeypatch.setenv('DEPLOYMIND_LOG_LEVEL', 'ERROR')
        monkeypatch.setenv('DEPLOYMIND_VERBOSE', 'true')

        loader = ConfigLoader(config_path=temp_config_file)
        config = loader.load()

        # Environment variables should override file settings
        assert config.default_repository == 'envuser/envrepo'
        assert config.log_level == 'ERROR'
        assert config.verbose is True

    def test_config_file_discovery_current_dir(self):
        """Test config file is discovered in current directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create config in temp directory
            config_path = Path(tmpdir) / '.deploymind.yml'
            with open(config_path, 'w') as f:
                yaml.dump({'defaults': {'repository': 'discovered/repo'}}, f)

            # Change to that directory
            original_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                loader = ConfigLoader()
                config = loader.load()

                assert config.default_repository == 'discovered/repo'
            finally:
                os.chdir(original_cwd)

    def test_config_file_discovery_parent_dir(self):
        """Test config file is discovered in parent directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create config in parent directory
            config_path = Path(tmpdir) / '.deploymind.yml'
            with open(config_path, 'w') as f:
                yaml.dump({'defaults': {'repository': 'parent/repo'}}, f)

            # Create subdirectory and change to it
            subdir = Path(tmpdir) / 'subdir'
            subdir.mkdir()

            original_cwd = os.getcwd()
            os.chdir(subdir)
            try:
                loader = ConfigLoader()
                config = loader.load()

                assert config.default_repository == 'parent/repo'
            finally:
                os.chdir(original_cwd)

    def test_load_config_convenience_function(self, temp_config_file):
        """Test the convenience function load_config()."""
        config = load_config(config_path=temp_config_file)

        assert isinstance(config, DeployMindConfig)
        assert config.default_repository == 'testuser/testrepo'
        assert len(config.profiles) == 2


class TestDeploymentProfile:
    """Test DeploymentProfile dataclass."""

    def test_create_profile_with_defaults(self):
        """Test creating profile with default values."""
        profile = DeploymentProfile(name='test')

        assert profile.name == 'test'
        assert profile.repository is None
        assert profile.port == 8080
        assert profile.strategy == 'rolling'
        assert profile.extra == {}

    def test_create_profile_with_custom_values(self):
        """Test creating profile with custom values."""
        profile = DeploymentProfile(
            name='prod',
            repository='user/repo',
            instance_id='i-123',
            port=9000,
            strategy='blue-green',
            extra={'custom_key': 'custom_value'}
        )

        assert profile.name == 'prod'
        assert profile.repository == 'user/repo'
        assert profile.instance_id == 'i-123'
        assert profile.port == 9000
        assert profile.strategy == 'blue-green'
        assert profile.extra['custom_key'] == 'custom_value'


class TestDeployMindConfig:
    """Test DeployMindConfig dataclass."""

    def test_create_config_with_defaults(self):
        """Test creating config with default values."""
        config = DeployMindConfig()

        assert config.default_repository is None
        assert config.default_port == 8080
        assert config.max_retries == 3
        assert config.enable_caching is True
        assert config.profiles == {}

    def test_create_config_with_custom_values(self):
        """Test creating config with custom values."""
        config = DeployMindConfig(
            default_repository='test/repo',
            max_retries=10,
            enable_caching=False
        )

        assert config.default_repository == 'test/repo'
        assert config.max_retries == 10
        assert config.enable_caching is False
