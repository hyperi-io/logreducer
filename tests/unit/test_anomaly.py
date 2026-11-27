"""
Unit tests for anomaly detection module
"""

import random
import string
import tracemalloc

import pytest
from sklearn.feature_extraction.text import HashingVectorizer

from logreducer import anomaly
from logreducer.anomaly import HASHED_FEATURES, AnomalyDetector, _scored_columns


class TestAnomalyDetector:
    """Test cases for AnomalyDetector"""

    def test_initialization_default(self):
        """Test anomaly detector initialization with defaults"""
        detector = AnomalyDetector()

        assert detector.contamination == 0.1
        assert hasattr(detector, "enabled")

    def test_initialization_custom_contamination(self):
        """Test anomaly detector initialization with custom contamination"""
        detector = AnomalyDetector(contamination=0.05)

        assert detector.contamination == 0.05

    def test_sklearn_unavailable(self, monkeypatch):
        """Test behavior when sklearn is unavailable"""
        monkeypatch.setattr(anomaly, "SKLEARN_AVAILABLE", False)
        detector = AnomalyDetector()

        assert not detector.enabled

        lines = ["Test line 1", "Test line 2"]
        anomalies, normal = detector.detect_anomalies(lines)

        # Should return all lines as normal when sklearn unavailable
        assert anomalies == []
        assert normal == lines

    def test_detect_anomalies_empty_input(self):
        """Test anomaly detection with empty input"""
        detector = AnomalyDetector()

        anomalies, normal = detector.detect_anomalies([])

        assert anomalies == []
        assert normal == []

    def test_detect_anomalies_insufficient_data(self):
        """Test anomaly detection with insufficient data (less than 10 lines)"""
        detector = AnomalyDetector()

        lines = ["Line 1", "Line 2", "Line 3", "Line 4", "Line 5"]

        anomalies, normal = detector.detect_anomalies(lines)

        # Should return all as normal when less than 10 lines
        assert anomalies == []
        assert normal == lines

    def test_lines_sharing_unusual_terms_are_anomalies(self):
        routine = [f"INFO GET /health 200 req={i}" for i in range(300)]
        unusual = [f"NOTICE rotated keys for tenant t{n} using vault backend" for n in range(5)]

        anomalies, normal = AnomalyDetector().detect_anomalies(routine + unusual)

        assert set(unusual) <= set(anomalies)
        assert len(anomalies) + len(normal) == len(routine) + len(unusual)

    def test_memory_does_not_follow_the_distinct_terms(self):
        """A vocabulary of 300K distinct n-grams cost about 80x the input, hashed columns about 14x."""
        rng = random.Random(3)
        words = ["".join(rng.choice(string.ascii_lowercase) for _ in range(8)) for _ in range(200_000)]
        lines = [" ".join(words[row * 100 : row * 100 + 100]) for row in range(2000)]

        tracemalloc.start()
        try:
            AnomalyDetector().detect_anomalies(lines)
            peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()

        assert peak < 30 * sum(map(len, lines))

    def test_no_shared_term_leaves_every_line_normal(self):
        # The one term is in every line, so no column separates them.
        lines = ["same words here"] * 15

        assert AnomalyDetector().detect_anomalies(lines) == ([], lines)

    @pytest.mark.parametrize(
        ("lines", "scored"),
        [
            pytest.param([f"alpha beta req{i}" for i in range(200)], 0, id="every-line-term-and-one-line-ids-dropped"),
            pytest.param([f"w{i % 50} req{i}" for i in range(200)], 20, id="capped-at-a-tenth-of-the-lines"),
            pytest.param([f"w{i % 5} req{i}" for i in range(200)], 5, id="shared-terms-kept"),
        ],
    )
    def test_scored_columns(self, lines, scored):
        counts = HashingVectorizer(
            n_features=HASHED_FEATURES, ngram_range=(1, 3), alternate_sign=False, norm=None
        ).transform(lines)

        assert len(_scored_columns(counts, len(lines))) == scored

    def test_detect_anomalies_real_sklearn_if_available(self):
        """Test with real sklearn if available"""
        detector = AnomalyDetector()

        if not detector.enabled:
            pytest.skip("sklearn not available")

        # Create lines with clear patterns and one anomaly
        normal_pattern = "INFO User logged in successfully"
        lines = [normal_pattern] * 8  # Repeat normal pattern
        lines.extend(
            [
                "ERROR Critical system failure with unexpected behavior",  # Anomaly
                "INFO User logged out successfully",  # Similar to normal
            ]
        )

        anomalies, normal = detector.detect_anomalies(lines)

        # Should process without error
        assert isinstance(anomalies, list)
        assert isinstance(normal, list)
        assert len(anomalies) + len(normal) == len(lines)
