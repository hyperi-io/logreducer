"""
Unit tests for pattern extraction module
"""

from unittest.mock import Mock, patch

from logreducer.config import BigDialConfig
from logreducer.patterns import FuzzyDeduplicator, LogPattern, PatternExtractor


class TestLogPattern:
    """Test cases for LogPattern dataclass"""

    def test_log_pattern_creation(self):
        """Test LogPattern creation with defaults"""
        pattern = LogPattern(template="User <*> logged in")

        assert pattern.template == "User <*> logged in"
        assert pattern.examples == []
        assert pattern.count == 0
        assert pattern.priority == 0.0
        assert pattern.anomaly_score == 0.0
        assert pattern.metadata == {}

    def test_log_pattern_with_data(self):
        """Test LogPattern creation with data"""
        examples = ["User alice logged in", "User bob logged in"]
        metadata = {"source": "auth.log"}

        pattern = LogPattern(
            template="User <*> logged in",
            examples=examples,
            count=5,
            priority=10.5,
            metadata=metadata,
        )

        assert pattern.template == "User <*> logged in"
        assert pattern.examples == examples
        assert pattern.count == 5
        assert pattern.priority == 10.5
        assert pattern.metadata == metadata


class TestPatternExtractor:
    """Test cases for PatternExtractor"""

    def test_initialization_with_config(self):
        """Test pattern extractor initialization with config"""
        config = BigDialConfig(max_patterns=100, examples_per_pattern=3)

        extractor = PatternExtractor(config)

        assert extractor.config == config
        assert hasattr(extractor, "miner")

    @patch("logreducer.patterns.TemplateMiner")
    def test_extract_patterns_empty_input(self, mock_template_miner):
        """Test pattern extraction with empty input"""
        config = BigDialConfig()
        extractor = PatternExtractor(config)

        result = extractor.extract_patterns([])

        assert result == []

    @patch("logreducer.patterns.TemplateMiner")
    def test_extract_patterns_basic(self, mock_template_miner):
        """Test basic pattern extraction"""
        config = BigDialConfig(max_patterns=10, examples_per_pattern=2)

        # Mock the miner and cluster
        mock_cluster = Mock()
        mock_cluster.get_template.return_value = "User <*> logged in"

        mock_miner = Mock()
        mock_miner.add_log_message.return_value = {"cluster_id": 1}
        mock_miner.drain.id_to_cluster = {1: mock_cluster}
        mock_template_miner.return_value = mock_miner

        extractor = PatternExtractor(config)
        extractor.miner = mock_miner

        lines = ["User alice logged in", "User bob logged in", "User charlie logged in"]

        result = extractor.extract_patterns(lines)

        # Should have processed lines
        assert mock_miner.add_log_message.call_count == len(lines)

        # Should return patterns
        assert isinstance(result, list)
        if len(result) > 0:
            assert isinstance(result[0], LogPattern)

    def test_filter_by_occurrence(self):
        """Test filtering patterns by minimum occurrence"""
        config = BigDialConfig(min_pattern_occurrences=3)
        extractor = PatternExtractor(config)

        patterns = [
            LogPattern(template="Pattern 1", count=5),
            LogPattern(template="Pattern 2", count=1),  # Should be filtered
            LogPattern(template="Pattern 3", count=10),
        ]

        filtered = extractor._filter_by_occurrence(patterns)

        assert len(filtered) == 2
        assert all(p.count >= 3 for p in filtered)

    def test_calculate_priority(self):
        """Test priority calculation"""
        config = BigDialConfig()
        extractor = PatternExtractor(config)

        patterns = [
            LogPattern(template="INFO: Normal operation", count=10),
            LogPattern(template="ERROR: Something failed", count=5),
            LogPattern(template="CRITICAL: System down", count=2),
        ]

        result = extractor._calculate_priority(patterns)

        # Priorities should be calculated
        for pattern in result:
            assert pattern.priority > 0

        # ERROR and CRITICAL should have higher priority than INFO (considering multipliers)
        error_pattern = next(p for p in result if "ERROR" in p.template)
        critical_pattern = next(p for p in result if "CRITICAL" in p.template)
        info_pattern = next(p for p in result if "INFO" in p.template)

        # CRITICAL should have highest priority (count * 200)
        assert critical_pattern.priority > info_pattern.priority
        # ERROR should have higher priority than INFO (count * 100 vs count * 1)
        assert error_pattern.priority > info_pattern.priority

    def test_initialization_default(self):
        """Test fuzzy deduplicator initialization with defaults"""
        dedup = FuzzyDeduplicator()

        assert dedup.threshold == 0.8
        assert hasattr(dedup, "enabled")

    @patch("logreducer.patterns.MINHASH_AVAILABLE", True)
    def test_initialization_custom_threshold(self):
        """Test fuzzy deduplicator initialization with custom threshold"""
        dedup = FuzzyDeduplicator(threshold=0.9)

        assert dedup.threshold == 0.9

    @patch("logreducer.patterns.MINHASH_AVAILABLE", False)
    def test_minhash_unavailable(self):
        """Test behavior when MinHash is unavailable"""
        dedup = FuzzyDeduplicator()

        assert not dedup.enabled

        # Should still work but return original lines when disabled
        lines = ["Line 1", "Line 1", "Line 2"]
        result = dedup.deduplicate(lines)

        # When disabled, should return original lines
        assert result == lines

    @patch("logreducer.patterns.MINHASH_AVAILABLE", True)
    @patch("logreducer.patterns.MinHashLSH")
    @patch("logreducer.patterns.MinHash")
    def test_deduplicate_lines_with_minhash(self, mock_minhash, mock_lsh):
        """Test deduplication with MinHash enabled"""
        # Mock MinHash
        mock_signature = Mock()
        mock_minhash.return_value = mock_signature

        # Mock LSH
        mock_lsh_instance = Mock()
        mock_lsh_instance.query.return_value = []  # No similar signatures found
        mock_lsh.return_value = mock_lsh_instance

        dedup = FuzzyDeduplicator()
        dedup.enabled = True
        dedup.lsh = mock_lsh_instance

        lines = [
            "User alice logged in from 192.168.1.1",
            "User bob logged in from 192.168.1.2",
            "System error occurred",
        ]

        result = dedup.deduplicate(lines)

        # Should process all lines
        assert len(result) <= len(lines)

    def test_simple_deduplication_fallback(self):
        """Test simple deduplication when MinHash unavailable"""
        with patch("logreducer.patterns.MINHASH_AVAILABLE", False):
            dedup = FuzzyDeduplicator()

            lines = [
                "Duplicate line",
                "Unique line",
                "Duplicate line",  # Exact duplicate
                "Another unique line",
            ]

            result = dedup.deduplicate(lines)

            # When MinHash unavailable, should return original lines unchanged
            assert len(result) == 4
            assert result == lines

    def test_get_statistics(self):
        """Test getting deduplication statistics"""
        dedup = FuzzyDeduplicator()

        lines = ["Line 1", "Line 2", "Line 1", "Line 3"]
        result = dedup.deduplicate(lines)

        # For now, just verify it returns something reasonable
        assert isinstance(result, list)
        assert len(result) <= len(lines)


