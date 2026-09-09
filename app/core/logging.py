"""
Application logging configuration.

This module provides a single get_logger function so every part of the
application logs consistently, without each module configuring its own
handlers.
"""

import logging
import os

_CONFIGURED = False


def _configure_root_logger() -> None:
    """Configure the root logger once, based on the LOG_LEVEL env var."""
    global _CONFIGURED

    if _CONFIGURED:
        return

    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """
    Get a configured logger for the given module name.

    Args:
        name: Usually __name__ of the calling module.

    Returns:
        A logger instance sharing the application's root configuration.
    """
    _configure_root_logger()
    return logging.getLogger(name)
