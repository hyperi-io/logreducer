"""
Unit tests for memory management module
"""

import pytest
from unittest.mock import Mock, patch
from logreducer.memory import MemoryMonitor, StreamingProcessor, BoundedDeduplicator


class TestMemoryMonitor:
    """Test MemoryMonitor class"""
    
    def test_initialization(self):
        """Test MemoryMonitor initialization"""
        monitor = MemoryMonitor(max_memory_gb=2.0)
        
        assert monitor.max_memory_gb == 2.0
        assert monitor.max_memory_bytes == 2.0 * 1024 * 1024 * 1024
        assert monitor.effective_limit == monitor.max_memory_bytes * 0.8
        assert monitor.safe_chunk_size >= 1000
    
    @patch('psutil.Process')
    def test_check_memory_safe(self, mock_process):
        """Test memory check when usage is safe"""
        mock_memory_info = Mock()
        mock_memory_info.rss = 500 * 1024 * 1024  # 500MB
        mock_process.return_value.memory_info.return_value = mock_memory_info
        
        monitor = MemoryMonitor(max_memory_gb=2.0)
        current_gb, is_safe = monitor.check_memory()
        
        assert is_safe is True
        assert current_gb < 1.0  # Less than 1GB
    
    @patch('logreducer.memory.gc.collect')
    @patch('logreducer.memory.psutil.Process')
    def test_check_memory_unsafe_with_gc(self, mock_process_class, mock_gc):
        """Test memory check when usage is unsafe, triggering GC"""
        # Need to account for calls during __init__ and check_memory
        mock_memory_info_init = Mock()
        mock_memory_info_init.rss = 500 * 1024 * 1024  # 500MB for init
        
        mock_memory_info_high = Mock()
        mock_memory_info_high.rss = 3 * 1024 * 1024 * 1024  # 3GB (triggers GC)
        
        mock_memory_info_low = Mock()
        mock_memory_info_low.rss = 500 * 1024 * 1024  # 500MB (after GC)
        
        # Mock process instance with calls: __init__, check_memory, check_memory_after_gc
        mock_process_instance = Mock()
        mock_process_instance.memory_info.side_effect = [
            mock_memory_info_init,   # Called during __init__
            mock_memory_info_high,   # First call in check_memory (triggers GC)
            mock_memory_info_low     # Second call in check_memory (after GC)
        ]
        mock_process_class.return_value = mock_process_instance
        
        monitor = MemoryMonitor(max_memory_gb=2.0)
        current_gb, is_safe = monitor.check_memory()
        
        mock_gc.assert_called_once()
        assert is_safe is True  # Should be safe after GC
    
    def test_estimate_file_strategy_full(self):
        """Test file strategy estimation for small files"""
        monitor = MemoryMonitor(max_memory_gb=2.0)
        
        # Small file (100MB)
        file_size = 100 * 1024 * 1024
        strategy = monitor.estimate_file_strategy(file_size)
        
        assert strategy == 'full'
    
    def test_estimate_file_strategy_chunked(self):
        """Test file strategy estimation for medium files"""
        monitor = MemoryMonitor(max_memory_gb=2.0)
        
        # Medium file (2GB)
        file_size = 2 * 1024 * 1024 * 1024
        strategy = monitor.estimate_file_strategy(file_size)
        
        assert strategy == 'chunked'
    
    def test_estimate_file_strategy_sampled(self):
        """Test file strategy estimation for large files"""
        monitor = MemoryMonitor(max_memory_gb=2.0)
        
        # Large file (20GB) 
        file_size = 20 * 1024 * 1024 * 1024
        strategy = monitor.estimate_file_strategy(file_size)
        
        assert strategy == 'sampled'


class TestStreamingProcessor:
    """Test StreamingProcessor class"""
    
    def test_initialization(self):
        """Test StreamingProcessor initialization"""
        monitor = MemoryMonitor(max_memory_gb=1.0)
        processor = StreamingProcessor(monitor)
        
        assert processor.memory_monitor == monitor
        assert processor.chunk_size == monitor.safe_chunk_size
    
    def test_read_file_streaming_full_strategy(self, small_log_file):
        """Test streaming read with full strategy"""
        monitor = MemoryMonitor(max_memory_gb=2.0)
        processor = StreamingProcessor(monitor)
        
        # Mock estimate_file_strategy to return 'full'
        monitor.estimate_file_strategy = Mock(return_value='full')
        
        lines = list(processor.read_file_streaming(str(small_log_file)))
        
        assert len(lines) == 10  # Should read all lines
        assert lines[0] == "2024-01-01 12:00:00 INFO Application started"
        assert "ERROR Database connection failed" in lines[2]
    
    def test_read_file_streaming_chunked_strategy(self, medium_log_file):
        """Test streaming read with chunked strategy"""
        monitor = MemoryMonitor(max_memory_gb=2.0)
        processor = StreamingProcessor(monitor)
        
        # Mock estimate_file_strategy to return 'chunked'
        monitor.estimate_file_strategy = Mock(return_value='chunked')
        
        lines = list(processor.read_file_streaming(str(medium_log_file)))
        
        assert len(lines) > 0  # Should read some lines
        # All lines should be non-empty strings
        assert all(isinstance(line, str) and len(line) > 0 for line in lines)
    
    def test_read_file_streaming_sampled_strategy(self, medium_log_file):
        """Test streaming read with sampled strategy"""
        monitor = MemoryMonitor(max_memory_gb=2.0)
        processor = StreamingProcessor(monitor)
        
        # Mock estimate_file_strategy to return 'sampled'
        monitor.estimate_file_strategy = Mock(return_value='sampled')
        
        lines = list(processor.read_file_streaming(str(medium_log_file)))
        
        # Should return sampled lines (likely fewer than total)
        assert len(lines) > 0
        assert len(lines) <= processor.chunk_size
        # All lines should be non-empty strings
        assert all(isinstance(line, str) and len(line) > 0 for line in lines)


