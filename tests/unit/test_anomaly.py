"""
Unit tests for anomaly detection module
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from logreducer.anomaly import AnomalyDetector


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

    @patch("logreducer.anomaly.SKLEARN_AVAILABLE", False)
    def test_sklearn_unavailable(self):
        """Test behavior when sklearn is unavailable"""
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

    @patch("logreducer.anomaly.SKLEARN_AVAILABLE", True)
    @patch("logreducer.anomaly.TfidfVectorizer")
    @patch("logreducer.anomaly.IsolationForest")
    def test_detect_anomalies_sufficient_data_mocked(self, mock_isolation_forest, mock_tfidf):
        """Test anomaly detection with mocked ML components"""
        # Mock TfidfVectorizer
        mock_vectorizer = Mock()
        mock_vectorizer.fit_transform.return_value.toarray.return_value = [
            [1, 0],
            [0, 1],
            [1, 1],
        ]
        mock_tfidf.return_value = mock_vectorizer

        # Mock IsolationForest
        mock_model = Mock()
        mock_model.fit.return_value = None
        mock_model.fit_predict.return_value = [1] * 10 + [-1]  # Most normal, 1 anomaly
        mock_model.score_samples.return_value = [0.1] * 11  # Dummy scores
        mock_isolation_forest.return_value = mock_model

        detector = AnomalyDetector()
        detector.enabled = True  # Force enable for test

        lines = [
            "Normal log line 1",
            "Normal log line 2",
            "Anomalous log line",
            "Another normal line",
            "Yet another normal line",
            "More normal content",
            "Regular operation log",
            "Standard system message",
            "Typical application log",
            "Usual process information",
            "Critical system failure unusual pattern",  # Should be anomaly
        ]

        anomalies, normal = detector.detect_anomalies(lines)

        # Verify results structure
        assert isinstance(anomalies, list)
        assert isinstance(normal, list)
        assert len(anomalies) + len(normal) == len(lines)

    @patch("logreducer.anomaly.SKLEARN_AVAILABLE", True)
    @patch("logreducer.anomaly.TfidfVectorizer")
    def test_detect_anomalies_vectorization_error(self, mock_tfidf):
        """Test error handling during vectorization"""
        # Mock vectorizer to raise exception
        mock_vectorizer = Mock()
        mock_vectorizer.fit_transform.side_effect = Exception("Vectorization failed")
        mock_tfidf.return_value = mock_vectorizer

        detector = AnomalyDetector()
        detector.enabled = True

        lines = ["Line " + str(i) for i in range(15)]  # Enough lines to trigger processing

        anomalies, normal = detector.detect_anomalies(lines)

        # Should handle error gracefully and return all as normal
        assert anomalies == []
        assert normal == lines

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
