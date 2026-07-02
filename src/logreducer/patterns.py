"""
Pattern extraction and clustering utilities
"""

from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig

if TYPE_CHECKING:
    from .config import BigDialConfig

# Try optional imports
try:
    from datasketch import MinHash, MinHashLSH

    MINHASH_AVAILABLE = True
except ImportError:
    MINHASH_AVAILABLE = False

try:
    import numpy as np
    from scipy.stats import entropy

    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


@dataclass
class LogPattern:
    """Represents a unique log pattern"""

    template: str
    examples: list[str] = field(default_factory=list)
    count: int = 0
    priority: float = 0.0
    anomaly_score: float = 0.0
    metadata: dict = field(default_factory=dict)


class PatternExtractor:
    """Extract patterns using Drain3 and other methods"""

    def __init__(self, config: "BigDialConfig") -> None:
        self.config = config
        self.setup_drain3()

    def setup_drain3(self) -> None:
        """Configure Drain3"""
        drain_config = TemplateMinerConfig()
        drain_config.profiling_enabled = False
        drain_config.drain_sim_th = self.config.drain_similarity
        drain_config.drain_depth = 4
        drain_config.snapshot_interval_minutes = 0  # Disable snapshots
        drain_config.snapshot_compress_state = False
        # Bound the template store when configured: Drain3 LRU-evicts beyond
        # drain_max_clusters, keeping memory flat on high-cardinality logs.
        drain_config.drain_max_clusters = self.config.max_clusters
        self.miner = TemplateMiner(config=drain_config)

    def extract_patterns(self, lines: Iterable[str]) -> list[LogPattern]:
        """Extract patterns from lines (accepts a stream; only clusters are held).

        Feeds each line into Drain3's online miner, so the caller can pass a
        generator - no need to materialise the whole line set. Memory is bounded
        by the number of clusters (see ``max_clusters``), not the line count.
        """
        pattern_map = {}

        for line in lines:
            result = self.miner.add_log_message(line)
            cluster_id = result["cluster_id"]

            if cluster_id not in pattern_map:
                cluster = self.miner.drain.id_to_cluster[cluster_id]
                pattern = LogPattern(template=cluster.get_template(), count=0)
                pattern_map[cluster_id] = pattern

            pattern = pattern_map[cluster_id]
            pattern.count += 1

            if len(pattern.examples) < self.config.examples_per_pattern:
                pattern.examples.append(line)

        patterns = list(pattern_map.values())

        # Apply filters
        patterns = self._filter_by_occurrence(patterns)
        patterns = self._calculate_priority(patterns)

        if SCIPY_AVAILABLE and hasattr(self.config, "entropy_threshold"):
            patterns = self._entropy_filter(patterns)

        # Sort by priority and limit
        patterns.sort(key=lambda p: p.priority, reverse=True)
        return patterns[: self.config.max_patterns]

    def _filter_by_occurrence(self, patterns: list[LogPattern]) -> list[LogPattern]:
        """Filter patterns by minimum occurrence"""
        return [p for p in patterns if p.count >= self.config.min_pattern_occurrences]

    def _calculate_priority(self, patterns: list[LogPattern]) -> list[LogPattern]:
        """Calculate priority scores"""
        for pattern in patterns:
            priority: float = pattern.count

            # Boost errors and warnings
            template_upper = pattern.template.upper()
            if "ERROR" in template_upper or "FAIL" in template_upper:
                priority *= 100
            elif "WARN" in template_upper:
                priority *= 50
            elif "CRITICAL" in template_upper or "FATAL" in template_upper:
                priority *= 200

            # Boost complex patterns
            priority *= 1 + pattern.template.count("<*>") * 0.5
            priority *= 1 + len(pattern.template.split()) * 0.1

            pattern.priority = priority

        return patterns

    def _entropy_filter(self, patterns: list[LogPattern]) -> list[LogPattern]:
        """Filter by information entropy"""
        if not SCIPY_AVAILABLE:
            return patterns

        for pattern in patterns:
            template_tokens = pattern.template.split()
            token_counts = Counter(template_tokens)
            probs = np.array(list(token_counts.values())) / len(template_tokens)
            pattern.metadata["entropy"] = entropy(probs)

        # Filter by entropy threshold
        if hasattr(self.config, "entropy_threshold"):
            patterns = [p for p in patterns if p.metadata.get("entropy", 1) > self.config.entropy_threshold]

        return patterns


class FuzzyDeduplicator:
    """Fuzzy deduplication using MinHash"""

    def __init__(self, threshold: float = 0.8):
        self.threshold = threshold
        self.enabled = MINHASH_AVAILABLE

        if self.enabled:
            self.lsh = MinHashLSH(threshold=threshold, num_perm=64)

    def deduplicate_stream(self, lines: Iterable[str]) -> Iterator[str]:
        """Yield near-unique lines as they arrive (streaming near-dup filter).

        Queries the LSH per line and inserts only new ones, so the reducer never
        materialises the full unique-line list. Note the LSH itself grows with
        the number of near-unique lines - that is inherent to fuzzy dedup.
        """
        if not self.enabled:
            yield from lines
            return

        for i, line in enumerate(lines):
            m = MinHash(num_perm=64)
            for word in line.split():
                m.update(word.encode("utf8"))

            if not self.lsh.query(m):
                self.lsh.insert(f"line_{i}", m)
                yield line

    def deduplicate(self, lines: Iterable[str]) -> list[str]:
        """Remove near-duplicates, returning a list (eager wrapper of the stream)."""
        return list(self.deduplicate_stream(lines))
