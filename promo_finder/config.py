"""
Configuration settings for Advanced Promo Finder.
Provides typed settings, thresholds, scoring weights, and model parameters.
"""

import os
from pathlib import Path
from typing import Dict
from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv
    # Load .env from project root if present
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except Exception:
    pass


class ScoringWeights(BaseModel):
    """Weights for candidate narrative evaluation."""
    hook: float = 0.20
    cliffhanger: float = 0.20
    clarity: float = 0.15
    conflict: float = 0.15
    emotion: float = 0.10
    visual: float = 0.10
    boundary: float = 0.10


class QualityGates(BaseModel):
    """Hard promotional thresholds."""
    min_hook: float = 6.0
    min_cliffhanger: float = 6.0
    min_clarity: float = 5.0
    min_duration: float = 20.0
    max_duration: float = 60.0
    reject_resolution_leaked: bool = True


class PromoFinderConfig(BaseModel):
    """Central configuration for promo extraction and ranking."""
    # Duration constraints
    min_duration: float = 20.0
    max_duration: float = 60.0

    # Heuristic pre-filtering
    candidates_per_episode: int = 4
    include_exploratory_candidate: bool = True

    # Scoring weights & gates
    weights: ScoringWeights = Field(default_factory=ScoringWeights)
    gates: QualityGates = Field(default_factory=QualityGates)

    # Score reconciliation weights (Candidate Evaluator vs Independent Judge)
    evaluator_weight: float = 0.35
    judge_weight: float = 0.65

    # Diversity & Deduplication
    iou_threshold: float = 0.40
    max_per_episode: int = 2
    top_n: int = 30

    # Model settings
    gemini_model: str = "gemini-3.5-flash"
    judge_model: str = "gemini-3.5-flash"
    temperature: float = 0.2
    max_retries: int = 3
    retry_delay_seconds: float = 2.0

    # Caching & Storage
    cache_dir: str = ".cache"
    enable_cache: bool = True

    # Feature flags
    enable_llm: bool = False
    enable_multisegment: bool = False


# Default singleton instance
DEFAULT_CONFIG = PromoFinderConfig()
