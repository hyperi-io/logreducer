"""Unit tests for logging configuration (the logreducer output standard).

Logs are filtered to ``logreducer`` records, so these drive logging through a
real reducer run (records originate in logreducer.core) rather than logging
from the test module directly.
"""

import json

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

    first_line = log_file.read_text().splitlines()[0]
    record = json.loads(first_line)  # loguru serialize=True -> one JSON object per line
    assert "record" in record


def test_disabled_logging_writes_nothing(tmp_path, small_log_file):
    log_file = tmp_path / "none.log"
    reducer = LogReducer(level="standard", enable_logging=False, log_file=str(log_file))
    reducer.process_file(str(small_log_file))
    assert not log_file.exists() or log_file.read_text() == ""
