#!/usr/bin/env python3
"""
Common utilities for Python project scripts
Provides centralized logging, configuration, and version management
"""

import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import yaml
from dynaconf import Dynaconf
from loguru import logger

# Project root detection
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Virtual environment paths
VENV_PATH = PROJECT_ROOT / ".venv"
VENV_PYTHON = VENV_PATH / "bin" / "python"
VENV_ACTIVATE = VENV_PATH / "bin" / "activate"


def setup_logging(
    level: str = "INFO",
    format_template: str | None = None,
    enable_console: bool = True,
    enable_file: bool = True,
    log_file: str | None = None,
) -> None:
    """
    Configure loguru logging with RFC 3339 timestamps (tee approach)
    Logs to both console and file by default with switches to disable either

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_template: Custom format template
        enable_console: Enable console output (default: True)
        enable_file: Enable file output (default: True)
        log_file: Log file path (default: .tmp/logs/script.log)
    """
    # Remove default handler to avoid duplicates
    logger.remove()

    # Default format with RFC 3339 timestamp
    if format_template is None:
        format_template = (
            "<green>{time:YYYY-MM-DDTHH:mm:ss.SSSZ}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        )

    # Add console handler if enabled
    if enable_console:
        logger.add(
            sys.stderr,
            format=format_template,
            level=level,
            colorize=True,
            backtrace=True,
            diagnose=True,
        )

    # Add file handler if enabled
    if enable_file:
        if log_file is None:
            log_dir = PROJECT_ROOT / ".tmp" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "script.log"

        logger.add(
            str(log_file),
            format=format_template,
            level=level,
            rotation="10 MB",
            retention="7 days",
            compression="gz",
            backtrace=True,
            diagnose=True,
        )

    logger.info(f"Logger initialized at {level} level (console={enable_console}, file={enable_file})")


def setup_config(config_file: str | None = None, env_prefix: str = "APP", **kwargs) -> Dynaconf:
    """
    Setup configuration with proper precedence:
    1. config.yaml (lowest priority)
    2. Environment variables with APP_ prefix
    3. CLI arguments passed as kwargs (highest priority)

    Args:
        config_file: Path to config file (default: config.yaml in project root)
        env_prefix: Environment variable prefix (default: APP)
        **kwargs: CLI arguments that override everything

    Returns:
        Configured Dynaconf instance
    """
    if config_file is None:
        config_file = PROJECT_ROOT / "config.yaml"

    # Create default config if it doesn't exist
    if not Path(config_file).exists():
        logger.info(f"Creating default config at {config_file}")
        create_default_config(config_file)

    # Configure dynaconf with proper precedence
    config = Dynaconf(
        settings_files=[str(config_file)],  # Base configuration file
        environments=True,  # Support environment-specific configs
        env_prefix=env_prefix,  # Environment variable prefix
        load_dotenv=True,  # Load .env files
        merge_enabled=True,  # Merge configurations
        **kwargs,  # CLI overrides
    )

    logger.info(f"Configuration loaded from {config_file}")
    logger.debug(f"Environment prefix: {env_prefix}")

    return config


def load_pdev_config():
    """Load configuration from pdev.yaml"""
    pdev_config_file = PROJECT_ROOT / "scripts" / "pdev.yaml"

    if pdev_config_file.exists():
        try:
            import yaml

            with open(pdev_config_file) as f:
                pdev_config = yaml.safe_load(f)
                return pdev_config.get("config", {})
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"Could not load pdev config: {e}")

    # Fallback minimal config
    return {
        "logging": {"level": "INFO", "format": "rfc3339", "enable_console": True, "enable_file": True},
        "dev": {"parallel_jobs": 4, "verbose": True},
        "paths": {"venv": ".venv", "tmp": ".tmp", "logs": ".tmp/logs"},
    }


def create_default_config(config_file: str) -> None:
    """Create a default configuration file from pdev.yaml template"""
    pdev_config = load_pdev_config()

    # Convert the config section to YAML for the default config file
    default_config = """# LogReducer Configuration
# This file provides base configuration that can be overridden by:
# 1. Environment variables with APP_ prefix (e.g., APP_LOG_LEVEL=DEBUG)
# 2. CLI arguments

# Configuration loaded from pdev.yaml - edit scripts/pdev.yaml to change defaults
"""

    try:
        import yaml

        default_config += yaml.dump(pdev_config, default_flow_style=False)
    except ImportError:
        # Minimal fallback if PyYAML not available
        default_config += """
log_level: INFO
dev:
  parallel_jobs: 4
paths:
  venv: ".venv"
  tmp: ".tmp"
"""

    Path(config_file).write_text(default_config)
    logger.info(f"Created default configuration at {config_file}")


def log_config_info(config: Dynaconf) -> None:
    """Log configuration information for debugging"""
    logger.debug("Configuration summary:")
    logger.debug(f"  Log level: {config.get('log_level', 'INFO')}")
    logger.debug(f"  Config sources: {config._loaded_files}")

    # Log environment variables that are being used
    import os

    env_vars = {k: v for k, v in os.environ.items() if k.startswith("APP_")}
    if env_vars:
        logger.debug(f"  Active environment variables: {list(env_vars.keys())}")
    else:
        logger.debug("  No APP_ environment variables found")


def get_project_path(relative_path: str) -> Path:
    """Get absolute path relative to project root"""
    return PROJECT_ROOT / relative_path


