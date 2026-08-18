"""Unit tests for the host-application embedding seams.

A host app with its own config cascade and logging standard must be able to
drive logreducer with a minor code change and zero logreducer-side knowledge
of the host: config injection (LogReducer(config=...)), env-cascade config
(BigDialConfig.from_env), and host-owned logging (own_sinks=False).
"""

import pytest

from logreducer import BigDialConfig, LogReducer, OutputFormat, setup_logging


class TestConfigInjection:
    def test_injected_config_wins_over_preset(self):
        cfg = BigDialConfig(max_memory_gb=0.25, max_patterns=42, drain_similarity=0.33)
        reducer = LogReducer(level="standard", config=cfg)
        assert reducer.config.max_patterns == 42
        assert reducer.config.drain_similarity == 0.33

    def test_injected_config_is_copied_not_mutated(self):
        cfg = BigDialConfig(max_patterns=42)
        LogReducer(config=cfg, max_patterns=99)
        assert cfg.max_patterns == 42  # caller's object untouched

    def test_kwargs_apply_on_top_of_injected_config(self):
        cfg = BigDialConfig(max_patterns=42)
        reducer = LogReducer(config=cfg, max_patterns=99)
        assert reducer.config.max_patterns == 99

    def test_unknown_kwarg_raises(self):
        with pytest.raises(ValueError, match="max_paterns"):
            LogReducer(max_paterns=500)  # typo must fail fast, not silently no-op


class TestFromEnv:
    def test_reads_default_prefix(self, monkeypatch):
        monkeypatch.setenv("LOGREDUCER_MAX_PATTERNS", "77")
        monkeypatch.setenv("LOGREDUCER_ENABLE_LOGGING", "true")
        monkeypatch.setenv("LOGREDUCER_OUTPUT_FORMAT", "jsonl")
        cfg = BigDialConfig.from_env()
        assert cfg.max_patterns == 77
        assert cfg.enable_logging is True
        assert cfg.output_format is OutputFormat.JSONL

    def test_cascade_prefixed_wins_over_bare(self, monkeypatch):
        monkeypatch.setenv("DFE_MAX_PATTERNS", "11")
        monkeypatch.setenv("LOGREDUCER_MAX_PATTERNS", "22")
        cfg = BigDialConfig.from_env("DFE", "LOGREDUCER")
        assert cfg.max_patterns == 11

    def test_cascade_falls_back_to_bare(self, monkeypatch):
        monkeypatch.setenv("LOGREDUCER_MAX_PATTERNS", "22")
        cfg = BigDialConfig.from_env("DFE", "LOGREDUCER")
        assert cfg.max_patterns == 22

    def test_optional_field_accepts_none(self, monkeypatch):
        monkeypatch.setenv("LOGREDUCER_FUZZY_THRESHOLD", "none")
        cfg = BigDialConfig.from_env()
        assert cfg.fuzzy_threshold is None

    def test_optional_int_field_coerces(self, monkeypatch):
        monkeypatch.setenv("LOGREDUCER_MAX_CLUSTERS", "5000")
        cfg = BigDialConfig.from_env()
        assert cfg.max_clusters == 5000

    def test_bool_field_typed_masking_coerces(self, monkeypatch):
        monkeypatch.setenv("LOGREDUCER_TYPED_MASKING", "true")
        cfg = BigDialConfig.from_env()
        assert cfg.typed_masking is True

    def test_unset_fields_keep_defaults(self):
        cfg = BigDialConfig.from_env()
        assert cfg.max_patterns == BigDialConfig().max_patterns


class TestHostOwnedLogging:
    def test_own_sinks_false_flows_records_to_host_handlers(self):
        """The embedding seam: logreducer registers nothing; the host's own
        loguru handler receives logreducer's records (which are filtered by
        the caller's module name, so they must originate inside the package -
        drive them via a real reduce())."""
        from loguru import logger

        from logreducer import logging_config

        reducer = LogReducer(level="standard", mode="pattern", enable_logging=True)
        setup_logging(enable=True, own_sinks=False, console=True, log_file="ignored-when-host-owned.log")
        try:
            assert logging_config._HANDLER_IDS == []  # nothing registered by us
            captured: list[str] = []
            host_id = logger.add(lambda m: captured.append(str(m)), filter="logreducer")
            try:
                reducer.reduce(["ERROR a", "ERROR a", "INFO b"])
            finally:
                logger.remove(host_id)
            assert captured, "logreducer records did not reach the host handler"
        finally:
            setup_logging(enable=False)  # restore the library default
