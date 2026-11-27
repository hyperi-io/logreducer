# Upstream:  Drain3, https://github.com/logpai/Drain3
#
# SPDX-License-Identifier: MIT
# This file implements the Drain algorithm for log parsing.
# Based on https://github.com/logpai/logparser/blob/master/logparser/Drain/Drain.py by LogPAI team
#
# MIT License
#
# Copyright (c) 2020-2022 International Business Machines
# and the Drain3 project contributors.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Project:   logreducer
# File:      src/logreducer/template_mining.py
# Purpose:   Online log template mining (the Drain algorithm) with regex pre-masking
# Language:  Python
#
# License:   Apache-2.0
# Copyright: (c) 2026 HYPERI PTY LIMITED

"""Online log template mining with the Drain algorithm.

Derived from Drain3 at commit 0fb6d6e1828838fa05c8f6fa5cda878e02ea79c7. It keeps
only the streaming path logreducer drives: mask a line, route it through a
fixed-depth prefix tree, and merge it into the most similar cluster of the same
token count, widening differing tokens to ``<*>``. Drain3's copyright and MIT
licence notice are in the header above, and the README credits Drain3 and logparser.
"""

import re
from collections import OrderedDict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

# Wildcard a widened template slot carries. Masks render as <NAME> in the same shape.
_PARAM_STR = "<*>"


class LogCluster:
    """One mined template and the number of lines merged into it.

    Attributes:
        log_template_tokens: The template, one token per whitespace-split word.
        cluster_id: Sequential id, never reused within a miner.
        size: Lines merged into this cluster.
        severe: Whether the line that founded the cluster was severe, as judged by
            the miner's ``is_severe`` predicate. Every merged line shares it.
        last_used: The miner's line number when the cluster last took a line.
    """

    __slots__ = ("cluster_id", "last_used", "log_template_tokens", "severe", "size")

    def __init__(self, log_template_tokens: Iterable[str], cluster_id: int, severe: bool = False) -> None:
        self.log_template_tokens = tuple(log_template_tokens)
        self.cluster_id = cluster_id
        self.size = 1
        self.severe = severe
        self.last_used = 0

    def get_template(self) -> str:
        """Return the template as one space-joined string."""
        return " ".join(self.log_template_tokens)


class ClusterStore:
    """Cluster id to cluster map, optionally bounded by least-recently-used eviction.

    Storing and ``touch`` mark a cluster as used. ``get`` and ``in`` only look, so
    scoring candidate clusters never changes which one is evicted next.
    """

    __slots__ = ("_clusters", "_maxsize")

    def __init__(self, maxsize: int | None = None) -> None:
        """Create an empty store.

        Args:
            maxsize: Clusters kept before the least recently used is evicted.
                ``None`` keeps every cluster.

        Raises:
            ValueError: If ``maxsize`` is below 1.
        """
        if maxsize is not None and maxsize < 1:
            raise ValueError(f"maxsize must be at least 1, not {maxsize}")
        self._maxsize = maxsize
        self._clusters: OrderedDict[int, LogCluster] = OrderedDict()

    def __setitem__(self, cluster_id: int, cluster: LogCluster) -> None:
        full = self._maxsize is not None and len(self._clusters) >= self._maxsize
        if full and cluster_id not in self._clusters:
            self._clusters.popitem(last=False)
        self._clusters[cluster_id] = cluster
        self._clusters.move_to_end(cluster_id)

    def __contains__(self, cluster_id: object) -> bool:
        return cluster_id in self._clusters

    def __len__(self) -> int:
        return len(self._clusters)

    def get(self, cluster_id: int) -> LogCluster | None:
        """Return the cluster without marking it used, or ``None`` if absent or evicted."""
        return self._clusters.get(cluster_id)

    def touch(self, cluster_id: int) -> None:
        """Mark a stored cluster as the most recently used."""
        self._clusters.move_to_end(cluster_id)

    def values(self) -> list[LogCluster]:
        """Return the stored clusters, least recently used first."""
        return list(self._clusters.values())


class Node:
    """A prefix-tree node: child nodes keyed by token, and the clusters stored here."""

    __slots__ = ("cluster_ids", "key_to_child_node")

    def __init__(self) -> None:
        self.key_to_child_node: dict[str, Node] = {}
        self.cluster_ids: list[int] = []


def _has_numbers(token: str) -> bool:
    return any(char.isdigit() for char in token)


