"""Unit tests for the Source abstraction - the IO-agnostic input seam."""

from pathlib import Path

import pytest

from logreducer import FileSource, LogReducer, Source


def test_list_is_a_source():
    """A plain list of str satisfies the Source protocol (re-iterable)."""
    assert isinstance(["a", "b", "c"], Source)


def test_reduce_in_memory_list():
    """reduce() works on an in-memory list - no file, no IO of any kind."""
    reducer = LogReducer(level="standard", mode="pattern")
    source = [f"ERROR request {i} failed timeout" for i in range(200)]
    result = reducer.reduce(source)
    assert isinstance(result, list)
    assert 0 < len(result) < len(source)
    assert all(isinstance(line, str) for line in result)


def test_reduce_list_stats_have_no_file_size():
    """Non-file sources report input_lines but no byte size / rate."""
    reducer = LogReducer(level="standard", mode="pattern")
    reducer.reduce(["one", "two", "three", "one", "two"])
    stats = reducer.stats
    assert stats["input_lines"] == 5
    assert stats["input_size_mb"] is None
    assert stats["processing_rate_mb_per_sec"] is None


def test_reduce_return_metadata_dict():
    reducer = LogReducer(level="standard", mode="pattern")
    out = reducer.reduce(["x", "y", "x"], return_metadata=True)
    assert isinstance(out, dict)
    assert set(out) == {"lines", "stats", "config"}


def test_filesource_is_reiterable(small_log_file, sample_log_lines):
    """FileSource yields the same lines on every pass (it re-opens the file)."""
    source = FileSource(str(small_log_file))
    first = list(source)
    second = list(source)
    assert first == second
    assert first == [line.strip() for line in sample_log_lines]


def test_filesource_size_bytes(small_log_file):
    source = FileSource(str(small_log_file))
    assert source.size_bytes == Path(small_log_file).stat().st_size


def test_filesource_size_bytes_missing(tmp_path):
    source = FileSource(str(tmp_path / "does-not-exist.log"))
    assert source.size_bytes is None


def test_reduce_rejects_one_shot_generator():
    """A bare generator is one-shot; the count pass would drain it - reject it."""
    reducer = LogReducer(level="standard", mode="pattern")
    generator = (line for line in ["a", "b", "c"])
    with pytest.raises(TypeError, match="re-iterable"):
        reducer.reduce(generator)