class TestBoundedDeduplicator:
    """Test BoundedDeduplicator class"""
    
    def test_initialization_default_hash(self):
        """Test deduplicator initialization with default hash"""
        dedup = BoundedDeduplicator(max_cache_size=1000)
        
        assert dedup.max_cache_size == 1000
        assert len(dedup.seen_hashes) == 0
        assert len(dedup.seen_set) == 0
        assert dedup.stats['total'] == 0
        assert dedup.stats['unique'] == 0
        assert dedup.stats['duplicates'] == 0
    
    def test_initialization_xxhash(self):
        """Test deduplicator initialization with xxhash"""
        with patch('xxhash.xxh64') as mock_xxhash:
            mock_hash_obj = Mock()
            mock_hash_obj.hexdigest.return_value = "test_hash"
            mock_xxhash.return_value = mock_hash_obj
            
            dedup = BoundedDeduplicator(hash_algorithm="xxhash")
            test_result = dedup.hash_func("test")
            
            assert test_result == "test_hash"
    
    def test_initialization_fallback_hash(self):
        """Test deduplicator initialization with non-xxhash algorithm"""
        # Test with md5 algorithm (always available)
        dedup = BoundedDeduplicator(hash_algorithm="md5")
        
        # Should use md5
        test_hash = dedup.hash_func("test")
        assert isinstance(test_hash, str)
        assert len(test_hash) == 32  # MD5 hash length
        
        # Test that xxhash works if available
        try:
            import xxhash
            dedup_xxhash = BoundedDeduplicator(hash_algorithm="xxhash")
            xxhash_result = dedup_xxhash.hash_func("test")
            assert isinstance(xxhash_result, str)
            assert len(xxhash_result) > 0
        except ImportError:
            # xxhash not available, test fallback behavior
            dedup_fallback = BoundedDeduplicator(hash_algorithm="xxhash")
            fallback_result = dedup_fallback.hash_func("test")
            assert isinstance(fallback_result, str)
            assert len(fallback_result) == 32  # Should fall back to blake2b (16 bytes = 32 hex chars)
    
    def test_is_duplicate_new_line(self):
        """Test duplicate detection for new line"""
        dedup = BoundedDeduplicator(max_cache_size=100)
        
        is_dup = dedup.is_duplicate("new unique line")
        
        assert is_dup is False
        assert dedup.stats['total'] == 1
        assert dedup.stats['unique'] == 1
        assert dedup.stats['duplicates'] == 0
        assert len(dedup.seen_hashes) == 1
        assert len(dedup.seen_set) == 1
    
    def test_is_duplicate_existing_line(self):
        """Test duplicate detection for existing line"""
        dedup = BoundedDeduplicator(max_cache_size=100)
        
        line = "duplicate line"
        dedup.is_duplicate(line)  # First time
        is_dup = dedup.is_duplicate(line)  # Second time
        
        assert is_dup is True
        assert dedup.stats['total'] == 2
        assert dedup.stats['unique'] == 1
        assert dedup.stats['duplicates'] == 1
    
    def test_cache_size_limit(self):
        """Test that cache respects size limit"""
        dedup = BoundedDeduplicator(max_cache_size=3)
        
        # Add 5 unique lines (more than cache size)
        lines = [f"line {i}" for i in range(5)]
        for line in lines:
            dedup.is_duplicate(line)
        
        # Cache should be limited to 3 items
        assert len(dedup.seen_hashes) == 3
        assert len(dedup.seen_set) == 3
        assert dedup.stats['unique'] == 5  # All were unique when first seen
    
    def test_deduplicate_lines_iterator(self):
        """Test deduplicating lines from iterator"""
        dedup = BoundedDeduplicator(max_cache_size=100)
        
        input_lines = [
            "line 1",
            "line 2", 
            "line 1",  # duplicate
            "line 3",
            "line 2",  # duplicate
            "line 4"
        ]
        
        result = list(dedup.deduplicate_lines(iter(input_lines)))
        
        # Should return only unique lines in order of first appearance
        expected = ["line 1", "line 2", "line 3", "line 4"]
        assert result == expected
        
        # Stats should be correct
        assert dedup.stats['total'] == 6
        assert dedup.stats['unique'] == 4
        assert dedup.stats['duplicates'] == 2