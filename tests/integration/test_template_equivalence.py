"""Template mining reproduces the drain3 0.9.11 output it replaced, on real corpora.

``tests/testdata/template_mining_golden.json.gz`` holds what drain3 0.9.11
produced for the first ``limit`` lines of every committed corpus under each
miner configuration: the per-line cluster assignment (as a sha256 digest), the
number of live clusters, and the templates and counts ``extract_patterns``
returned, in order. Server-free; no mocks.
"""

import gzip
import hashlib
import json
from typing import Any

import pytest

from logreducer.config import BigDialConfig
from logreducer.patterns import PatternExtractor, is_severe
from tests.integration import corpora

pytestmark = pytest.mark.integration

GOLDEN_PATH = corpora.TESTDATA_DIR / "template_mining_golden.json.gz"
GOLDEN: dict[str, Any] = json.loads(gzip.decompress(GOLDEN_PATH.read_bytes()))
CASES = [(name, label) for name in GOLDEN["results"] for label in GOLDEN["configs"]]
# drain3 0.9.11 over each corpus's quiet lines alone, built by tests/testdata/build_quiet_golden.py.
QUIET_GOLDEN: dict[str, Any] = json.loads(
    gzip.decompress((corpora.TESTDATA_DIR / "template_mining_quiet_golden.json.gz").read_bytes())
)


def _config(label: str) -> BigDialConfig:
    # Keep every cluster, so the comparison covers the whole template set.
    return BigDialConfig(min_pattern_occurrences=1, max_patterns=10**9, **GOLDEN["configs"][label])


def test_golden_covers_every_corpus():
    assert sorted(GOLDEN["results"]) == sorted(corpora.dataset_names())
    assert sorted(QUIET_GOLDEN["results"]) == sorted(corpora.dataset_names())


def _drain3_per_class(label: str, lines: list[str]) -> list[tuple[list[list[Any]], int]]:
    """Drain3 alone (no severity split) over the non-severe and the severe lines separately.

    Returns, per class, the extracted [template, count] pairs and the live cluster count.
    """
    runs = []
    for severe in (False, True):
        extractor = PatternExtractor(_config(label))
        extractor.miner.drain.is_severe = None
        patterns = extractor.extract_patterns([line for line in lines if is_severe(line) is severe])
        runs.append(([[p.template, p.count] for p in patterns], len(extractor.miner.drain.id_to_cluster)))
    return runs


def _drain3_mixes_severity(label: str, lines: list[str]) -> bool:
    """True when Drain3 puts severe and non-severe lines of this corpus in one cluster."""
    extractor = PatternExtractor(_config(label))
    extractor.miner.drain.is_severe = None
    classes: dict[int, set[bool]] = {}
    for line in lines:
        classes.setdefault(extractor.miner.add_log_message(line).cluster_id, set()).add(is_severe(line))
    return any(len(severities) > 1 for severities in classes.values())


@pytest.mark.parametrize(("name", "label"), CASES)
def test_cluster_assignment_matches_drain3(name, label):
    """Same assignment as Drain3, except that a severe line never joins a non-severe cluster."""
    expected = GOLDEN["results"][name][label]
    lines = corpora.read_all(name, limit=GOLDEN["limit"])
    assert len(lines) == expected["lines"]

    miner = PatternExtractor(_config(label)).miner
    clusters = [miner.add_log_message(line) for line in lines]

    if not _drain3_mixes_severity(label, lines):
        ids = [cluster.cluster_id for cluster in clusters]
        assert hashlib.sha256(",".join(map(str, ids)).encode()).hexdigest() == expected["assignments_sha256"]
        assert len(miner.drain.id_to_cluster) == expected["live_clusters"]
        return

    assert all(cluster.severe == is_severe(line) for cluster, line in zip(clusters, lines, strict=True))
    assert len(miner.drain.id_to_cluster) == sum(live for _, live in _drain3_per_class(label, lines))
    assert len(miner.drain.id_to_cluster) > expected["live_clusters"]


@pytest.mark.parametrize(("name", "label"), CASES)
def test_extracted_patterns_match_drain3(name, label):
    """Same templates and counts as Drain3, except that severe lines form their own templates."""
    expected = GOLDEN["results"][name][label]
    lines = corpora.read_all(name, limit=GOLDEN["limit"])

    patterns = [[p.template, p.count] for p in PatternExtractor(_config(label)).extract_patterns(lines)]

    if not _drain3_mixes_severity(label, lines):
        assert patterns == expected["patterns"]
        return

    per_class = [pairs for pairs, _ in _drain3_per_class(label, lines)]
    assert sorted(patterns) == sorted(per_class[0] + per_class[1])
    assert sorted(patterns) != sorted(expected["patterns"])


@pytest.mark.parametrize(("name", "label"), CASES)
def test_quiet_lines_match_drain3(name, label):
    """The reducer mines only the quiet lines, and they give what Drain3 gave over them alone."""
    expected = QUIET_GOLDEN["results"][name][label]
    quiet_lines = [line for line in corpora.read_all(name, limit=GOLDEN["limit"]) if not is_severe(line)]
    assert len(quiet_lines) == expected["lines"]

    extractor = PatternExtractor(_config(label))
    patterns = extractor.extract_patterns(quiet_lines)

    assert sorted([p.template, p.count] for p in patterns) == expected["patterns"]
    assert len(extractor.miner.drain.id_to_cluster) == expected["live_clusters"]