class Drain:
    """The Drain online clustering algorithm over a fixed-depth prefix tree.

    The first tree level splits lines by token count, the next levels by leading
    tokens (a token containing a digit routes to the ``<*>`` child), and each leaf
    holds the clusters a line is scored against.

    Attributes:
        max_node_depth: Depth of the leaf nodes, counting the token-count level as 1.
        sim_th: Minimum share of matching tokens to join an existing cluster.
        max_children: Children a tree node holds before new tokens share ``<*>``.
        max_leaf_clusters: Clusters a leaf offers a line, the most recently used
            kept. ``None`` offers every live cluster, which is Drain3's behaviour.
        is_severe: Predicate that marks a line as severe. A severe line never
            joins a non-severe cluster, and the reverse, so a level word is never
            widened to ``<*>`` by a non-severe neighbour. ``None`` treats every
            line alike, which is Drain3's behaviour.
        root_node: Root of the prefix tree.
        id_to_cluster: Every live cluster, keyed by id.
        clusters_counter: The id given to the newest cluster.

    One-token lines all reach the same leaf, and with ``sim_th`` above 0 they can
    only join the cluster holding the same token, so they are looked up by token
    instead of scored against every cluster at that leaf.
    """

    def __init__(
        self,
        depth: int = 4,
        sim_th: float = 0.4,
        max_children: int = 100,
        max_clusters: int | None = None,
        is_severe: Callable[[str], bool] | None = None,
        max_leaf_clusters: int | None = None,
    ) -> None:
        """Create an empty miner.

        Args:
            depth: Tree depth, counting the root and the token-count level.
                Depth 4 routes on the first token only.
            sim_th: Minimum share of matching tokens to join an existing cluster.
            max_children: Children a tree node holds before new tokens share ``<*>``.
            max_clusters: Clusters kept before the least recently used is evicted.
                ``None`` keeps every cluster.
            is_severe: Predicate that keeps severe and non-severe lines in
                separate clusters. ``None`` treats every line alike.
            max_leaf_clusters: Clusters a leaf offers a line, which bounds the
                comparisons per line. Past it the leaf drops its least recently
                used cluster, which stays live but takes no more lines. ``None``
                offers every live cluster.

        Raises:
            ValueError: If ``depth`` is below 3, or ``max_clusters`` or
                ``max_leaf_clusters`` is below 1.
        """
        if depth < 3:
            raise ValueError(f"depth must be at least 3, not {depth}")
        if max_leaf_clusters is not None and max_leaf_clusters < 1:
            raise ValueError(f"max_leaf_clusters must be at least 1, not {max_leaf_clusters}")
        self.max_node_depth = depth - 2
        self.sim_th = sim_th
        self.max_children = max_children
        self.max_leaf_clusters = max_leaf_clusters
        self.is_severe = is_severe
        self.root_node = Node()
        self.id_to_cluster = ClusterStore(max_clusters)
        self.clusters_counter = 0
        self._lines_seen = 0
        # (token, severe) to cluster id for one-token clusters, which may name evicted ids.
        self._one_token_ids: dict[tuple[str, bool], int] = {}

    def _indexes_one_token(self, token: str) -> bool:
        """True when a one-token line can only join the cluster holding the same token."""
        return 0 < self.sim_th <= 1 and token != _PARAM_STR

    @property
    def clusters(self) -> list[LogCluster]:
        """Return every live cluster."""
        return self.id_to_cluster.values()

    def add_log_message(self, content: str) -> LogCluster:
        """Merge one (already masked) line into its cluster, creating one if none matches.

        Args:
            content: The line to cluster.

        Returns:
            The cluster the line joined. Its template reflects this line.
        """
        content_tokens = content.split()
        severe = self.is_severe is not None and self.is_severe(content)
        match_cluster = self.tree_search(content_tokens, severe)
        self._lines_seen += 1

        if match_cluster is None:
            self.clusters_counter += 1
            match_cluster = LogCluster(content_tokens, self.clusters_counter, severe)
            match_cluster.last_used = self._lines_seen
            self.id_to_cluster[match_cluster.cluster_id] = match_cluster
            self.add_seq_to_prefix_tree(match_cluster)
            return match_cluster

        match_cluster.log_template_tokens = self.create_template(content_tokens, match_cluster.log_template_tokens)
        match_cluster.size += 1
        match_cluster.last_used = self._lines_seen
        self.id_to_cluster.touch(match_cluster.cluster_id)
        return match_cluster

    def tree_search(self, tokens: Sequence[str], severe: bool = False) -> LogCluster | None:
        """Return the best live cluster for ``tokens`` at or above ``sim_th``, or ``None``.

        Args:
            tokens: The line, split on whitespace.
            severe: Whether the line is severe. Only clusters of the same severity are candidates.

        Returns:
            The matching cluster, or ``None`` when the line needs a new one.
        """
        token_count = len(tokens)
        cur_node = self.root_node.key_to_child_node.get(str(token_count))
        if cur_node is None:
            return None

        # Empty lines share the single cluster stored at their token-count node.
        if token_count == 0:
            return self.id_to_cluster.get(cur_node.cluster_ids[0])

        if token_count == 1 and self._indexes_one_token(tokens[0]):
            cluster_id = self._one_token_ids.get((tokens[0], severe))
            return None if cluster_id is None else self.id_to_cluster.get(cluster_id)

        cur_node_depth = 1
        for token in tokens:
            if cur_node_depth >= self.max_node_depth or cur_node_depth == token_count:
                break
            child = cur_node.key_to_child_node.get(token)
            if child is None:
                child = cur_node.key_to_child_node.get(_PARAM_STR)
            if child is None:
                return None
            cur_node = child
            cur_node_depth += 1

        return self.fast_match(cur_node.cluster_ids, tokens, severe)

    def add_seq_to_prefix_tree(self, cluster: LogCluster) -> None:
        """Route a new cluster down the tree and store its id at the leaf it reaches.

        Args:
            cluster: The cluster just created.
        """
        token_count = len(cluster.log_template_tokens)
        token_count_str = str(token_count)
        if token_count_str not in self.root_node.key_to_child_node:
            self.root_node.key_to_child_node[token_count_str] = Node()
        cur_node = self.root_node.key_to_child_node[token_count_str]

        if token_count == 0:
            cur_node.cluster_ids = [cluster.cluster_id]
            return

        if token_count == 1 and self._indexes_one_token(cluster.log_template_tokens[0]):
            self._one_token_ids[(cluster.log_template_tokens[0], cluster.severe)] = cluster.cluster_id
            # Dropping evicted ids at twice the live count costs O(1) per line, amortised.
            if len(self._one_token_ids) >= 2 * len(self.id_to_cluster):
                self._one_token_ids = {
                    key: cluster_id
                    for key, cluster_id in self._one_token_ids.items()
                    if cluster_id in self.id_to_cluster
                }
            return

        current_depth = 1
        for token in cluster.log_template_tokens:
            if current_depth >= self.max_node_depth or current_depth >= token_count:
                # Drop ids the store has evicted before adding the new one.
                live: list[LogCluster] = []
                for cluster_id in cur_node.cluster_ids:
                    kept = self.id_to_cluster.get(cluster_id)
                    if kept is not None:
                        live.append(kept)
                if self.max_leaf_clusters is not None and len(live) >= self.max_leaf_clusters:
                    # Removed in place, because list order breaks ties in fast_match.
                    live.remove(min(live, key=lambda candidate: candidate.last_used))
                cur_node.cluster_ids = [kept.cluster_id for kept in live]
                cur_node.cluster_ids.append(cluster.cluster_id)
                break

            children = cur_node.key_to_child_node
            if token in children:
                cur_node = children[token]
            elif _has_numbers(token):
                if _PARAM_STR not in children:
                    children[_PARAM_STR] = Node()
                cur_node = children[_PARAM_STR]
            elif _PARAM_STR in children:
                if len(children) < self.max_children:
                    children[token] = Node()
                    cur_node = children[token]
                else:
                    cur_node = children[_PARAM_STR]
            elif len(children) + 1 < self.max_children:
                children[token] = Node()
                cur_node = children[token]
            elif len(children) + 1 == self.max_children:
                children[_PARAM_STR] = Node()
                cur_node = children[_PARAM_STR]
            else:
                cur_node = children[_PARAM_STR]

            current_depth += 1

    def fast_match(self, cluster_ids: Sequence[int], tokens: Sequence[str], severe: bool = False) -> LogCluster | None:
        """Return the most similar live cluster at or above ``sim_th``, or ``None``.

        Ties on similarity go to the cluster with more ``<*>`` slots, then to the
        earlier candidate. Clusters whose severity differs from the line's are skipped.

        Args:
            cluster_ids: Candidate clusters stored at the leaf the line reached.
            tokens: The line, split on whitespace.
            severe: Whether the line is severe.

        Returns:
            The best candidate, or ``None`` if none reaches ``sim_th``.
        """
        max_sim = -1.0
        max_param_count = -1
        max_cluster = None

        for cluster_id in cluster_ids:
            cluster = self.id_to_cluster.get(cluster_id)
            # Departs from Drain3: a severe line and a non-severe cluster never match.
            if cluster is None or cluster.severe != severe:
                continue
            cur_sim, param_count = self.get_seq_distance(cluster.log_template_tokens, tokens)
            if cur_sim > max_sim or (cur_sim == max_sim and param_count > max_param_count):
                max_sim = cur_sim
                max_param_count = param_count
                max_cluster = cluster

        if max_sim >= self.sim_th:
            return max_cluster
        return None

    def get_seq_distance(self, template: Sequence[str], tokens: Sequence[str]) -> tuple[float, int]:
        """Score a line against a template of the same length.

        ``<*>`` slots count towards neither similarity nor mismatch.

        Args:
            template: The cluster template tokens.
            tokens: The line tokens.

        Returns:
            The share of template tokens the line matches exactly, and the number
            of ``<*>`` slots in the template.
        """
        if not template:
            return 1.0, 0

        sim_tokens = 0
        param_count = 0
        for template_token, token in zip(template, tokens, strict=True):
            if template_token == _PARAM_STR:
                param_count += 1
            elif template_token == token:
                sim_tokens += 1

        return sim_tokens / len(template), param_count

    def create_template(self, tokens: Sequence[str], template: Sequence[str]) -> tuple[str, ...]:
        """Widen every template token the line does not match to ``<*>``.

        Args:
            tokens: The line tokens.
            template: The current template tokens.

        Returns:
            The merged template.
        """
        return tuple(
            template_token if token == template_token else _PARAM_STR
            for token, template_token in zip(tokens, template, strict=True)
        )


