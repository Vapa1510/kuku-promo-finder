"""
Independent LLM-as-a-Judge Module
=================================
Performs independent second-pass editorial evaluation of promo candidates.
Verifies retention potential, curiosity gap, and checks whether narrative
tension was prematurely resolved before the clip ends.
"""

import json
import os
import re
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, Any

from .models import PromoCandidate, JudgeEvaluation
from .config import PromoFinderConfig, DEFAULT_CONFIG
from .storage import CacheManager

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    genai = None
    types = None
    GENAI_AVAILABLE = False


RESOLUTION_PATTERNS = [
    re.compile(r"\bapologiz(?:e|ed|ing)\b", re.I),
    re.compile(r"\bforgiv(?:e|en|ing)\b", re.I),
    re.compile(r"\breconcil(?:e|ed|iation)\b", re.I),
    re.compile(r"\bsafe now\b", re.I),
    re.compile(r"\ball is well\b", re.I),
    re.compile(r"\bhappily\b", re.I),
    re.compile(r"\brelief\b", re.I),
    re.compile(r"\blaughed together\b", re.I),
]


class BaseJudge(ABC):
    """Abstract interface for independent editorial judges."""

    @abstractmethod
    def judge(self, candidate: PromoCandidate) -> JudgeEvaluation:
        """Independently evaluate promo candidate from an editorial perspective."""
        pass


class RuleBasedJudge(BaseJudge):
    """
    Deterministic editorial judge.
    Checks tension sustainability, curiosity gap, and premature resolution leaks.
    """

    def __init__(self, config: PromoFinderConfig = DEFAULT_CONFIG):
        self.config = config

    def judge(self, candidate: PromoCandidate) -> JudgeEvaluation:
        events = candidate.events
        if not events:
            return JudgeEvaluation(
                candidate_id=candidate.candidate_id,
                judge_score=1.0,
                judge_verdict="REJECT",
                strengths="None",
                weaknesses="Empty candidate segment",
                comparative_notes="Cannot be used.",
                resolution_leaked=False,
            )

        closing_cutoff = max(candidate.start_time, candidate.end_time - 3.0)
        closing_events = [ev for ev in events if ev.end >= closing_cutoff] or events[-1:]
        closing_text = " ".join(f"{ev.text} {ev.tone or ''}" for ev in closing_events)

        # Check for premature resolution leak
        resolution_leaked = any(pat.search(closing_text) for pat in RESOLUTION_PATTERNS)

        base_score = 6.0

        # Hook presence
        if candidate.hook_signals:
            base_score += min(1.5, len(candidate.hook_signals) * 0.5)

        # Cliffhanger ending check
        last_ev = events[-1]
        if last_ev.event_type == "DIALOGUE":
            if last_ev.text.strip().endswith("?"):
                base_score += 1.5
            elif last_ev.text.strip().endswith("!"):
                base_score += 1.0
            else:
                base_score += 0.5
        elif last_ev.event_type in ("ACTION", "SOUND_FX", "CAMERA"):
            base_score += 0.8

        # Emotional stakes
        if candidate.emotional_signals:
            base_score += min(1.2, len(candidate.emotional_signals) * 0.4)

        # Duration appropriateness (sweet spot 25s - 50s)
        if 25.0 <= candidate.duration <= 50.0:
            base_score += 0.5
        elif candidate.duration < 22.0 or candidate.duration > 58.0:
            base_score -= 0.5

        # Penalty for premature resolution leak
        if resolution_leaked:
            base_score -= 3.0
            weaknesses = "Tension prematurely resolves near the end; diminishes curiosity gap."
        else:
            weaknesses = "Pacing could be tightened slightly in middle transition."

        judge_score = round(min(10.0, max(1.0, base_score)), 1)

        # Verdict
        if resolution_leaked or judge_score < 5.0:
            verdict = "REJECT"
        elif judge_score >= 8.0:
            verdict = "STRONG"
        elif judge_score >= 6.5:
            verdict = "GOOD"
        else:
            verdict = "BORDERLINE"

        strengths = (
            f"Strong dramatic momentum with {len(candidate.hook_signals)} detected narrative hooks "
            f"and high-stakes dialogue."
        )
        comparative_notes = f"Ranked with editorial score {judge_score:.1f} and verdict {verdict}."

        return JudgeEvaluation(
            candidate_id=candidate.candidate_id,
            judge_score=judge_score,
            judge_verdict=verdict,
            strengths=strengths,
            weaknesses=weaknesses,
            comparative_notes=comparative_notes,
            resolution_leaked=resolution_leaked,
        )


class LLMJudge(BaseJudge):
    """
    Independent LLM-as-a-Judge using google.genai.Client.
    Uses prompts/llm_judge_v1.txt in an isolated evaluation pass.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-3.5-flash",
        config: PromoFinderConfig = DEFAULT_CONFIG,
        cache_manager: Optional[CacheManager] = None,
        prompt_path: Optional[str] = None,
    ):
        self.config = config
        self.model_name = model_name
        self.fallback = RuleBasedJudge(config=config)
        self.cache_manager = cache_manager or CacheManager(config.cache_dir)

        if prompt_path and Path(prompt_path).exists():
            with open(prompt_path, "r", encoding="utf-8") as f:
                self.prompt_template = f.read()
        else:
            default_p = Path(__file__).resolve().parent.parent / "prompts" / "llm_judge_v1.txt"
            if default_p.exists():
                with open(default_p, "r", encoding="utf-8") as f:
                    self.prompt_template = f.read()
            else:
                self.prompt_template = "Judge candidate {candidate_id}:\n{segment_text}"

        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        self.client = None
        if GENAI_AVAILABLE and self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key, http_options={'api_version': 'v1beta'})
            except Exception:
                self.client = None

    def judge(self, candidate: PromoCandidate) -> JudgeEvaluation:
        segment_text = candidate.summary_text()
        cache_key = self.cache_manager.generate_key(
            candidate_id=candidate.candidate_id,
            text=segment_text,
            model_name=self.model_name,
            prompt_version="judge_v1",
        )

        cached_data = self.cache_manager.get(cache_key)
        if cached_data:
            try:
                return JudgeEvaluation.model_validate(cached_data)
            except Exception:
                pass

        if not self.client:
            res = self.fallback.judge(candidate)
            self.cache_manager.set(cache_key, res.model_dump())
            return res

        prompt = self.prompt_template.format(
            candidate_id=candidate.candidate_id,
            episode_number=candidate.episode_number,
            start_ts=candidate.start_display,
            end_ts=candidate.end_display,
            duration=candidate.duration,
            segment_text=segment_text,
        )

        for attempt in range(self.config.max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=self.config.temperature,
                        response_mime_type="application/json",
                    ),
                )
                raw_text = response.text or "{}"
                cleaned_text = re.sub(r"^```(?:json)?\s*", "", raw_text.strip(), flags=re.I)
                cleaned_text = re.sub(r"\s*```$", "", cleaned_text.strip())
                data = json.loads(cleaned_text)

                evaluation = JudgeEvaluation.model_validate(data)
                self.cache_manager.set(cache_key, evaluation.model_dump())
                return evaluation
            except Exception as e:
                if attempt == self.config.max_retries - 1:
                    fallback_res = self.fallback.judge(candidate)
                    fallback_res.weaknesses += f" (LLM judge failed: {str(e)})"
                    self.cache_manager.set(cache_key, fallback_res.model_dump())
                    return fallback_res
                time.sleep(self.config.retry_delay_seconds)

        return self.fallback.judge(candidate)