class TestStreamingAndBounds:
    """Streaming fuzzy dedup and the bounded Drain3 template store."""

    def test_deduplicate_stream_is_a_generator(self):
        import types

        dedup = FuzzyDeduplicator()
        out = dedup.deduplicate_stream(iter(["a b c", "a b c", "x y z"]))
        assert isinstance(out, types.GeneratorType)  # lazy, not a materialised list
        result = list(out)
        if dedup.enabled:
            assert "a b c" in result
            assert "x y z" in result
        else:
            assert result == ["a b c", "a b c", "x y z"]  # passthrough when disabled

    def test_max_clusters_bounds_template_store(self):
        # 50 distinct templates (each twice, to survive the occurrence filter),
        # but the store is capped at 5 -> Drain3 LRU-evicts down to the cap.
        extractor = PatternExtractor(BigDialConfig(max_clusters=5))
        lines = [f"SERVICE{i} started on host node{i} pid={p}" for i in range(50) for p in (1, 2)]
        extractor.extract_patterns(lines)
        assert len(extractor.miner.drain.id_to_cluster) <= 5


class TestTypedMasking:
    """Opt-in typed Drain3 masking (config.typed_masking)."""

    IP_LINES = [
        "Accepted connection from 192.168.1.10 port 22",
        "Accepted connection from 10.0.0.7 port 22",
        "Accepted connection from 172.16.31.5 port 22",
    ]
    NUM_LINES = [
        "Task finished in 123 ms",
        "Task finished in 45678 ms",
        "Task finished in 9 ms",
    ]

    def test_default_ip_lines_use_bare_wildcard(self):
        """Off by default: the IP slot is a bare <*>, never a typed mask.

        Asserted on the live Drain cluster template - LogPattern.template is a
        first-seen snapshot, taken before later lines widen any slot to <*>.
        """
        extractor = PatternExtractor(BigDialConfig())
        extractor.extract_patterns(self.IP_LINES)
        clusters = list(extractor.miner.drain.clusters)
        assert len(clusters) == 1
        template = clusters[0].get_template()
        assert "<*>" in template
        assert "<IP>" not in template

    def test_default_configures_no_masking_instructions(self):
        """Off by default: the miner carries zero masking instructions."""
        extractor = PatternExtractor(BigDialConfig())
        assert list(extractor.miner.masker.masking_instructions) == []

    def test_typed_masking_ip(self):
        """IP-bearing lines yield a typed <IP> slot, no bare wildcard."""
        extractor = PatternExtractor(BigDialConfig(typed_masking=True))
        patterns = extractor.extract_patterns(self.IP_LINES)
        assert len(patterns) == 1
        assert "<IP>" in patterns[0].template
        assert "<*>" not in patterns[0].template

    def test_typed_masking_num(self):
        """Number-bearing lines yield a typed <NUM> slot."""
        extractor = PatternExtractor(BigDialConfig(typed_masking=True))
        patterns = extractor.extract_patterns(self.NUM_LINES)
        assert len(patterns) == 1
        assert "<NUM>" in patterns[0].template
        assert "<*>" not in patterns[0].template

    def test_examples_keep_original_unmasked_lines(self):
        """Masking shapes templates only - examples stay the raw lines."""
        extractor = PatternExtractor(BigDialConfig(typed_masking=True))
        patterns = extractor.extract_patterns(self.IP_LINES)
        assert patterns[0].examples == self.IP_LINES

    def test_typed_masking_uuid_mac_ipv6_hex(self):
        """The remaining curated shapes each land as their own typed slot."""
        extractor = PatternExtractor(BigDialConfig(typed_masking=True))
        lines = [
            "session 123e4567-e89b-12d3-a456-426614174000 from aa:bb:cc:dd:ee:01 via fe80::1 commit deadbeefcafe",
            "session 00000000-0000-4000-8000-000000000000 from 00:11:22:33:44:55"
            " via 2001:db8::8a2e:370:7334 commit 0123456789abcdef",
        ]
        patterns = extractor.extract_patterns(lines)
        assert len(patterns) == 1
        template = patterns[0].template
        for slot in ("<UUID>", "<MAC>", "<IPV6>", "<HEX>"):
            assert slot in template

    def test_long_decimal_is_num_not_hex(self):
        """A pure-decimal token is NUM even at hex-plausible length."""
        extractor = PatternExtractor(BigDialConfig(typed_masking=True))
        lines = ["request took 12345678 ns", "request took 987654321 ns"]
        patterns = extractor.extract_patterns(lines)
        assert len(patterns) == 1
        assert "<NUM>" in patterns[0].template
        assert "<HEX>" not in patterns[0].template