class MaskingInstruction:
    """Replace every regex match in a line with ``<mask_with>`` before clustering.

    Attributes:
        regex: The compiled pattern.
        mask_with: Name the match renders as, inside angle brackets.
    """

    __slots__ = ("mask_with", "regex")

    def __init__(self, pattern: str, mask_with: str) -> None:
        """Compile a masking rule.

        Args:
            pattern: Regular expression for the values to mask.
            mask_with: Name the match renders as, inside angle brackets.
        """
        self.regex = re.compile(pattern)
        self.mask_with = mask_with

    def mask(self, content: str) -> str:
        """Return ``content`` with every match replaced by ``<mask_with>``."""
        return self.regex.sub(f"<{self.mask_with}>", content)


@dataclass(frozen=True, slots=True)
class TemplateMinerConfig:
    """Tuning for a :class:`TemplateMiner`.

    Attributes:
        drain_sim_th: Minimum share of matching tokens to join an existing cluster.
        drain_depth: Prefix-tree depth, counting the root and the token-count level.
        drain_max_children: Children a tree node holds before new tokens share ``<*>``.
        drain_max_clusters: Clusters kept before the least recently used is evicted.
            ``None`` keeps every cluster.
        drain_max_leaf_clusters: Clusters a leaf offers a line (see :class:`Drain`).
            ``None`` offers every live cluster.
        masking_instructions: Masks applied to each line in order, before clustering.
        drain_is_severe: Predicate that keeps severe and non-severe lines in
            separate clusters (see :class:`Drain`). ``None`` treats every line alike.
    """

    drain_sim_th: float = 0.4
    drain_depth: int = 4
    drain_max_children: int = 100
    drain_max_clusters: int | None = None
    drain_max_leaf_clusters: int | None = None
    masking_instructions: tuple[MaskingInstruction, ...] = ()
    drain_is_severe: Callable[[str], bool] | None = None


