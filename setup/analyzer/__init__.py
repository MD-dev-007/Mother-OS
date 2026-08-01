"""Heuristic folder analysis (no LLM)."""

from setup.analyzer.classifier import ClassificationResult, classify_folder, classify_tree
from setup.analyzer.confidence import (
    AUTO_THRESHOLD,
    CLARIFY_THRESHOLD,
    BucketedClassification,
    ClassificationBucket,
    apply_bucket,
    bucket_for_score,
)
from setup.analyzer.duplicates import DuplicateGroup, find_duplicates
from setup.analyzer.relationships import RelatedGroup, find_related_groups

__all__ = [
    "AUTO_THRESHOLD",
    "CLARIFY_THRESHOLD",
    "BucketedClassification",
    "ClassificationBucket",
    "ClassificationResult",
    "DuplicateGroup",
    "RelatedGroup",
    "apply_bucket",
    "bucket_for_score",
    "classify_folder",
    "classify_tree",
    "find_duplicates",
    "find_related_groups",
]
