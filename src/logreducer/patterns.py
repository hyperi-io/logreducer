"""Pattern extraction (Drain3 template mining) and fuzzy deduplication."""

import heapq
import logging
import re
from collections import deque
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

from .memory import Occurrence
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
    """Represents a unique log pattern.

    Attributes:
        template: The pattern, with ``<*>`` for the slots that vary.
        examples: Lines kept as examples.
        count: Lines that joined the pattern.
        priority: Rank score (see ``pattern_priority``).
        anomaly_score: Score from anomaly detection.
        metadata: Free-form extras.
        severe: Whether its lines are CRITICAL, FATAL or ERROR. Kept when the
            template has widened the level word to ``<*>``.
    """

    template: str
    examples: list[str] = field(default_factory=list)
    count: int = 0
    priority: float = 0.0
    anomaly_score: float = 0.0
    metadata: dict = field(default_factory=dict)
    severe: bool = False


def _typed_masking_instructions(timestamp: bool = False) -> tuple[MaskingInstruction, ...]:
    """Build the curated masking set for typed template slots.

    The miner applies these to each line before clustering, so masked values
    become literal typed tokens (``<IP>``, ``<NUM>``, ...) rather than
    collapsing to the bare ``<*>`` wildcard. Instructions run sequentially
    over already-masked text, so the specific shapes (IP, UUID, MAC, IPv6)
    precede the greedy catch-alls (HEX, NUM).

    Args:
        timestamp: Also mask ISO-8601 timestamps. Only the severe-shape key
            sets it, so the miner's typed templates stay as they are.
    """
    # Zero-width token boundaries (drain3's documented idiom): mask a value
    # delimited by non-alphanumerics, never a substring of a word.
    start = r"(?:(?<=[^A-Za-z0-9])|^)"
    end = r"(?:(?=[^A-Za-z0-9])|$)"
    hex4 = r"[0-9A-Fa-f]{1,4}"
    # ISO-8601 date and time, with optional fraction and Z or offset. Listed first because the
    # NUM mask stops at letters and would leave the "T10" and "07Z" of a stamp unmasked.
    iso_timestamp = (r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}(?::?\d{2})?)?", "TIMESTAMP")
    shapes = [
        *([iso_timestamp] if timestamp else []),
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


# A level is a whole word in any case, so a field name like error_count does not count.
_SEVERE_LEVEL = re.compile(r"\b(?:CRITICAL|FATAL|ERROR)\b", re.IGNORECASE)


def is_severe(text: str) -> bool:
    """True for a line or template that names a CRITICAL, FATAL or ERROR level."""
    return _SEVERE_LEVEL.search(text) is not None


class SevereShapes:
    """The first severe line of each shape, fed one line at a time.

    Numbers, IPs, hex runs and ISO-8601 timestamps do not change a shape, and digits inside an
    identifier do (``E1`` and ``E2`` are two shapes). The reducer feeds it every line as the
    source is read, before any sampling or dedup, so a severe line cannot be lost to either.
    It holds one line per distinct shape.
    """

    def __init__(self) -> None:
        self._masks = _typed_masking_instructions(timestamp=True)
        self._first_of_shape: dict[str, str] = {}

    def add(self, line: str) -> None:
        """Remember ``line`` when it is severe and its shape is new."""
        if not is_severe(line):
            return
        shape = line
        for mask in self._masks:
            shape = mask.mask(shape)
        self._first_of_shape.setdefault(shape, line)

    @property
    def lines(self) -> list[str]:
        """The remembered lines, in the order their shapes first appeared."""
        return list(self._first_of_shape.values())


def cap_outside_severe[T](ranked: Sequence[T], cap: int, severe: Callable[[T], bool]) -> list[T]:
    """Keep every severe item and the first ``cap`` others, in ranked order.

    A severity boost is a finite multiplier, so a frequent quiet item can outrank a rare
    severe one. Severe items sit outside the cap instead.
    """
    kept: list[T] = []
    others = 0
    for item in ranked:
        if severe(item):
            kept.append(item)
        elif others < cap:
            kept.append(item)
            others += 1
    return kept


def pattern_priority(template: str, count: int, severe: bool = False) -> float:
    """Rank score for a template seen ``count`` times.

    Severity boosts are checked highest-first so a template containing both
    (e.g. "CRITICAL: write FAILED") scores as critical, not merely error. A
    ``severe`` pattern scores as error at least, because its template may have
    widened the level word to ``<*>``.
    """
    priority: float = count

    template_upper = template.upper()
    if "CRITICAL" in template_upper or "FATAL" in template_upper:
        priority *= 200
    elif severe or "ERROR" in template_upper or "FAIL" in template_upper:
        priority *= 100
    elif "WARN" in template_upper:
        priority *= 50

    # Boost complex patterns
    priority *= 1 + template.count("<*>") * 0.5
    priority *= 1 + len(template.split()) * 0.1
    return priority


class _RetiredPatterns:
    """Patterns whose cluster was LRU-evicted, holding only those the capped ranking can still return.

    A retired pattern's template no longer changes, and its count grows only while the dedup
    cache still holds an ``Occurrence`` pointing at it. That cache is FIFO, so ``window`` lines
    after the last one that carried an ``Occurrence``, the count is final. Final patterns compete
    for the ``cap`` places the output has, and one that loses can never win one back. Severe
    patterns are all kept, as the cap does not apply to them.
    """

    def __init__(self, cap: int, min_count: int, window: int) -> None:
        self._cap = cap
        self._min_count = min_count
        self._window = window
        self._severe: list[tuple[int, LogPattern]] = []
        # Min-heap on (priority, -cluster_id): the root is the one the final sort ranks last.
        self._best: list[tuple[float, int, LogPattern]] = []
        # Min-heap on the line number of the pattern's last Occurrence.
        self._counting: list[tuple[int, int, LogPattern]] = []

    def add(self, cluster_id: int, pattern: LogPattern, last_occurrence: int | None) -> None:
        """Retire the pattern of an evicted cluster, given the line number of its last ``Occurrence``."""
        if pattern.severe:
            self._severe.append((cluster_id, pattern))
        elif last_occurrence is None:
            self._offer(cluster_id, pattern)
        else:
            heapq.heappush(self._counting, (last_occurrence, cluster_id, pattern))

    def advance(self, line_number: int) -> None:
        """Rank every retired pattern whose count can no longer change by ``line_number``."""
        while self._counting and line_number - self._counting[0][0] >= self._window:
            _, cluster_id, pattern = heapq.heappop(self._counting)
            self._offer(cluster_id, pattern)

    def _offer(self, cluster_id: int, pattern: LogPattern) -> None:
        if pattern.count < self._min_count:
            return
        heapq.heappush(self._best, (_priority(pattern), -cluster_id, pattern))
        if len(self._best) > self._cap:
            heapq.heappop(self._best)

    def items(self) -> list[tuple[int, LogPattern]]:
        """Return every retired pattern that could still reach the output, keyed by cluster id."""
        best = [(-negative_id, pattern) for _, negative_id, pattern in self._best]
        counting = [(cluster_id, pattern) for _, cluster_id, pattern in self._counting]
        return self._severe + best + counting


def _priority(pattern: LogPattern) -> float:
    return pattern_priority(pattern.template, pattern.count, pattern.severe)


class PatternExtractor:
    """Extract patterns using the online template miner (see template_mining)."""

    def __init__(self, config: BigDialConfig) -> None:
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
            drain_is_severe=is_severe,
        )
        self.miner = TemplateMiner(drain_config)

    def extract_patterns(self, lines: Iterable[str]) -> list[LogPattern]:
        """Extract patterns from lines (accepts a stream; only clusters are held).

        Feeds each line into the online miner, so the caller can pass a
        generator - no need to materialise the whole line set. With ``max_clusters``
        set, memory is bounded by it and by ``max_patterns``, not by the line count
        or the number of distinct templates.
        """
        return self.extract_counted_patterns((line, None) for line in lines)

    def extract_counted_patterns(self, pairs: Iterable[tuple[str, Occurrence | None]]) -> list[LogPattern]:
        """Like ``extract_patterns``, for lines paired with their dedup ``Occurrence``.

        Repeats that exact dedup drops after a line was kept still count towards
        the pattern that line joined, so 100 identical errors make one pattern
        with ``count == 100``. The ``Occurrence`` objects must come from a dedup
        cache, and any fuzzy index between, of at most ``dedup_cache_size`` lines:
        an evicted pattern's count is taken as final twice that many lines after
        its last ``Occurrence``, once a near-duplicate matched to it has also left
        the dedup cache.
        """
        pattern_map: dict[int, LogPattern] = {}
        last_occurrence: dict[int, int] = {}
        retired = _RetiredPatterns(
            self.config.max_patterns, self.config.min_pattern_occurrences, 2 * self.config.dedup_cache_size
        )
        max_clusters = self.config.max_clusters
        # Sweeping at twice the store's bound costs O(1) per line, amortised.
        sweep_at = None if max_clusters is None else 2 * max_clusters

        for line_number, (line, occurrence) in enumerate(pairs):
            retired.advance(line_number)
            cluster = self.miner.add_log_message(line)
            pattern = pattern_map.get(cluster.cluster_id)
            if pattern is None:
                pattern = LogPattern(template=cluster.get_template(), count=0, severe=cluster.severe)
                pattern_map[cluster.cluster_id] = pattern

            pattern.count += 1
            if occurrence is not None:
                occurrence.target = pattern
                last_occurrence[cluster.cluster_id] = line_number

            if len(pattern.examples) < self.config.examples_per_pattern:
                pattern.examples.append(line)

            if sweep_at is not None and len(pattern_map) >= sweep_at:
                self._retire_evicted(pattern_map, last_occurrence, retired)

        # Later lines widen a cluster's slots to <*>, so the stored template is
        # re-read once the feed ends; an LRU-evicted cluster keeps its snapshot.
        for cluster_id, pattern in pattern_map.items():
            live_cluster = self.miner.get_cluster(cluster_id)
            if live_cluster is not None:
                pattern.template = live_cluster.get_template()

        # Cluster ids rise in creation order, which the stable sort below breaks ties on.
        candidates = sorted([*pattern_map.items(), *retired.items()], key=lambda item: item[0])
        patterns = [pattern for _, pattern in candidates]

        # Apply filters
        patterns = self._filter_by_occurrence(patterns)
        patterns = self._calculate_priority(patterns)

        # Sort by priority and limit, with severe patterns outside the limit
        patterns.sort(key=lambda p: p.priority, reverse=True)
        return cap_outside_severe(patterns, self.config.max_patterns, lambda p: p.severe)

    def _retire_evicted(
        self, pattern_map: dict[int, LogPattern], last_occurrence: dict[int, int], retired: _RetiredPatterns
    ) -> None:
        """Move the patterns of clusters the miner has evicted out of ``pattern_map``."""
        evicted = [cluster_id for cluster_id in pattern_map if self.miner.get_cluster(cluster_id) is None]
        for cluster_id in evicted:
            retired.add(cluster_id, pattern_map.pop(cluster_id), last_occurrence.pop(cluster_id, None))

    def _filter_by_occurrence(self, patterns: list[LogPattern]) -> list[LogPattern]:
        """Filter patterns by minimum occurrence, keeping every CRITICAL, FATAL or ERROR one."""
        return [p for p in patterns if p.count >= self.config.min_pattern_occurrences or p.severe]

    def _calculate_priority(self, patterns: list[LogPattern]) -> list[LogPattern]:
        """Set each pattern's priority score (see ``pattern_priority``)."""
        for pattern in patterns:
            pattern.priority = pattern_priority(pattern.template, pattern.count, pattern.severe)

        return patterns


