"""Configuration loader for DeployMind.

Loads configuration from multiple sources with priority:
1. CLI arguments (highest priority)
2. .deploymind.yml file
3. Environment variables (lowest priority)
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
import yaml
from dataclasses import dataclass, field

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DeploymentProfile:
    """Deployment profile configuration."""
    name: str
    repository: Optional[str] = None
    instance_id: Optional[str] = None
    port: int = 8080
    health_check_path: str = "/health"
    strategy: str = "rolling"
    environment: str = "production"
    region: str = "us-east-1"
    # Additional profile-specific settings
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DeployMindConfig:
    """Complete DeployMind configuration."""
    # Default settings
    default_repository: Optional[str] = None
    default_instance: Optional[str] = None
    default_port: int = 8080
    default_strategy: str = "rolling"
    default_environment: str = "production"

    # Profiles
    profiles: Dict[str, DeploymentProfile] = field(default_factory=dict)

    # Retry settings
    max_retries: int = 3
    retry_delay_seconds: int = 5
    retry_exponential_backoff: bool = True

    # Timeout settings
    health_check_timeout: int = 120
    build_timeout: int = 600
    deployment_timeout: int = 300

    # Performance settings
    enable_caching: bool = True
    cache_ttl_seconds: int = 300

    # Logging
    log_level: str = "INFO"
    verbose: bool = False


class ConfigLoader:
    """Loads and merges configuration from multiple sources."""

    DEFAULT_CONFIG_FILES = [
        ".deploymind.yml",
        ".deploymind.yaml",
        "deploymind.yml",
        "deploymind.yaml"
    ]

    def __init__(self, config_path: Optional[str] = None):
        """Initialize config loader.

        Args:
            config_path: Optional explicit path to config file
        """
        self.config_path = config_path
        self.config = DeployMindConfig()

    def load(self) -> DeployMindConfig:
        """Load configuration from all sources.

        Returns:
            Complete configuration object
        """
        # Load from file
        config_file = self._find_config_file()
        if config_file:
            logger.info(f"Loading configuration from {config_file}")
            self._load_from_file(config_file)
        else:
            logger.debug("No configuration file found, using defaults")

        # Environment variables can override file settings
        self._load_from_env()

        return self.config

    def _find_config_file(self) -> Optional[Path]:
        """Find configuration file in current directory or parents.

        Returns:
            Path to config file or None if not found
        """
        # Use explicit path if provided
        if self.config_path:
            path = Path(self.config_path)
            if path.exists():
                return path
            logger.warning(f"Config file not found: {self.config_path}")
            return None

        # Search in current directory and parents
        current_dir = Path.cwd()
        for _ in range(5):  # Search up to 5 parent directories
            for config_name in self.DEFAULT_CONFIG_FILES:
                config_file = current_dir / config_name
                if config_file.exists():
                    return config_file
            current_dir = current_dir.parent
            if current_dir == current_dir.parent:  # Reached root
                break

        return None

    def _load_from_file(self, config_path: Path):
        """Load configuration from YAML file.

        Args:
            config_path: Path to YAML config file
        """
        try:
            with open(config_path, 'r') as f:
                data = yaml.safe_load(f)

            if not data:
                logger.warning(f"Empty configuration file: {config_path}")
                return

            # Load default settings
            if 'defaults' in data:
                defaults = data['defaults']
                self.config.default_repository = defaults.get('repository')
                self.config.default_instance = defaults.get('instance')
                self.config.default_port = defaults.get('port', 8080)
                self.config.default_strategy = defaults.get('strategy', 'rolling')
                self.config.default_environment = defaults.get('environment', 'production')

            # Load profiles
            if 'profiles' in data:
                for profile_name, profile_data in data['profiles'].items():
                    profile = DeploymentProfile(
                        name=profile_name,
                        repository=profile_data.get('repository'),
                        instance_id=profile_data.get('instance'),
                        port=profile_data.get('port', 8080),
                        health_check_path=profile_data.get('health_check_path', '/health'),
                        strategy=profile_data.get('strategy', 'rolling'),
                        environment=profile_data.get('environment', 'production'),
                        region=profile_data.get('region', 'us-east-1'),
                        extra=profile_data.get('extra', {})
                    )
                    self.config.profiles[profile_name] = profile

            # Load retry settings
            if 'retry' in data:
                retry = data['retry']
                self.config.max_retries = retry.get('max_retries', 3)
                self.config.retry_delay_seconds = retry.get('delay_seconds', 5)
                self.config.retry_exponential_backoff = retry.get('exponential_backoff', True)

            # Load timeout settings
            if 'timeouts' in data:
                timeouts = data['timeouts']
                self.config.health_check_timeout = timeouts.get('health_check', 120)
                self.config.build_timeout = timeouts.get('build', 600)
                self.config.deployment_timeout = timeouts.get('deployment', 300)

            # Load performance settings
            if 'performance' in data:
                perf = data['performance']
                self.config.enable_caching = perf.get('enable_caching', True)
                self.config.cache_ttl_seconds = perf.get('cache_ttl_seconds', 300)

            # Load logging settings
            if 'logging' in data:
                logging_config = data['logging']
                self.config.log_level = logging_config.get('level', 'INFO')
                self.config.verbose = logging_config.get('verbose', False)

            logger.info(f"Loaded configuration with {len(self.config.profiles)} profiles")

        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML config: {e}")
            raise ValueError(f"Invalid YAML configuration: {e}")
        except Exception as e:
            logger.error(f"Failed to load config file: {e}")
            raise

    def _load_from_env(self):
        """Load configuration overrides from environment variables."""
        # Environment variables with DEPLOYMIND_ prefix can override settings
        if os.getenv('DEPLOYMIND_DEFAULT_REPOSITORY'):
            self.config.default_repository = os.getenv('DEPLOYMIND_DEFAULT_REPOSITORY')

        if os.getenv('DEPLOYMIND_DEFAULT_INSTANCE'):
            self.config.default_instance = os.getenv('DEPLOYMIND_DEFAULT_INSTANCE')

        if os.getenv('DEPLOYMIND_LOG_LEVEL'):
            self.config.log_level = os.getenv('DEPLOYMIND_LOG_LEVEL')

        if os.getenv('DEPLOYMIND_VERBOSE'):
            self.config.verbose = os.getenv('DEPLOYMIND_VERBOSE').lower() in ('true', '1', 'yes')

    def get_profile(self, profile_name: str) -> Optional[DeploymentProfile]:
        """Get a specific deployment profile by name.

        Args:
            profile_name: Name of the profile

        Returns:
            DeploymentProfile or None if not found
        """
        return self.config.profiles.get(profile_name)

    def merge_with_cli_args(
        self,
        repository: Optional[str] = None,
        instance: Optional[str] = None,
        port: Optional[int] = None,
        strategy: Optional[str] = None,
        environment: Optional[str] = None,
        profile: Optional[str] = None
    ) -> Dict[str, Any]:
        """Merge configuration with CLI arguments.

        CLI arguments have highest priority, then profile, then defaults.

        Args:
            repository: Repository from CLI
            instance: Instance ID from CLI
            port: Port from CLI
            strategy: Strategy from CLI
            environment: Environment from CLI
            profile: Profile name to use

        Returns:
            Merged configuration dictionary
        """
        # Start with defaults
        merged = {
            'repository': self.config.default_repository,
            'instance': instance or self.config.default_instance,
            'port': port or self.config.default_port,
            'strategy': strategy or self.config.default_strategy,
            'environment': environment or self.config.default_environment
        }

        # Apply profile if specified
        if profile:
            profile_obj = self.get_profile(profile)
            if profile_obj:
                if profile_obj.repository:
                    merged['repository'] = profile_obj.repository
                if profile_obj.instance_id:
                    merged['instance'] = profile_obj.instance_id
                merged['port'] = profile_obj.port
                merged['strategy'] = profile_obj.strategy
                merged['environment'] = profile_obj.environment
            else:
                logger.warning(f"Profile '{profile}' not found in configuration")

        # CLI arguments override everything
        if repository:
            merged['repository'] = repository
        if instance:
            merged['instance'] = instance
        if port:
            merged['port'] = port
        if strategy:
            merged['strategy'] = strategy
        if environment:
            merged['environment'] = environment

        return merged


def load_config(config_path: Optional[str] = None) -> DeployMindConfig:
    """Convenience function to load configuration.

    Args:
        config_path: Optional explicit path to config file

    Returns:
        Loaded configuration
    """
    loader = ConfigLoader(config_path=config_path)
    return loader.load()
