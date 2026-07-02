"""
Anomaly detection utilities
"""

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

    def detect_anomalies(self, lines: list[str]) -> tuple[list[str], list[str]]:
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
            # Keep the TF-IDF matrix SPARSE - IsolationForest accepts sparse
            # input directly. Densifying (.toarray()) would allocate
            # n_lines x n_features x 8 bytes, which dwarfs the sparse matrix and
            # can blow the memory budget on a large unique-line set.
            X = vectorizer.fit_transform(lines)
        except ValueError:
            # Empty vocabulary (every term filtered by min_df/max_df) - nothing
            # to score, so treat all lines as normal rather than failing.
            return [], lines

        iso_forest = IsolationForest(contamination=self.contamination, random_state=42, n_estimators=100)
        labels = iso_forest.fit_predict(X)
        scores = iso_forest.score_samples(X)

        # One pass: split normal vs anomalous, collecting scores for the latter.
        normal: list[str] = []
        anomaly_with_scores: list[tuple[str, float]] = []
        for line, label, score in zip(lines, labels, scores, strict=False):
            if label == -1:
                anomaly_with_scores.append((line, score))
            else:
                normal.append(line)

        # Most anomalous first (IsolationForest scores: lower = more anomalous).
        anomaly_with_scores.sort(key=lambda pair: pair[1])
        anomalous = [line for line, _ in anomaly_with_scores]

        logger.info(f"Found {len(anomalous)} anomalies out of {len(lines)} lines")

        return anomalous, normal
