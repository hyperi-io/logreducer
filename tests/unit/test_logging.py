"""Unit tests for logging configuration (the logreducer output standard).

Logs are filtered to ``logreducer`` records, so these drive logging through a
real reducer run (records originate in logreducer.core) rather than logging
from the test module directly.
"""

import json
import logging
from datetime import datetime

import pytest

from logreducer import LogReducer
from logreducer.logging_config import setup_logging


@pytest.fixture(autouse=True)
def _teardown_logging():
    # Tear down our own handlers after each test (also flushes the file sink).
    yield
    setup_logging(enable=False)


def test_reducer_writes_formatted_log_file(tmp_path, small_log_file):
    log_file = tmp_path / "run.log"
    reducer = LogReducer(level="standard", enable_logging=True, log_file=str(log_file), log_level="DEBUG")
    reducer.process_file(str(small_log_file))
    setup_logging(enable=False)  # remove the file handler to flush

    content = log_file.read_text()
    assert content.strip()
    assert "logreducer.core" in content  # name:function:line layout


def test_json_log_format(tmp_path, small_log_file, monkeypatch):
    monkeypatch.setenv("LOG_FORMAT", "json")
    log_file = tmp_path / "run.jsonl"
    reducer = LogReducer(level="standard", enable_logging=True, log_file=str(log_file), log_level="INFO")
    reducer.process_file(str(small_log_file))
    setup_logging(enable=False)

    lines = log_file.read_text().splitlines()
    records = [json.loads(line) for line in lines]  # one JSON object per line
    assert records
    first = records[0]
    assert set(first) >= {"timestamp", "level", "target", "function", "line_number", "message", "fields"}
    assert first["target"].startswith("logreducer.")
    assert first["timestamp"].endswith("Z")


def test_text_log_file_is_ascii_with_rfc3339_time(tmp_path, small_log_file):
    log_file = tmp_path / "run.log"
    reducer = LogReducer(level="standard", enable_logging=True, log_file=str(log_file), log_level="INFO")
    reducer.process_file(str(small_log_file))
    setup_logging(enable=False)

    first_line = log_file.read_text(encoding="utf-8").splitlines()[0]
    first_line.encode("ascii")  # raises if the file sink wrote a non-ASCII byte
    timestamp, rest = first_line.split(" ", 1)
    assert datetime.fromisoformat(timestamp).tzinfo is not None  # offset-aware RFC 3339
    assert rest.startswith("[INFO    ] logreducer.core:")


def test_file_sink_escapes_non_ascii(tmp_path):
    log_file = tmp_path / "unicode.log"
    setup_logging(enable=True, log_file=str(log_file), log_level="INFO")
    logging.getLogger("logreducer.test").info("caf" + chr(0xE9))
    setup_logging(enable=False)

    assert log_file.read_text(encoding="ascii").rstrip().endswith("caf\\xe9")


def test_disabled_logging_writes_nothing(tmp_path, small_log_file):
    log_file = tmp_path / "none.log"
    reducer = LogReducer(level="standard", enable_logging=False, log_file=str(log_file))
    reducer.process_file(str(small_log_file))
    assert not log_file.exists() or log_file.read_text() == ""
