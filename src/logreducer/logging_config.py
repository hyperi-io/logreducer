"""Logging configuration for LogReducer.

Output follows one strict standard so logreducer's logs sit uniformly beside a
host application's logs in a shared deployment: RFC 3339 timestamps, a
``time | LEVEL | name:function:line - message`` layout, ASCII-only in files,
solarized colours in an interactive terminal, a plain prefix in CI, and one
JSON object per line when ``LOG_FORMAT=json``.

logreducer is a library, not a service, so it only ever manages its OWN loguru
handlers (filtered to ``logreducer`` records) and never removes a host
application's handlers - embedding logreducer inside another application must
not disturb that application's logging.

ENV overrides:
    LOG_LEVEL=DEBUG
    LOG_FORMAT=json|text
    LOG_OUTPUT=stdout|stderr
"""

import contextlib
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from loguru import Logger

# Solarized palette (https://ethanschoonover.com/solarized/) for the console
# sink - readable on both light and dark terminal backgrounds.
SOLARIZED = {
    "base01": "#586e75",
    "green": "#859900",
    "cyan": "#2aa198",
    "blue": "#268bd2",
    "yellow": "#b58900",
    "orange": "#cb4b16",
    "red": "#dc322f",
}

# Handler ids this module has registered, so re-configuring only tears down our
# own sinks - never the host application's.
_HANDLER_IDS: list[int] = []


def _is_ci() -> bool:
    """True in a CI environment (colours off, plain prefix format)."""
    return (
        os.getenv("CI") == "true"
        or os.getenv("GITHUB_ACTIONS") == "true"
        or os.getenv("GITLAB_CI") == "true"
        or os.getenv("JENKINS_URL") is not None
    )


def _is_interactive() -> bool:
    """True only for an interactive UTF-8 terminal (never a pipe/container)."""
    if _is_ci() or not sys.stderr.isatty():
        return False
    term = os.getenv("TERM", "")
    if not term or term == "dumb":
        return False
    locale = (os.getenv("LC_ALL") or os.getenv("LANG") or "").upper()
    return "UTF-8" in locale or "UTF8" in locale


def _console_format(colorize: bool, ci: bool) -> str:
    """Console format string - solarized colours, or a plain CI prefix."""
    if ci or not colorize:
        return "[{level: <8}] {name}:{function}:{line} - {message}"
    return (
        f"<fg {SOLARIZED['green']}>{{time:YYYY-MM-DDTHH:mm:ss.SSSZZ}}</fg {SOLARIZED['green']}> | "
        f"<level>{{level: <8}}</level> | "
        f"<fg {SOLARIZED['cyan']}>{{name}}</fg {SOLARIZED['cyan']}>:"
        f"<fg {SOLARIZED['cyan']}>{{function}}</fg {SOLARIZED['cyan']}>:"
        f"<fg {SOLARIZED['cyan']}>{{line}}</fg {SOLARIZED['cyan']}> - "
        f"<level>{{message}}</level>"
    )


def _file_format() -> str:
    """File format string - ASCII only, RFC 3339 timestamp with bracketed level."""
    return "{time:YYYY-MM-DDTHH:mm:ss.SSSZZ} [{level: <8}] {name}:{function}:{line} - {message}"


def _apply_solarized_levels() -> None:
    """Colour the loguru levels with the solarized scheme."""
    logger.level("TRACE", color=f"<fg {SOLARIZED['base01']}>")
    logger.level("DEBUG", color=f"<fg {SOLARIZED['base01']}>")
    logger.level("INFO", color=f"<fg {SOLARIZED['blue']}>")
    logger.level("SUCCESS", color=f"<fg {SOLARIZED['green']}>")
    logger.level("WARNING", color=f"<fg {SOLARIZED['yellow']}>")
    logger.level("ERROR", color=f"<fg {SOLARIZED['orange']}>")
    logger.level("CRITICAL", color=f"<fg {SOLARIZED['red']}>")


def setup_logging(
    enable: bool = False,
    log_file: str | None = None,
    log_level: str = "INFO",
    log_format: str = "text",
    console: bool = False,
) -> None:
    """Configure logreducer's own logging sinks.

    Args:
        enable: Whether logreducer emits logs at all (default False).
        log_file: Optional path for an ASCII, rotating file sink.
        log_level: Threshold level (overridden by ``LOG_LEVEL``).
        log_format: ``text`` (human) or ``json`` (overridden by ``LOG_FORMAT``).
        console: Also log to the console (stderr, or ``LOG_OUTPUT=stdout``).
    """
    # Env beats caller, so a deployment can retune logging without code changes.
    log_level = os.environ.get("LOG_LEVEL", log_level).upper()
    fmt_selector = (os.environ.get("LOG_FORMAT") or log_format or "text").strip().lower()
    serialize = fmt_selector == "json"

    # Tear down ONLY our previously registered handlers.
    global _HANDLER_IDS
    for handler_id in _HANDLER_IDS:
        try:
            logger.remove(handler_id)
        except ValueError:
            pass
    _HANDLER_IDS = []

    if not enable:
        logger.disable("logreducer")
        return

    ci = _is_ci()
    stream = sys.stdout if os.environ.get("LOG_OUTPUT") == "stdout" else sys.stderr

    if console:
        # CLI/app mode owns the console: drop loguru's default stderr handler
        # (id 0) so our formatted line is not printed twice. Only the pristine
        # default is removed - a host app's own handlers (ids > 0) are untouched
        # (embedding logreducer only ever goes through the console=False path).
        with contextlib.suppress(ValueError):
            logger.remove(0)
        colorize = not serialize and not ci and _is_interactive()
        if colorize:
            _apply_solarized_levels()
        _HANDLER_IDS.append(
            logger.add(
                stream,
                level=log_level,
                format=_console_format(colorize, ci),
                colorize=colorize,
                serialize=serialize,
                filter="logreducer",
            )
        )

    if log_file:
        try:
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)
            _HANDLER_IDS.append(
                logger.add(
                    log_file,
                    level=log_level,
                    format=_file_format(),
                    rotation="10 MB",
                    retention="7 days",
                    encoding="utf-8",
                    serialize=serialize,
                    filter="logreducer",
                )
            )
        except OSError as exc:
            # A bad log path should never take the process down.
            logger.warning(f"Could not create log file {log_file}: {exc}")

    logger.enable("logreducer")


def get_logger(name: str = "logreducer") -> "Logger":
    """Return a logger bound for the given logreducer submodule name."""
    return logger.bind(name=name)