class TemplateMiner:
    """Mask each line, then cluster it with :class:`Drain`.

    Attributes:
        config: The tuning this miner was built with.
        drain: The clustering state.
    """

    def __init__(self, config: TemplateMinerConfig | None = None) -> None:
        """Create an empty miner.

        Args:
            config: Tuning. ``None`` uses the :class:`TemplateMinerConfig` defaults.
        """
        self.config = config if config is not None else TemplateMinerConfig()
        self.drain = Drain(
            depth=self.config.drain_depth,
            sim_th=self.config.drain_sim_th,
            max_children=self.config.drain_max_children,
            max_clusters=self.config.drain_max_clusters,
            is_severe=self.config.drain_is_severe,
            max_leaf_clusters=self.config.drain_max_leaf_clusters,
        )

    def add_log_message(self, log_message: str) -> LogCluster:
        """Mask one line and merge it into its cluster.

        Args:
            log_message: The raw line.

        Returns:
            The cluster the line joined. Its template keeps widening as later
            lines join, so read it again once the feed ends.
        """
        masked = log_message
        for instruction in self.config.masking_instructions:
            masked = instruction.mask(masked)
        return self.drain.add_log_message(masked)

    def get_cluster(self, cluster_id: int) -> LogCluster | None:
        """Return a live cluster without marking it used, or ``None`` once evicted."""
        return self.drain.id_to_cluster.get(cluster_id)
