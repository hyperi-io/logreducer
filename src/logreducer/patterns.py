"""Pattern extraction (Drain3 template mining) and fuzzy deduplication."""

import logging
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .template_mining import MaskingInstruction, TemplateMiner, TemplateMinerConfig

if TYPE_CHECKING:
    from .config import BigDialConfig

logger = logging.getLogger(__name__)

# datasketch powers fuzzy dedup and ships in the optional `enhanced` extra;
# without it FuzzyDeduplicator degrades to a pass-through (with a warning).
try:
    from datasketch import MinHash, MinHashLSH

    MINHASH_AVAILABLE = True
except ImportError:
    MINHASH_AVAILABLE = False


@dataclass
class LogPattern:
    """Represents a unique log pattern."""

    template: str
    examples: list[str] = field(default_factory=list)
    count: int = 0
    priority: float = 0.0
    anomaly_score: float = 0.0
    metadata: dict = field(default_factory=dict)


def _typed_masking_instructions() -> tuple[MaskingInstruction, ...]:
    """Build the curated masking set for typed template slots.

    The miner applies these to each line before clustering, so masked values
    become literal typed tokens (``<IP>``, ``<NUM>``, ...) rather than
    collapsing to the bare ``<*>`` wildcard. Instructions run sequentially
    over already-masked text, so the specific shapes (IP, UUID, MAC, IPv6)
    precede the greedy catch-alls (HEX, NUM).
    """
    # Zero-width token boundaries (drain3's documented idiom): mask a value
    # delimited by non-alphanumerics, never a substring of a word.
    start = r"(?:(?<=[^A-Za-z0-9])|^)"
    end = r"(?:(?=[^A-Za-z0-9])|$)"
    hex4 = r"[0-9A-Fa-f]{1,4}"
    shapes = [
        # IPv4 dotted quad.
        (r"\d{1,3}(?:\.\d{1,3}){3}", "IP"),
        # UUID before HEX, which would otherwise eat its 8/12-char runs.
        (r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}", "UUID"),
        # MAC (colon or dash separated) before IPv6, whose colon-hex shape overlaps.
        (r"[0-9A-Fa-f]{2}(?:[:-][0-9A-Fa-f]{2}){5}", "MAC"),
        # IPv6, best-effort: the full 8-group form, a '::'-compressed form
        # (middle or trailing), then a leading-'::' form. Plain colon runs
        # without '::' stay unmasked - that shape also matches timestamps.
        (
            rf"(?:{hex4}:){{7}}{hex4}"
            rf"|(?:{hex4}:){{1,6}}:(?:{hex4}(?::{hex4}){{0,5}})?"
            rf"|::(?:{hex4}(?::{hex4}){{0,6}})?",
            "IPV6",
        ),
        # Hex token of >= 8 hex chars: 0x-prefixed, or containing at least
        # one a-f letter so a long pure-decimal token stays NUM.
        (r"0[xX][0-9A-Fa-f]{8,}|(?=\d*[A-Fa-f])[0-9A-Fa-f]{8,}", "HEX"),
        # Integer (drain3's documented NUM example).
        (r"[-+]?\d+", "NUM"),
    ]
    return tuple(MaskingInstruction(f"{start}(?:{pattern}){end}", name) for pattern, name in shapes)


class PatternExtractor:
    """Extract patterns using the online template miner (see template_mining)."""

    def __init__(self, config: "BigDialConfig") -> None:
        self.config = config
        self.setup_drain3()

    def setup_drain3(self) -> None:
        """Configure the template miner."""
        # Opt-in typed masking: pre-cluster masking of well-known value shapes
        # so templates carry typed slots (<IP>, <NUM>, ...) instead of <*>.
        masking = _typed_masking_instructions() if self.config.typed_masking else ()
        drain_config = TemplateMinerConfig(
            drain_sim_th=self.config.drain_similarity,
            drain_depth=4,
            # Bound the template store when configured: the miner LRU-evicts beyond
            # drain_max_clusters, keeping memory flat on high-cardinality logs.
            drain_max_clusters=self.config.max_clusters,
            masking_instructions=masking,
        )
        self.miner = TemplateMiner(drain_config)

    def extract_patterns(self, lines: Iterable[str]) -> list[LogPattern]:
        """Extract patterns from lines (accepts a stream; only clusters are held).

        Feeds each line into the online miner, so the caller can pass a
        generator - no need to materialise the whole line set. Memory is bounded
        by the number of clusters (see ``max_clusters``), not the line count.
        """
        pattern_map: dict[int, LogPattern] = {}

        for line in lines:
            cluster = self.miner.add_log_message(line)
            pattern = pattern_map.get(cluster.cluster_id)
            if pattern is None:
                pattern = LogPattern(template=cluster.get_template(), count=0)
                pattern_map[cluster.cluster_id] = pattern

            pattern.count += 1

            if len(pattern.examples) < self.config.examples_per_pattern:
                pattern.examples.append(line)

        # Later lines widen a cluster's slots to <*>, so the stored template is
        # re-read once the feed ends; an LRU-evicted cluster keeps its snapshot.
        for cluster_id, pattern in pattern_map.items():
            live_cluster = self.miner.get_cluster(cluster_id)
            if live_cluster is not None:
                pattern.template = live_cluster.get_template()

        patterns = list(pattern_map.values())

        # Apply filters
        patterns = self._filter_by_occurrence(patterns)
        patterns = self._calculate_priority(patterns)

        # Sort by priority and limit
        patterns.sort(key=lambda p: p.priority, reverse=True)
        return patterns[: self.config.max_patterns]

    def _filter_by_occurrence(self, patterns: list[LogPattern]) -> list[LogPattern]:
        """Filter patterns by minimum occurrence."""
        return [p for p in patterns if p.count >= self.config.min_pattern_occurrences]

    def _calculate_priority(self, patterns: list[LogPattern]) -> list[LogPattern]:
        """Calculate priority scores.

        Severity boosts are checked highest-first so a template containing both
        (e.g. "CRITICAL: write FAILED") scores as critical, not merely error.
        """
        for pattern in patterns:
            priority: float = pattern.count

            template_upper = pattern.template.upper()
            if "CRITICAL" in template_upper or "FATAL" in template_upper:
                priority *= 200
            elif "ERROR" in template_upper or "FAIL" in template_upper:
                priority *= 100
            elif "WARN" in template_upper:
                priority *= 50

            # Boost complex patterns
            priority *= 1 + pattern.template.count("<*>") * 0.5
            priority *= 1 + len(pattern.template.split()) * 0.1

            pattern.priority = priority

        return patterns


class FuzzyDeduplicator:
    """Fuzzy (near-duplicate) deduplication using MinHash LSH."""

    def __init__(self, threshold: float = 0.8):
        self.threshold = threshold
        self.enabled = MINHASH_AVAILABLE

        if self.enabled:
            self.lsh = MinHashLSH(threshold=threshold, num_perm=64)
        else:
            logger.warning("datasketch not installed - fuzzy dedup disabled (pip install 'logreducer[enhanced]')")

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
                m.update(word.encode("utf-8", "surrogatepass"))

            if not self.lsh.query(m):
                self.lsh.insert(f"line_{i}", m)
                yield line

    def deduplicate(self, lines: Iterable[str]) -> list[str]:
        """Remove near-duplicates, returning a list (eager wrapper of the stream)."""
        return list(self.deduplicate_stream(lines))
