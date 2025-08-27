"""
Anomaly detection utilities
"""

from typing import List, Tuple, Optional
import numpy as np
from loguru import logger

# Try optional imports
try:
    from sklearn.ensemble import IsolationForest
    from sklearn.feature_extraction.text import TfidfVectorizer

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


class AnomalyDetector:
    """Detect anomalous log lines"""

    def __init__(self, contamination: float = 0.1):
        self.contamination = contamination
        self.enabled = SKLEARN_AVAILABLE

        if not self.enabled:
            logger.warning("scikit-learn not available, anomaly detection disabled")

    def detect_anomalies(self, lines: List[str]) -> Tuple[List[str], List[str]]:
        """
        Separate anomalous and normal lines

        Returns:
            (anomalous_lines, normal_lines)
        """
        if not self.enabled or len(lines) < 10:
            return [], lines

        # Vectorize
        vectorizer = TfidfVectorizer(
            max_features=min(1000, len(lines) // 10),
            ngram_range=(1, 3),
            max_df=0.9,
            min_df=2 if len(lines) > 100 else 1,
        )

        try:
            X = vectorizer.fit_transform(lines).toarray()
        except:
            return [], lines

        # Detect anomalies
        iso_forest = IsolationForest(
            contamination=self.contamination, random_state=42, n_estimators=100
        )

        labels = iso_forest.fit_predict(X)
        scores = iso_forest.score_samples(X)

        # Separate
        anomalous = [line for line, label in zip(lines, labels) if label == -1]
        normal = [line for line, label in zip(lines, labels) if label == 1]

        # Sort by anomaly score
        anomaly_with_scores = [
            (line, score)
            for line, label, score in zip(lines, labels, scores)
            if label == -1
        ]
        anomaly_with_scores.sort(key=lambda x: x[1])

        anomalous = [line for line, _ in anomaly_with_scores]

        logger.info(f"Found {len(anomalous)} anomalies out of {len(lines)} lines")

        return anomalous, normal
