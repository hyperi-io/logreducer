"""Logging configuration for LogReducer, on the standard library ``logging``.

Output follows one strict standard so logreducer's logs sit uniformly beside a
host application's logs in a shared deployment: RFC 3339 timestamps, a
``time | LEVEL | name:function:line - message`` layout, ASCII-only in files,
solarized colours in an interactive terminal, a plain prefix in CI, and one
JSON object per line when ``LOG_FORMAT=json``.

logreducer is a library, not a service, so it only ever attaches handlers to its
OWN ``logreducer`` logger and never touches the root logger or a host
application's handlers - embedding logreducer inside another application must
not disturb that application's logging.

ENV overrides:
    LOG_LEVEL=DEBUG
    LOG_FORMAT=json|text
    LOG_OUTPUT=stdout|stderr
"""

import json
import logging
import logging.handlers
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

PACKAGE_LOGGER_NAME = "logreducer"

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

_LEVEL_COLOURS = {
    logging.DEBUG: SOLARIZED["base01"],
    logging.INFO: SOLARIZED["blue"],
    logging.WARNING: SOLARIZED["yellow"],
    logging.ERROR: SOLARIZED["orange"],
    logging.CRITICAL: SOLARIZED["red"],
}

# Above CRITICAL, so a disabled logreducer emits nothing, not even through a host's handlers.
_DISABLED_LEVEL = logging.CRITICAL + 1

# Rotate the file sink at 10 MB and keep seven rotated files.
_FILE_MAX_BYTES = 10 * 1024 * 1024
_FILE_BACKUPS = 7

# Every attribute a bare LogRecord carries; anything else came from the caller's ``extra=``.
_STANDARD_RECORD_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}

# Handlers this module has attached, so re-configuring only tears down our own
# sinks - never the host application's.
_HANDLERS: list[logging.Handler] = []

logger = logging.getLogger(__name__)


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


def _paint(text: str, hex_colour: str) -> str:
    """Wrap ``text`` in a 24-bit ANSI foreground colour."""
    red, green, blue = (int(hex_colour[i : i + 2], 16) for i in (1, 3, 5))
    return f"\x1b[38;2;{red};{green};{blue}m{text}\x1b[0m"


def _local_rfc3339(created: float) -> str:
    """RFC 3339 local time with milliseconds and the UTC offset."""
    return datetime.fromtimestamp(created).astimezone().isoformat(timespec="milliseconds")


class _LineFormatter(logging.Formatter):
    """Render ``[time] LEVEL name:function:line - message`` on one line (plus any traceback)."""

    def __init__(self, *, with_time: bool, colour: bool, ascii_only: bool) -> None:
        super().__init__()
        self._with_time = with_time
        self._colour = colour
        self._ascii_only = ascii_only

    def format(self, record: logging.LogRecord) -> str:
        """Render one record."""
        level = f"{record.levelname:<8}"
        where = f"{record.name}:{record.funcName}:{record.lineno}"
        message = record.getMessage()
        if record.exc_info:
            message = f"{message}\n{self.formatException(record.exc_info)}"

        if self._colour:
            level_colour = _LEVEL_COLOURS.get(record.levelno, SOLARIZED["blue"])
            line = (
                f"{_paint(_local_rfc3339(record.created), SOLARIZED['green'])} | "
                f"{_paint(level, level_colour)} | {_paint(where, SOLARIZED['cyan'])} - {_paint(message, level_colour)}"
            )
        elif self._with_time:
            line = f"{_local_rfc3339(record.created)} [{level}] {where} - {message}"
        else:
            line = f"[{level}] {where} - {message}"

        if self._ascii_only:
            return line.encode("ascii", "backslashreplace").decode("ascii")
        return line


