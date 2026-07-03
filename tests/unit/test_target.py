"""Unit tests for reduce_to_target (real reducer, real sources - no mocks).

The fake sources here are genuine data sources (they implement the Source /
sample_batch contract), not mocks of internal code. Each template recurs (>=2
lines) so it survives the reducer's min-occurrence filter and yields examples.
"""

import pytest

from logreducer import LogReducer, reduce_to_target


class ManyTemplateSource:
    """A sampleable source with many distinct log shapes (-> many patterns).

    Two lines per template (differing in a trailing value) so each shape forms
    one Drain3 cluster with count >= 2 and survives the occurrence filter.
    """

    def __init__(self, n_templates: int = 40) -> None:
        self._lines = [f"ERRORTYPE{i} subsystem={i} failed code={v}" for i in range(n_templates) for v in (1, 2)]

    def __iter__(self):
        return iter(self._lines)

    def sample_batch(self, n: int) -> list[str]:
        return self._lines[:n]


class GrowingSource:
    """Each pull yields one brand-new (recurring) template, so reps keep growing."""

    def __init__(self) -> None:
        self.calls = 0

    def __iter__(self):
        return iter([])

    def sample_batch(self, n: int) -> list[str]:
        self.calls += 1
        k = self.calls
        return [f"KIND{k} distinct event value={v}" for v in range(3)]


class EmptySource:
    def __iter__(self):
        return iter([])

    def sample_batch(self, n: int) -> list[str]:
        return []


def _reducer() -> LogReducer:
    return LogReducer(level="standard", mode="pattern")


def test_reaches_target():
    source = ManyTemplateSource(n_templates=40)
    result = reduce_to_target(source, _reducer(), target_rows=10, max_fetches=5)
    assert result["stats"]["stop_reason"] == "target"
    assert len(result["lines"]) == 10
    assert result["stats"]["collected"] == 10


def test_stops_on_exhausted_source():
    result = reduce_to_target(EmptySource(), _reducer(), target_rows=100, max_fetches=5)
    assert result["stats"]["stop_reason"] == "exhausted"
    assert result["lines"] == []
    assert result["stats"]["fetches"] == 1


def test_stops_on_max_fetches():
    source = GrowingSource()
    result = reduce_to_target(source, _reducer(), target_rows=10_000, max_fetches=3, plateau_rounds=100)
    assert result["stats"]["stop_reason"] == "max_fetches"
    assert result["stats"]["fetches"] == 3
    assert 0 < len(result["lines"]) < 10_000


def test_stops_on_plateau():
    # A fixed small set of templates: after the first pull, no new representatives.
    source = ManyTemplateSource(n_templates=5)
    result = reduce_to_target(source, _reducer(), target_rows=10_000, max_fetches=50, plateau_rounds=2)
    assert result["stats"]["stop_reason"] == "plateau"
    assert 0 < len(result["lines"]) < 10_000


def test_list_source_fallback_reservoir():
    # A plain list has no sample_batch; the reservoir fallback still works.
    # 10 templates x 3 variants so each survives the occurrence filter.
    lines = [f"SHAPE{i} log variant value={v}" for i in range(10) for v in range(3)]
    result = reduce_to_target(lines, _reducer(), target_rows=5, max_fetches=5)
    assert result["stats"]["collected"] > 0
    assert result["stats"]["stop_reason"] in {"target", "plateau"}


def test_adaptive_batch_sizing_records_final_batch():
    source = ManyTemplateSource(n_templates=40)
    result = reduce_to_target(source, _reducer(), target_rows=10, max_fetches=5, max_batch_memory_gb=0.5)
    assert result["stats"]["final_batch_rows"] > 0


def test_invalid_target_raises():
    with pytest.raises(ValueError, match="target_rows"):
        reduce_to_target(EmptySource(), _reducer(), target_rows=0)


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"max_fetches": 0}, "max_fetches"),
        ({"batch_rows": 0}, "batch_rows"),
        ({"plateau_rounds": 0}, "plateau_rounds"),
    ],
)
def test_invalid_loop_params_raise(kwargs, match):
    with pytest.raises(ValueError, match=match):
        reduce_to_target(EmptySource(), _reducer(), target_rows=5, **kwargs)


def test_fixed_batch_rows_disables_adaptive_sizing():
    source = ManyTemplateSource(n_templates=40)
    result = reduce_to_target(
        source, _reducer(), target_rows=10, max_fetches=5, batch_rows=123, max_batch_memory_gb=0.5
    )
    # batch_rows pins the batch size; the adaptive sizer must not change it.
    assert result["stats"]["final_batch_rows"] == 123


def test_seed_makes_reservoir_fallback_deterministic():
    # A plain list uses the client-side reservoir; the same seed must pull the
    # same batches and therefore collect the same representatives.
    lines = [f"SHAPE{i} log variant value={v}" for i in range(40) for v in range(3)]
    a = reduce_to_target(lines, _reducer(), target_rows=8, max_fetches=3, batch_rows=50, seed=7)
    b = reduce_to_target(lines, _reducer(), target_rows=8, max_fetches=3, batch_rows=50, seed=7)
    assert a["lines"] == b["lines"]
