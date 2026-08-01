from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple


class ClassificationBucket(str, Enum):
    """How confidently a folder was classified (drives clarifier / M4 routing)."""

    AUTO_CLASSIFY = "auto_classify"
    NEEDS_CLARIFICATION = "needs_clarification"
    UNKNOWN = "unknown"


AUTO_THRESHOLD = 0.85
CLARIFY_THRESHOLD = 0.50


def bucket_for_score(score: float) -> ClassificationBucket:
    if score >= AUTO_THRESHOLD:
        return ClassificationBucket.AUTO_CLASSIFY
    if score >= CLARIFY_THRESHOLD:
        return ClassificationBucket.NEEDS_CLARIFICATION
    return ClassificationBucket.UNKNOWN


@dataclass(frozen=True)
class BucketedClassification:
    entity_type: str
    confidence: float
    bucket: ClassificationBucket
    signals: List[str]
    top_guesses: List[Tuple[str, float]]
    entity_options_for_m4: List[str]

    def to_dict(self) -> dict:
        return {
            "entity_type": self.entity_type,
            "confidence": self.confidence,
            "bucket": self.bucket.value,
            "signals": list(self.signals),
            "top_guesses": [{"entity": e, "score": s} for e, s in self.top_guesses],
            "entity_options_for_m4": list(self.entity_options_for_m4),
        }


def apply_bucket(
    *,
    entity_type: str,
    confidence: float,
    signals: List[str],
    scores: List[Tuple[str, float]],
    all_entity_types: List[str],
) -> BucketedClassification:
    """
    Map a classification score to a bucket and M4 payload hints.

    - >= 0.85: AUTO_CLASSIFY
    - 0.50–0.84: NEEDS_CLARIFICATION with top 2 entity guesses
    - < 0.50: UNKNOWN with full entity list for M4
    """
    bucket = bucket_for_score(confidence)
    ranked = sorted(scores, key=lambda x: x[1], reverse=True)
    top_guesses = ranked[:2]

    if bucket == ClassificationBucket.UNKNOWN:
        options = list(all_entity_types)
    elif bucket == ClassificationBucket.NEEDS_CLARIFICATION:
        options = [e for e, _ in top_guesses]
        if entity_type and entity_type not in options:
            options.insert(0, entity_type)
        options = options[:2]
    else:
        options = [entity_type] if entity_type else []

    return BucketedClassification(
        entity_type=entity_type,
        confidence=confidence,
        bucket=bucket,
        signals=signals,
        top_guesses=top_guesses,
        entity_options_for_m4=options,
    )