class _JsonFormatter(logging.Formatter):
    """Render one flat JSON object per record, keyed like scalo's JSON log lines."""

    def format(self, record: logging.LogRecord) -> str:
        """Render one record."""
        timestamp = datetime.fromtimestamp(record.created, UTC).isoformat(timespec="microseconds")
        entry: dict[str, object] = {
            "timestamp": timestamp.replace("+00:00", "Z"),
            "level": record.levelname,
            "target": record.name,
            "function": record.funcName,
            "line_number": record.lineno,
            "message": record.getMessage(),
            "fields": {key: value for key, value in record.__dict__.items() if key not in _STANDARD_RECORD_ATTRS},
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str, ensure_ascii=True)


def _attach(package_logger: logging.Logger, handler: logging.Handler, formatter: logging.Formatter) -> None:
    handler.setFormatter(formatter)
    package_logger.addHandler(handler)
    _HANDLERS.append(handler)


def setup_logging(
    enable: bool = False,
    log_file: str | None = None,
    log_level: str = "INFO",
    log_format: str = "text",
    console: bool = False,
    own_sinks: bool = True,
) -> None:
    """Configure logreducer's own logging sinks.

    Records always propagate to the host application's handlers as well, so a
    host that has configured the root logger sees logreducer's records there.

    Args:
        enable: Whether logreducer emits logs at all (default False).
        log_file: Optional path for an ASCII file sink that rotates at 10 MB
            and keeps seven rotated files.
        log_level: Threshold level (overridden by ``LOG_LEVEL``).
        log_format: ``text`` (human) or ``json`` (overridden by ``LOG_FORMAT``).
        console: Also log to the console (stderr, or ``LOG_OUTPUT=stdout``).
        own_sinks: When False, attach NO handlers and leave the threshold to the
            host - logreducer's records flow to the HOST application's handlers
            at the host's level. This is the embedding seam: a host app that owns
            logging calls ``setup_logging(enable=True, own_sinks=False)`` and
            logreducer's output lands in the host's sinks, formatted by the
            host's standard.

    Raises:
        ValueError: If the resolved level is not a ``logging`` level name.
    """
    # Env beats caller, so a deployment can retune logging without code changes.
    log_level = os.environ.get("LOG_LEVEL", log_level).upper()
    fmt_selector = (os.environ.get("LOG_FORMAT") or log_format or "text").strip().lower()
    serialize = fmt_selector == "json"

    # Tear down ONLY our previously attached handlers.
    package_logger = logging.getLogger(PACKAGE_LOGGER_NAME)
    for handler in _HANDLERS:
        package_logger.removeHandler(handler)
        handler.close()
    _HANDLERS.clear()

    if not enable:
        package_logger.setLevel(_DISABLED_LEVEL)
        return

    if not own_sinks:
        package_logger.setLevel(logging.NOTSET)
        return

    package_logger.setLevel(log_level)
    ci = _is_ci()

    if console:
        stream = sys.stdout if os.environ.get("LOG_OUTPUT") == "stdout" else sys.stderr
        colour = not serialize and not ci and _is_interactive()
        console_formatter = (
            _JsonFormatter() if serialize else _LineFormatter(with_time=colour, colour=colour, ascii_only=False)
        )
        _attach(package_logger, logging.StreamHandler(stream), console_formatter)

    if log_file:
        try:
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.handlers.RotatingFileHandler(
                log_file, maxBytes=_FILE_MAX_BYTES, backupCount=_FILE_BACKUPS, encoding="utf-8"
            )
        except OSError as exc:
            # A bad log path should never take the process down.
            logger.warning("Could not create log file %s: %s", log_file, exc)
        else:
            file_formatter = (
                _JsonFormatter() if serialize else _LineFormatter(with_time=True, colour=False, ascii_only=True)
            )
            _attach(package_logger, file_handler, file_formatter)


def get_logger(name: str = PACKAGE_LOGGER_NAME) -> logging.Logger:
    """Return the logger for a logreducer module name (``logreducer.<module>``)."""
    return logging.getLogger(name)