class FuzzyDeduplicator:
    """Fuzzy (near-duplicate) deduplication using MinHash LSH.

    With ``max_entries`` set, the index holds the most recently admitted lines and drops the
    oldest first, the same sliding window ``BoundedDeduplicator`` keeps for exact repeats. A
    near-duplicate of a line that has left the window is admitted again.
    """

    def __init__(self, threshold: float = 0.8, max_entries: int | None = None):
        """Create a deduplicator.

        Args:
            threshold: Jaccard similarity at or above which a line is a near-duplicate.
            max_entries: Admitted lines the index holds. ``None`` keeps every one.

        Raises:
            ValueError: If ``max_entries`` is below 1.
        """
        if max_entries is not None and max_entries < 1:
            raise ValueError(f"max_entries must be at least 1 or None, got {max_entries!r}")
        self.threshold = threshold
        self.max_entries = max_entries
        self._keys: deque[int] = deque()
        self._occurrences: dict[int, Occurrence] = {}
        self._next_key = 0
        self.enabled = MINHASH_AVAILABLE

        if self.enabled:
            self.lsh = MinHashLSH(threshold=threshold, num_perm=64)
        else:
            logger.warning("datasketch not installed - fuzzy dedup disabled (pip install 'logreducer[enhanced]')")

    def deduplicate_stream(self, lines: Iterable[str]) -> Iterator[str]:
        """Yield near-unique lines as they arrive (streaming near-dup filter).

        Queries the LSH per line and inserts only new ones, so the reducer never
        materialises the full unique-line list. The index grows with near-unique
        lines up to ``max_entries``.
        """
        if not self.enabled:
            yield from lines
            return

        for line in lines:
            if self._admit(line):
                yield line

    def deduplicate_pairs(self, pairs: Iterable[tuple[str, Occurrence]]) -> Iterator[tuple[str, Occurrence]]:
        """``deduplicate_stream`` over (line, Occurrence) pairs, keeping each pair intact.

        A dropped near-duplicate, and every later exact repeat of it, counts towards the
        pattern of the admitted line it matched.
        """
        if not self.enabled:
            yield from pairs
            return

        for pair in pairs:
            if self._admit(*pair):
                yield pair

    def _admit(self, line: str, occurrence: Occurrence | None = None) -> bool:
        """True (and remembered) when no near-duplicate of ``line`` is in the index."""
        m = MinHash(num_perm=64)
        for word in line.split():
            m.update(word.encode("utf-8", "surrogatepass"))

        if matches := cast("list[int]", self.lsh.query(m)):
            if occurrence is not None and (admitted := self._occurrences.get(min(matches))) is not None:
                occurrence.target = admitted.target
                admitted.repeat()
            return False
        if self.max_entries is not None and len(self._keys) >= self.max_entries:
            evicted = self._keys.popleft()
            self.lsh.remove(evicted)
            self._occurrences.pop(evicted, None)
        key = self._next_key
        self._next_key += 1
        self.lsh.insert(key, m)
        self._keys.append(key)
        if occurrence is not None:
            self._occurrences[key] = occurrence
        return True

    def deduplicate(self, lines: Iterable[str]) -> list[str]:
        """Remove near-duplicates, returning a list (eager wrapper of the stream)."""
        return list(self.deduplicate_stream(lines))
