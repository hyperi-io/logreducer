"""Anomaly detection utilities."""

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Fewer lines than this are returned unscored, all of them normal.
MIN_SCORED_LINES = 10

# Hashed n-gram columns. Hashing keeps no vocabulary, so memory follows the
# line count, not the number of distinct terms the lines carry.
HASHED_FEATURES = 2**20

# Scored columns: the most frequent hashed terms in at least two lines and at most this share of them.
MAX_SCORED_FEATURES = 1000
MAX_DOC_SHARE = 0.9

# Try optional imports
try:
    from sklearn.ensemble import IsolationForest
    from sklearn.feature_extraction.text import HashingVectorizer, TfidfTransformer

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


class AnomalyDetector:
    """Detect anomalous log lines."""

    def __init__(self, contamination: float = 0.1):
        self.contamination = contamination
        self.enabled = SKLEARN_AVAILABLE

        if not self.enabled:
            logger.warning("scikit-learn not available, anomaly detection disabled")

    def detect_anomalies(self, lines: list[str]) -> tuple[list[str], list[str]]:
        """Separate anomalous and normal lines.

        Returns:
            (anomalous_lines, normal_lines)
        """
        if not self.enabled or len(lines) < MIN_SCORED_LINES:
            return [], lines

        # The matrix stays sparse: densified it is lines x HASHED_FEATURES x 8 bytes.
        counts = HashingVectorizer(
            n_features=HASHED_FEATURES, ngram_range=(1, 3), alternate_sign=False, norm=None
        ).transform(lines)
        columns = _scored_columns(counts, len(lines))
        if columns.size == 0:
            # No term is shared by enough lines to score, so every line is normal.
            return [], lines
        X = TfidfTransformer().fit_transform(counts[:, columns])

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


def _scored_columns(counts: Any, line_count: int) -> np.ndarray:
    """Pick the hashed columns to score, as a vocabulary with ``min_df``, ``max_df`` and ``max_features`` would.

    A term in a single line, a request id say, isolates that line in one split, so it
    says nothing about how unusual the line is. A term in nearly every line separates none.
    """
    min_lines = 2 if line_count > 100 else 1
    doc_freq = counts.getnnz(axis=0)
    shared = np.flatnonzero((doc_freq >= min_lines) & (doc_freq <= MAX_DOC_SHARE * line_count))
    limit = min(MAX_SCORED_FEATURES, line_count // 10)
    if shared.size <= limit:
        return shared
    term_freq = np.asarray(counts[:, shared].sum(axis=0)).ravel()
    return np.sort(shared[np.argsort(-term_freq, kind="stable")[:limit]])
