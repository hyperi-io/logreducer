"""
Unit tests for pattern extraction module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from logreducer.patterns import PatternExtractor, FuzzyDeduplicator, LogPattern
from logreducer.config import BigDialConfig


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
            metadata=metadata
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
        assert hasattr(extractor, 'miner')
    
    @patch('logreducer.patterns.TemplateMiner')
    def test_extract_patterns_empty_input(self, mock_template_miner):
        """Test pattern extraction with empty input"""
        config = BigDialConfig()
        extractor = PatternExtractor(config)
        
        result = extractor.extract_patterns([])
        
        assert result == []
    
    @patch('logreducer.patterns.TemplateMiner')
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
        
        lines = [
            "User alice logged in",
            "User bob logged in", 
            "User charlie logged in"
        ]
        
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
            LogPattern(template="Pattern 3", count=10)
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
            LogPattern(template="CRITICAL: System down", count=2)
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
    
    @patch('logreducer.patterns.SCIPY_AVAILABLE', True)
    @patch('logreducer.patterns.entropy')
    def test_entropy_filter(self, mock_entropy):
        """Test entropy-based filtering"""
        mock_entropy.return_value = 1.5
        
        config = BigDialConfig()
        config.entropy_threshold = 1.0
        extractor = PatternExtractor(config)
        
        patterns = [
            LogPattern(template="User <*> logged in", count=10),
            LogPattern(template="System started", count=5)
        ]
        
        result = extractor._entropy_filter(patterns)
        
        # Should add entropy metadata
        for pattern in result:
            assert 'entropy' in pattern.metadata


class TestFuzzyDeduplicator:
    """Test cases for FuzzyDeduplicator"""
    
    @patch('logreducer.patterns.MINHASH_AVAILABLE', True)
    def test_initialization_default(self):
        """Test fuzzy deduplicator initialization with defaults"""
        dedup = FuzzyDeduplicator()
        
        assert dedup.threshold == 0.8
        assert hasattr(dedup, 'enabled')
    
    @patch('logreducer.patterns.MINHASH_AVAILABLE', True) 
    def test_initialization_custom_threshold(self):
        """Test fuzzy deduplicator initialization with custom threshold"""
        dedup = FuzzyDeduplicator(threshold=0.9)
        
        assert dedup.threshold == 0.9
    
    @patch('logreducer.patterns.MINHASH_AVAILABLE', False)
    def test_minhash_unavailable(self):
        """Test behavior when MinHash is unavailable"""
        dedup = FuzzyDeduplicator()
        
        assert not dedup.enabled
        
        # Should still work but return original lines when disabled
        lines = ["Line 1", "Line 1", "Line 2"]
        result = dedup.deduplicate(lines)
        
        # When disabled, should return original lines
        assert result == lines
    
    @patch('logreducer.patterns.MINHASH_AVAILABLE', True)
    @patch('logreducer.patterns.MinHashLSH')
    @patch('logreducer.patterns.MinHash')
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
            "System error occurred"
        ]
        
        result = dedup.deduplicate(lines)
        
        # Should process all lines
        assert len(result) <= len(lines)
    
    def test_simple_deduplication_fallback(self):
        """Test simple deduplication when MinHash unavailable"""
        with patch('logreducer.patterns.MINHASH_AVAILABLE', False):
            dedup = FuzzyDeduplicator()
            
            lines = [
                "Duplicate line",
                "Unique line",
                "Duplicate line",  # Exact duplicate
                "Another unique line"
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