def ensure_venv_python() -> Path:
    """Get path to Python executable in virtual environment"""
    venv_python = PROJECT_ROOT / ".venv" / "bin" / "python"
    if not venv_python.exists():
        logger.error("Virtual environment not found. Run: scripts/setup")
        sys.exit(1)
    return venv_python


# Example usage functions
def run_command(cmd, check=True, capture_output=False, **kwargs):
    """
    Run a command with consistent error handling

    Args:
        cmd: Command as list of strings
        check: Raise exception on non-zero exit
        capture_output: Capture stdout/stderr
        **kwargs: Additional arguments for subprocess.run

    Returns:
        subprocess.CompletedProcess
    """
    try:
        return subprocess.run(cmd, check=check, capture_output=capture_output, **kwargs)
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {' '.join(cmd)}")
        logger.error(f"Exit code: {e.returncode}")
        if e.stderr:
            logger.error(f"Error: {e.stderr.decode() if isinstance(e.stderr, bytes) else e.stderr}")
        raise
    except FileNotFoundError:
        logger.error(f"Command not found: {cmd[0]}")
        raise


def get_project_version():
    """
    Get current project version from pyproject.toml

    Returns:
        Version string or None if not found
    """
    pyproject_file = PROJECT_ROOT / "pyproject.toml"
    if pyproject_file.exists():
        content = pyproject_file.read_text()
        match = re.search(r'^\[project\].*?^version = "(.*?)"', content, re.MULTILINE | re.DOTALL)
        if match:
            return match.group(1)
    return None


def get_package_name():
    """
    Get package name from pyproject.toml

    Returns:
        Package name or None if not found
    """
    pyproject_file = PROJECT_ROOT / "pyproject.toml"
    if pyproject_file.exists():
        content = pyproject_file.read_text()
        match = re.search(r'^\[project\].*?^name = "(.*?)"', content, re.MULTILINE | re.DOTALL)
        if match:
            return match.group(1)
    return None


def get_python_version():
    """
    Get required Python version from .python-version file
    Falls back to config floor if not found

    Returns:
        Python version string or None if not configured
    """
    version_file = PROJECT_ROOT / ".python-version"
    if version_file.exists():
        return version_file.read_text().strip()

    # Fall back to floor version from config
    config_file = SCRIPT_DIR / "pdev.yaml"
    config = load_yaml_config(config_file)
    floor = config.get("base", {}).get("python_version_floor")
    return floor


def load_yaml_config(config_file: Path) -> dict[str, Any]:
    """
    Load YAML configuration file

    Args:
        config_file: Path to YAML file

    Returns:
        Parsed configuration dictionary
    """
    if config_file.exists():
        with open(config_file) as f:
            return yaml.safe_load(f) or {}
    return {}


def check_git_repo() -> bool:
    """
    Check if current directory is a git repository

    Returns:
        True if in a git repo, False otherwise
    """
    try:
        subprocess.run(["git", "rev-parse", "--git-dir"], capture_output=True, check=True, cwd=PROJECT_ROOT)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def get_git_tags():
    """
    Get list of git tags

    Returns:
        List of tag names
    """
    try:
        result = subprocess.run(["git", "tag", "-l"], capture_output=True, text=True, check=True, cwd=PROJECT_ROOT)
        return [t for t in result.stdout.strip().split("\n") if t]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def init_script(
    script_name: str,
    config_file: str | None = None,
    log_level: str | None = None,
    **cli_args,
) -> tuple[Dynaconf, Any]:
    """
    Initialize a script with logging and configuration

    Args:
        script_name: Name of the script for logging context
        config_file: Optional config file path
        log_level: Optional log level override
        **cli_args: CLI arguments to merge into config

    Returns:
        Tuple of (config, logger) ready to use
    """
    # Setup configuration first
    config = setup_config(config_file=config_file, **cli_args)

    # Override log level if provided
    if log_level:
        config.log_level = log_level

    # Setup logging with config values (tee approach by default)
    setup_logging(
        level=config.get("log_level", "INFO"),
        format_template=(None if config.get("log_format") == "rfc3339" else config.get("log_format")),
        enable_console=config.get("enable_console_log", True),
        enable_file=config.get("enable_file_log", True),
        log_file=config.get("log_file"),
    )

    # Configure logger for this script
    script_logger = logger.bind(script=script_name)
    script_logger.info(f"Starting {script_name}")

    # Log configuration info in debug mode
    if config.get("log_level") == "DEBUG":
        log_config_info(config)

    return config, script_logger


# Kubernetes/Docker configuration helpers
def load_k8s_config() -> dict[str, Any]:
    """Load configuration from Kubernetes ConfigMap/Secret pattern"""
    k8s_config = {}

    # Check for mounted config file
    k8s_config_path = Path("/app/config.yaml")
    if k8s_config_path.exists():
        logger.info("Found Kubernetes config at /app/config.yaml")
        return {"config_file": str(k8s_config_path)}

    # Check for common K8s patterns
    config_dir = Path("/app/config")
    if config_dir.exists():
        logger.info(f"Found config directory at {config_dir}")
        config_files = list(config_dir.glob("*.yaml")) + list(config_dir.glob("*.yml"))
        if config_files:
            k8s_config["config_file"] = str(config_files[0])

    return k8s_config
