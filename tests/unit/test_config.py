"""
Unit tests for configuration module
"""

import pytest

from logreducer import LogReducer
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

        assert config.max_memory_gb == 1.0
        assert config.dedup_cache_size == 100000
        assert config.hash_algorithm == "xxhash"
        assert config.drain_similarity == 0.4
        assert config.examples_per_pattern == 3

    def test_custom_config(self):
        """Test custom configuration values"""
        config = BigDialConfig(max_memory_gb=2.0, drain_similarity=0.3)

        assert config.max_memory_gb == 2.0
        assert config.drain_similarity == 0.3
        # Default values should still be present
        assert config.examples_per_pattern == 3

    def test_typed_masking_defaults_off(self):
        """Typed masking is opt-in; default behaviour stays unmasked."""
        assert BigDialConfig().typed_masking is False

    def test_post_init_memory_adjustment(self):
        """Test that __post_init__ adjusts memory if too high"""
        # This will depend on system memory, so we test behavior
        config = BigDialConfig(max_memory_gb=999999.0)  # Unrealistic high value

        # Should be adjusted down based on available memory
        assert config.max_memory_gb < 999999.0


class TestGetPresetConfig:
    """Test get_preset_config function"""

    def test_standard_preset(self):
        """Test standard preset configuration"""
        config = get_preset_config(ProcessingLevel.STANDARD)

        assert isinstance(config, BigDialConfig)
        assert config.max_memory_gb == 0.5
        assert config.max_patterns == 500
        assert config.examples_per_pattern == 2
        assert config.fuzzy_threshold is None  # Disabled for speed

    def test_enhanced_preset(self):
        """Test enhanced preset configuration"""
        config = get_preset_config(ProcessingLevel.ENHANCED)

        assert isinstance(config, BigDialConfig)
        assert config.max_memory_gb == 1.0
        assert config.max_patterns == 1000
        assert config.examples_per_pattern == 3
        assert config.fuzzy_threshold == 0.8

    def test_maximum_preset(self):
        """Test maximum preset configuration"""
        config = get_preset_config(ProcessingLevel.MAXIMUM)

        assert isinstance(config, BigDialConfig)
        assert config.max_memory_gb == 2.0
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

        # Pattern count should increase
        assert standard.max_patterns < enhanced.max_patterns < maximum.max_patterns


OUT_OF_RANGE = [
    ("dedup_cache_size", 0),
    ("temporal_window_minutes", 0),
    ("max_patterns", 0),
    ("max_patterns", -1),
    ("examples_per_pattern", 0),
    ("max_clusters", 0),
    ("anomaly_max_rows", 0),
    ("max_memory_gb", 0),
    ("max_memory_gb", -1.0),
    ("max_memory_gb", float("nan")),
    ("max_memory_gb", float("inf")),
    ("drain_similarity", 1.5),
    ("fuzzy_threshold", 0.0),
    ("anomaly_contamination", 0.9),
]


class TestOutOfRangeValues:
    """Values that used to crash a run later, or silently empty its output."""

    @pytest.mark.parametrize(("field", "value"), OUT_OF_RANGE)
    def test_dataclass_rejects(self, field, value):
        with pytest.raises(ValueError, match=field):
            BigDialConfig(**{field: value})

    @pytest.mark.parametrize(("field", "value"), OUT_OF_RANGE)
    def test_reducer_override_rejects(self, field, value):
        with pytest.raises(ValueError, match=field):
            LogReducer(**{field: value})


class TestFromEnvErrors:
    @pytest.mark.parametrize(
        ("variable", "raw", "expected"),
        [
            ("LOGREDUCER_MAX_PATTERNS", "abc", "LOGREDUCER_MAX_PATTERNS='abc'"),
            ("LOGREDUCER_ENABLE_LOGGING", "treu", "LOGREDUCER_ENABLE_LOGGING='treu'"),
            ("LOGREDUCER_MAX_PATTERNS", "0", "max_patterns"),
        ],
    )
    def test_bad_value_names_the_variable(self, monkeypatch, variable, raw, expected):
        monkeypatch.setenv(variable, raw)
        with pytest.raises(ValueError, match=expected.replace("'", ".")):
            BigDialConfig.from_env()
