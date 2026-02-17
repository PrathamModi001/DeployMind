"""Structured JSON logging setup for DeployMind."""

import logging
import sys

from pythonjsonlogger.json import JsonFormatter as _JsonFormatter


def get_logger(name: str, level: str = "INFO") -> logging.Logger:
    """Create a structured JSON logger.

    Args:
        name: Logger name (typically __name__).
        level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = _JsonFormatter(
            fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    return logger
