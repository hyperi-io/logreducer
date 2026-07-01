"""
Unit tests for configuration module
"""

import pytest

from logreducer.config import BigDialConfig, ProcessingLevel, ProcessingMode, get_preset_config


class TestProcessingLevel:
    """Test ProcessingLevel enum"""

    def test_processing_levels_exist(self):
        """Test that all processing levels are defined"""
        assert ProcessingLevel.STANDARD.value == "standard"
        assert ProcessingLevel.ENHANCED.value == "enhanced"
        assert ProcessingLevel.MAXIMUM.value == "maximum"

    def test_processing_level_from_string(self):
        """Test creating ProcessingLevel from string"""
        assert ProcessingLevel("standard") == ProcessingLevel.STANDARD
        assert ProcessingLevel("enhanced") == ProcessingLevel.ENHANCED
        assert ProcessingLevel("maximum") == ProcessingLevel.MAXIMUM


class TestProcessingMode:
    """Test ProcessingMode enum"""

    def test_processing_modes_exist(self):
        """Test that all processing modes are defined"""
        assert ProcessingMode.PATTERN.value == "pattern"
        assert ProcessingMode.ANOMALY.value == "anomaly"
        assert ProcessingMode.TEMPORAL.value == "temporal"
        assert ProcessingMode.HYBRID.value == "hybrid"

    def test_processing_mode_from_string(self):
        """Test creating ProcessingMode from string"""
        assert ProcessingMode("pattern") == ProcessingMode.PATTERN
        assert ProcessingMode("anomaly") == ProcessingMode.ANOMALY
        assert ProcessingMode("temporal") == ProcessingMode.TEMPORAL
        assert ProcessingMode("hybrid") == ProcessingMode.HYBRID


class TestBigDialConfig:
    """Test BigDialConfig dataclass"""

    def test_default_config(self):
        """Test default configuration values"""
        config = BigDialConfig()

        assert config.max_memory_gb == 2.0
        assert config.chunk_size == 50000
        assert config.dedup_cache_size == 100000
        assert config.hash_algorithm == "xxhash"
        assert config.drain_similarity == 0.4
        assert config.examples_per_pattern == 3

    def test_custom_config(self):
        """Test custom configuration values"""
        config = BigDialConfig(max_memory_gb=4.0, chunk_size=100000, drain_similarity=0.3)

        assert config.max_memory_gb == 4.0
        assert config.chunk_size == 100000
        assert config.drain_similarity == 0.3
        # Default values should still be present
        assert config.examples_per_pattern == 3

    def test_post_init_memory_adjustment(self):
        """Test that __post_init__ adjusts memory if too high"""
        # This will depend on system memory, so we test behavior
        config = BigDialConfig(max_memory_gb=999999.0)  # Unrealistic high value

        # Should be adjusted down based on available memory
        assert config.max_memory_gb < 999999.0

    def test_post_init_workers(self):
        """Test that __post_init__ sets n_workers if None"""
        config = BigDialConfig(n_workers=None)

        assert config.n_workers is not None
        assert isinstance(config.n_workers, int)
        assert config.n_workers > 0
        # Should be set to actual CPU count (no arbitrary limit)
        import multiprocessing as mp

        assert config.n_workers <= mp.cpu_count()


class TestGetPresetConfig:
    """Test get_preset_config function"""

    def test_standard_preset(self):
        """Test standard preset configuration"""
        config = get_preset_config(ProcessingLevel.STANDARD)

        assert isinstance(config, BigDialConfig)
        assert config.max_memory_gb == 1.0
        assert config.chunk_size == 100000
        assert config.max_patterns == 500
        assert config.examples_per_pattern == 2
        assert config.fuzzy_threshold is None  # Disabled for speed

    def test_enhanced_preset(self):
        """Test enhanced preset configuration"""
        config = get_preset_config(ProcessingLevel.ENHANCED)

        assert isinstance(config, BigDialConfig)
        assert config.max_memory_gb == 2.0
        assert config.chunk_size == 50000
        assert config.max_patterns == 1000
        assert config.examples_per_pattern == 3
        assert config.fuzzy_threshold == 0.8

    def test_maximum_preset(self):
        """Test maximum preset configuration"""
        config = get_preset_config(ProcessingLevel.MAXIMUM)

        assert isinstance(config, BigDialConfig)
        assert config.max_memory_gb == 4.0
        assert config.chunk_size == 25000
        assert config.max_patterns == 2000
        assert config.examples_per_pattern == 5
        assert config.fuzzy_threshold == 0.9

    def test_preset_progression(self):
        """Test that presets have logical progression"""
        standard = get_preset_config(ProcessingLevel.STANDARD)
        enhanced = get_preset_config(ProcessingLevel.ENHANCED)
        maximum = get_preset_config(ProcessingLevel.MAXIMUM)

        # Memory should increase
        assert standard.max_memory_gb < enhanced.max_memory_gb < maximum.max_memory_gb

        # Chunk size should decrease (more thorough processing)
        assert standard.chunk_size > enhanced.chunk_size > maximum.chunk_size

        # Pattern count should increase
        assert standard.max_patterns < enhanced.max_patterns < maximum.max_patterns
