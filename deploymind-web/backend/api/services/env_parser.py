"""Parse .env files and detect secrets."""
import re
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


class EnvFileParser:
    """Parser for .env files with automatic secret detection."""

    # Patterns that indicate a variable is likely a secret
    SECRET_PATTERNS = [
        r".*PASSWORD.*",
        r".*SECRET.*",
        r".*KEY.*",
        r".*TOKEN.*",
        r".*API.*KEY.*",
        r".*PRIVATE.*",
        r".*CREDENTIALS.*",
        r".*AUTH.*",
        r".*CERT.*",
        r".*PASSPHRASE.*",
    ]

    def parse_env_file(self, content: str) -> List[Dict]:
        """
        Parse .env file content into key-value pairs.

        Args:
            content: .env file content as string

        Returns:
            List of dicts with {key, value, is_secret}
        """
        variables = []
        lines = content.split('\n')

        for line_num, line in enumerate(lines, 1):
            # Skip comments and empty lines
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            # Parse KEY=VALUE format
            if '=' not in line:
                logger.warning(f"Line {line_num} invalid format (missing =): {line}")
                continue

            # Split on first = only
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip()

            # Validate key format (alphanumeric + underscore)
            if not self._is_valid_key(key):
                logger.warning(f"Line {line_num} invalid key format: {key}")
                continue

            # Remove quotes if present
            value = self._remove_quotes(value)

            # Detect if it's a secret
            is_secret = self._is_secret(key)

            variables.append({
                "key": key,
                "value": value,
                "is_secret": is_secret
            })

        return variables

    def parse_env_dict(self, env_dict: Dict[str, str]) -> List[Dict]:
        """
        Parse environment variables from dictionary.

        Args:
            env_dict: Dictionary of environment variables

        Returns:
            List of dicts with {key, value, is_secret}
        """
        variables = []

        for key, value in env_dict.items():
            if not self._is_valid_key(key):
                logger.warning(f"Invalid key format: {key}")
                continue

            variables.append({
                "key": key,
                "value": str(value),
                "is_secret": self._is_secret(key)
            })

        return variables

    def _is_valid_key(self, key: str) -> bool:
        """
        Check if environment variable key is valid.

        Valid keys: alphanumeric + underscore, starting with letter or underscore
        """
        pattern = r'^[A-Za-z_][A-Za-z0-9_]*$'
        return bool(re.match(pattern, key))

    def _remove_quotes(self, value: str) -> str:
        """
        Remove surrounding quotes from value.

        Supports single quotes, double quotes, and backticks.
        """
        # Remove double quotes
        if value.startswith('"') and value.endswith('"') and len(value) >= 2:
            return value[1:-1]

        # Remove single quotes
        if value.startswith("'") and value.endswith("'") and len(value) >= 2:
            return value[1:-1]

        # Remove backticks
        if value.startswith("`") and value.endswith("`") and len(value) >= 2:
            return value[1:-1]

        return value

    def _is_secret(self, key: str) -> bool:
        """
        Check if environment variable name suggests it's a secret.

        Args:
            key: Environment variable name

        Returns:
            True if likely a secret, False otherwise
        """
        key_upper = key.upper()

        # Check against all secret patterns
        for pattern in self.SECRET_PATTERNS:
            if re.match(pattern, key_upper):
                return True

        return False

    def validate_env_file(self, content: str) -> Dict:
        """
        Validate .env file content and return statistics.

        Args:
            content: .env file content

        Returns:
            Dict with validation results and statistics
        """
        lines = content.split('\n')
        total_lines = len(lines)
        valid_lines = 0
        invalid_lines = 0
        comment_lines = 0
        empty_lines = 0

        for line in lines:
            line = line.strip()

            if not line:
                empty_lines += 1
            elif line.startswith('#'):
                comment_lines += 1
            elif '=' in line:
                key = line.split('=', 1)[0].strip()
                if self._is_valid_key(key):
                    valid_lines += 1
                else:
                    invalid_lines += 1
            else:
                invalid_lines += 1

        return {
            "total_lines": total_lines,
            "valid_variables": valid_lines,
            "invalid_lines": invalid_lines,
            "comment_lines": comment_lines,
            "empty_lines": empty_lines,
            "is_valid": invalid_lines == 0
        }
