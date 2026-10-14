"""Unit tests for the template miner (logreducer.template_mining).

Real miner, no mocks. The cross-check against the drain3 output it replaced
lives in tests/integration/test_template_equivalence.py.
"""

import importlib.metadata
import re
import subprocess
import sys

import pytest

from logreducer.template_mining import (
    ClusterStore,
    Drain,
    LogCluster,
    MaskingInstruction,
    TemplateMiner,
    TemplateMinerConfig,
)

# Packages the miner replaced; none may be imported or declared any more.
REPLACED = {"drain3", "jsonpickle", "cachetools", "loguru"}


class TestClustering:
    def test_differing_token_widens_to_wildcard(self):
        miner = TemplateMiner()
        first = miner.add_log_message("user alice logged in")
        second = miner.add_log_message("user bob logged in")

        assert first is second
        assert second.get_template() == "user <*> logged in"
        assert second.size == 2

    def test_below_similarity_threshold_starts_a_new_cluster(self):
        # One of four tokens matches: 0.25 is below the default 0.4.
        miner = TemplateMiner()
        first = miner.add_log_message("disk full on sda")
        second = miner.add_log_message("disk ok for now")

        assert first.cluster_id != second.cluster_id

    def test_lower_threshold_merges_the_same_lines(self):
        miner = TemplateMiner(TemplateMinerConfig(drain_sim_th=0.2))
        first = miner.add_log_message("disk full on sda")
        second = miner.add_log_message("disk ok for now")

        assert first is second
        assert second.get_template() == "disk <*> <*> <*>"

    def test_token_count_partitions_clusters(self):
        miner = TemplateMiner()
        short = miner.add_log_message("job done")
        long = miner.add_log_message("job done quickly")

        assert short.cluster_id != long.cluster_id

    def test_empty_and_blank_lines_share_one_empty_cluster(self):
        miner = TemplateMiner()
        empty = miner.add_log_message("")
        blank = miner.add_log_message("   \t ")

        assert empty is blank
        assert empty.get_template() == ""
        assert empty.size == 2

    def test_whitespace_runs_split_like_single_spaces(self):
        miner = TemplateMiner()
        first = miner.add_log_message("  a   b c ")
        second = miner.add_log_message("a b c")

        assert first is second
        assert second.get_template() == "a b c"

    def test_cluster_ids_are_sequential(self):
        miner = TemplateMiner()
        ids = [miner.add_log_message(line).cluster_id for line in ("a", "b c", "d e f")]

        assert ids == [1, 2, 3]

    def test_full_node_routes_new_first_tokens_to_the_wildcard_child(self):
        # max_children=3: alpha and beta get their own nodes, the third slot
        # becomes <*>, and gamma and delta both land under it and merge.
        miner = TemplateMiner(TemplateMinerConfig(drain_max_children=3))
        clusters = [miner.add_log_message(f"{word} x y") for word in ("alpha", "beta", "gamma", "delta")]

        assert len({c.cluster_id for c in clusters}) == 3
        assert clusters[2] is clusters[3]
        assert clusters[3].get_template() == "<*> x y"

    def test_numeric_first_token_routes_to_the_wildcard_child(self):
        miner = TemplateMiner()
        miner.add_log_message("42 requests served")

        first_layer = miner.drain.root_node.key_to_child_node["3"]
        assert list(first_layer.key_to_child_node) == ["<*>"]

    def test_depth_below_three_is_rejected(self):
        with pytest.raises(ValueError, match="depth must be at least 3"):
            Drain(depth=2)


class TestMasking:
    def test_mask_renders_as_named_slot(self):
        miner = TemplateMiner(TemplateMinerConfig(masking_instructions=(MaskingInstruction(r"\d+", "NUM"),)))
        cluster = miner.add_log_message("took 15 ms")

        assert cluster.get_template() == "took <NUM> ms"

    def test_masks_apply_in_order(self):
        # The IP mask runs first, so the NUM mask never sees the octets.
        instructions = (
            MaskingInstruction(r"\d{1,3}(?:\.\d{1,3}){3}", "IP"),
            MaskingInstruction(r"\d+", "NUM"),
        )
        miner = TemplateMiner(TemplateMinerConfig(masking_instructions=instructions))

        assert miner.add_log_message("from 10.0.0.1 port 22").get_template() == "from <IP> port <NUM>"


class TestClusterStore:
    def _cluster(self, cluster_id: int) -> LogCluster:
        return LogCluster(["t"], cluster_id)

    def test_unbounded_store_keeps_everything(self):
        store = ClusterStore()
        for cluster_id in range(1, 101):
            store[cluster_id] = self._cluster(cluster_id)

        assert len(store) == 100

    def test_evicts_least_recently_used(self):
        store = ClusterStore(maxsize=2)
        store[1] = self._cluster(1)
        store[2] = self._cluster(2)
        store.touch(1)
        store[3] = self._cluster(3)

        assert 2 not in store
        assert 1 in store
        assert 3 in store

    def test_get_does_not_refresh_recency(self):
        store = ClusterStore(maxsize=2)
        store[1] = self._cluster(1)
        store[2] = self._cluster(2)
        assert store.get(1) is not None
        store[3] = self._cluster(3)

        assert store.get(1) is None
        assert store.get(2) is not None

    def test_replacing_a_stored_id_evicts_nothing(self):
        store = ClusterStore(maxsize=2)
        store[1] = self._cluster(1)
        store[2] = self._cluster(2)
        store[1] = self._cluster(1)

        assert len(store) == 2

    @pytest.mark.parametrize("maxsize", [0, -1])
    def test_maxsize_below_one_is_rejected(self, maxsize):
        with pytest.raises(ValueError, match="maxsize must be at least 1"):
            ClusterStore(maxsize=maxsize)

    def test_miner_get_cluster_returns_none_once_evicted(self):
        miner = TemplateMiner(TemplateMinerConfig(drain_max_clusters=1))
        first = miner.add_log_message("a b")
        second = miner.add_log_message("c d e")

        assert miner.get_cluster(first.cluster_id) is None
        assert miner.get_cluster(second.cluster_id) is second


class TestNoReplacedDependency:
    def test_importing_logreducer_loads_none_of_the_replaced_packages(self):
        code = (
            "import sys, logreducer, logreducer.core, logreducer.patterns, logreducer.temporal\n"
            "print(sorted(m for m in sys.modules if m.split('.')[0] in "
            f"{sorted(REPLACED)!r}))"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )

        assert result.stdout.strip() == "[]"

    def test_distribution_declares_none_of_the_replaced_packages(self):
        requirements = importlib.metadata.requires("logreducer") or []
        names = {re.split(r"[\s;<>=!~\[(]", req, maxsplit=1)[0].lower() for req in requirements}

        assert names.isdisjoint(REPLACED)
