"""
Advanced Promo Finder Package
=============================
Hybrid AI promotional clip discovery and ranking system.
"""

from .config import PromoFinderConfig, DEFAULT_CONFIG
from .models import (
    ScreenplayEvent,
    Scene,
    Episode,
    PromoSegment,
    PromoCandidate,
    CandidateEvaluation,
    JudgeEvaluation,
    FinalPromoResult,
    HumanReviewRecord,
)
from .normalizer import normalize_timestamp, format_timestamp, normalize_label
from .parser import parse_episode, load_all_episodes
from .detector import detect_candidates, detect_all_candidates
from .heuristics import score_events_heuristics, filter_top_candidates
from .evaluator import GeminiEvaluator, RuleBasedEvaluator
from .judge import LLMJudge, RuleBasedJudge
from .evidence_validator import validate_candidate_evidence
from .ranker import rank_and_deduplicate


def run_pipeline(*args, **kwargs):
    """Lazy import of run_pipeline."""
    from .pipeline import run_pipeline as _rp
    return _rp(*args, **kwargs)


__version__ = "2.0.0"

__all__ = [
    "PromoFinderConfig",
    "DEFAULT_CONFIG",
    "ScreenplayEvent",
    "Scene",
    "Episode",
    "PromoSegment",
    "PromoCandidate",
    "CandidateEvaluation",
    "JudgeEvaluation",
    "FinalPromoResult",
    "HumanReviewRecord",
    "normalize_timestamp",
    "format_timestamp",
    "normalize_label",
    "parse_episode",
    "load_all_episodes",
    "detect_candidates",
    "detect_all_candidates",
    "score_events_heuristics",
    "filter_top_candidates",
    "GeminiEvaluator",
    "RuleBasedEvaluator",
    "LLMJudge",
    "RuleBasedJudge",
    "validate_candidate_evidence",
    "rank_and_deduplicate",
    "run_pipeline",
]
