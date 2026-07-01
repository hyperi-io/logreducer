"""Unit tests for the typer CLI (entry point ``logreducer.cli:main``).

Drives the real console-script entry point with a patched argv, so the typer
wiring, source dispatch, and error paths are all exercised.
"""

import json
import sys

import pytest

from logreducer import cli


def _run_cli(monkeypatch, argv: list[str]) -> int:
    """Invoke the CLI as if from the shell; return its exit code."""
    monkeypatch.setattr(sys, "argv", ["logreducer", *argv])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    code = exc.value.code
    return 0 if code is None else int(code)


def test_cli_version(monkeypatch, capsys):
    assert _run_cli(monkeypatch, ["--version"]) == 0
    assert "logreducer version" in capsys.readouterr().out


def test_cli_reduce_file(monkeypatch, capsys, small_log_file):
    assert _run_cli(monkeypatch, [str(small_log_file)]) == 0
    assert capsys.readouterr().out.strip()  # produced reduced lines


def test_cli_reduce_to_output_file(monkeypatch, small_log_file, tmp_path):
    out_file = tmp_path / "reduced.log"
    assert _run_cli(monkeypatch, [str(small_log_file), "-o", str(out_file)]) == 0
    assert out_file.exists()
    assert out_file.read_text().strip()


def test_cli_stats(monkeypatch, capsys, small_log_file):
    assert _run_cli(monkeypatch, [str(small_log_file), "--stats"]) == 0
    err = capsys.readouterr().err
    assert "Reduction:" in err


def test_cli_metadata_json_emits_valid_json(monkeypatch, capsys, small_log_file):
    """--metadata --format json prints parseable JSON to stdout.

    Regression: the config dict held OutputFormat enum members, so json.dumps
    of the metadata result raised TypeError after all the processing work.
    """
    assert _run_cli(monkeypatch, [str(small_log_file), "--metadata", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert set(payload) == {"lines", "stats", "config"}
    # Enum config values are serialised to their string .value, not a repr.
    assert payload["config"]["output_format"] == "json"


def test_cli_estimate_prints_to_stdout(monkeypatch, capsys, small_log_file):
    """--estimate is the command's product and must reach stdout.

    Regression: the estimate went through the library logger, which is disabled
    unless --log is passed, so the installed entry point printed nothing.
    """
    assert _run_cli(monkeypatch, [str(small_log_file), "--estimate"]) == 0
    out = capsys.readouterr().out
    assert "Processing strategy:" in out
    assert "Expected output lines:" in out


def test_cli_missing_input_errors(monkeypatch):
    assert _run_cli(monkeypatch, []) != 0


def test_cli_dsn_requires_query(monkeypatch):
    assert _run_cli(monkeypatch, ["--dsn", "postgresql://user@host/db"]) != 0


def test_cli_kafka_dsn_requires_topic_group(monkeypatch):
    assert _run_cli(monkeypatch, ["--dsn", "kafka://broker:9092"]) != 0


def test_cli_sqlite_dsn_end_to_end(monkeypatch, capsys, tmp_path):
    pytest.importorskip("sqlalchemy")
    from sqlalchemy import create_engine, text

    url = f"sqlite:///{tmp_path / 'logs.db'}"
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE logs (line TEXT)"))
        conn.execute(
            text("INSERT INTO logs (line) VALUES (:l)"),
            [{"l": f"ERROR request failed shard={i % 3}"} for i in range(30)],
        )
    engine.dispose()

    assert _run_cli(monkeypatch, ["--dsn", url, "--query", "SELECT line FROM logs"]) == 0
    assert capsys.readouterr().out.strip()
