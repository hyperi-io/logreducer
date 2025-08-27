"""
Logging configuration for LogReducer
"""

import sys
from pathlib import Path
from typing import Optional

from loguru import logger


def setup_logging(
    enable: bool = False,
    log_file: Optional[str] = None,
    log_level: str = "INFO",
    log_format: str = "rfc3339",
    console: bool = False,
) -> None:
    """
    Configure logging for LogReducer.

    Args:
        enable: Whether to enable logging (default False)
        log_file: Path to log file (None = no file logging)
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_format: Format style ('rfc3339' or 'simple')
        console: Whether to also log to console/stderr (default False)
    """
    # Remove all existing handlers
    logger.remove()

    if not enable:
        # Logging disabled - add null handler
        logger.disable("logreducer")
        return

    # Select format based on preference
    if log_format == "rfc3339":
        fmt = "<green>{time:YYYY-MM-DDTHH:mm:ss.SSSZ}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
        file_fmt = "{time:YYYY-MM-DDTHH:mm:ss.SSSZ} | {level: <8} | {name}:{function}:{line} - {message}"
    else:
        fmt = "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"
        file_fmt = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}"

    # Add stderr handler for console output (only if console=True)
    if console:
        logger.add(sys.stderr, format=fmt, level=log_level, filter="logreducer")

    # Add file handler if specified
    if log_file:
        try:
            # Create parent directory if needed
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            logger.add(
                log_file,
                format=file_fmt,
                level=log_level,
                rotation="1 day",
                retention="7 days",
                compression="gz",
                filter="logreducer",
            )
        except Exception as e:
            # Don't fail if we can't create log file
            logger.warning(f"Could not create log file {log_file}: {e}")

    logger.enable("logreducer")


def get_logger(name: str = "logreducer"):
    """
    Get a logger instance.

    Args:
        name: Logger name (usually module name)

    Returns:
        Logger instance
    """
    return logger.bind(name=f"logreducer.{name}")
