"""Unit tests for the Sink abstraction - the IO-agnostic output seam."""

import json

import pytest

from logreducer import FileSink, LogReducer, Sink


def test_filesink_is_a_sink(tmp_path):
    assert isinstance(FileSink(str(tmp_path / "out.log")), Sink)


def test_filesink_line_format(tmp_path):
    path = tmp_path / "out.log"
    count = FileSink(str(path), output_format="line").write(["alpha", "beta", "gamma"])
    assert count == 3
    assert path.read_text().splitlines() == ["alpha", "beta", "gamma"]


def test_filesink_jsonl_format(tmp_path):
    path = tmp_path / "out.jsonl"
    count = FileSink(str(path), output_format="jsonl").write(["a", "b"])
    assert count == 2
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert rows == [{"line": "a"}, {"line": "b"}]


def test_filesink_json_format(tmp_path):
    path = tmp_path / "out.json"
    count = FileSink(str(path), output_format="json").write(["a", "b"])
    assert count == 2
    doc = json.loads(path.read_text())
    assert doc["lines"] == ["a", "b"]
    assert "timestamp" in doc


def test_filesink_rejects_unknown_format(tmp_path):
    with pytest.raises(ValueError):
        FileSink(str(tmp_path / "x"), output_format="xml")


def test_filesink_streams_a_generator(tmp_path):
    """write() consumes a generator lazily and still counts correctly."""
    path = tmp_path / "gen.log"
    count = FileSink(str(path)).write(f"line {i}" for i in range(5))
    assert count == 5
    assert path.read_text().splitlines()[-1] == "line 4"


def test_reduce_writes_to_sink(tmp_path):
    """reduce(sink=...) hands the reduced lines to the sink."""
    reducer = LogReducer(level="standard", mode="pattern")
    path = tmp_path / "reduced.log"
    sink = FileSink(str(path), output_format="line")
    result = reducer.reduce([f"ERROR x {i % 3}" for i in range(60)], sink=sink)
    assert path.read_text().splitlines() == result
