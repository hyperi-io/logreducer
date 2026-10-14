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
from logreducer.patterns import PatternExtractor
from tests.integration import corpora

pytestmark = pytest.mark.integration

GOLDEN_PATH = corpora.TESTDATA_DIR / "template_mining_golden.json.gz"
GOLDEN: dict[str, Any] = json.loads(gzip.decompress(GOLDEN_PATH.read_bytes()))
CASES = [(name, label) for name in GOLDEN["results"] for label in GOLDEN["configs"]]


def _config(label: str) -> BigDialConfig:
    # Keep every cluster, so the comparison covers the whole template set.
    return BigDialConfig(min_pattern_occurrences=1, max_patterns=10**9, **GOLDEN["configs"][label])


def test_golden_covers_every_corpus():
    assert sorted(GOLDEN["results"]) == sorted(corpora.dataset_names())


@pytest.mark.parametrize(("name", "label"), CASES)
def test_cluster_assignment_matches_drain3(name, label):
    expected = GOLDEN["results"][name][label]
    lines = corpora.read_all(name, limit=GOLDEN["limit"])
    assert len(lines) == expected["lines"]

    miner = PatternExtractor(_config(label)).miner
    ids = [miner.add_log_message(line).cluster_id for line in lines]

    assert hashlib.sha256(",".join(map(str, ids)).encode()).hexdigest() == expected["assignments_sha256"]
    assert len(miner.drain.id_to_cluster) == expected["live_clusters"]


@pytest.mark.parametrize(("name", "label"), CASES)
def test_extracted_patterns_match_drain3(name, label):
    expected = GOLDEN["results"][name][label]
    lines = corpora.read_all(name, limit=GOLDEN["limit"])

    patterns = PatternExtractor(_config(label)).extract_patterns(lines)

    assert [[p.template, p.count] for p in patterns] == expected["patterns"]
