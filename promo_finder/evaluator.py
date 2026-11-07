"""
Candidate Evaluator Module
==========================
Performs deep narrative evaluation of promotional candidates using either the
modern Google GenAI SDK (Gemini 2.5 Flash) or a deterministic, rule-based
narrative evaluator fallback for 100% offline reliability.
"""

import json
import os
import re
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

from .models import PromoCandidate, CandidateEvaluation
from .config import PromoFinderConfig, DEFAULT_CONFIG
from .evidence_validator import validate_candidate_evidence
from .storage import CacheManager
from .heuristics import (
    extract_matched_signals,
    HOOK_PATTERNS,
    CLIFFHANGER_PATTERNS,
    EMOTIONAL_PATTERNS,
)

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    genai = None
    types = None
    GENAI_AVAILABLE = False


class BaseEvaluator(ABC):
    """Abstract interface for candidate narrative evaluators."""

    @abstractmethod
    def evaluate(self, candidate: PromoCandidate) -> CandidateEvaluation:
        """Evaluate a promo candidate and return structured narrative scores."""
        pass


class RuleBasedEvaluator(BaseEvaluator):
    """
    Deterministic narrative evaluator.
    Evaluates hook impact in the first 3 seconds, unresolved cliffhanger in the final 3 seconds,
    emotional tension, standalone clarity, and boundary quality without requiring external APIs.
    """

    def __init__(self, config: PromoFinderConfig = DEFAULT_CONFIG):
        self.config = config

    def evaluate(self, candidate: PromoCandidate) -> CandidateEvaluation:
        events = candidate.events
        if not events:
            return CandidateEvaluation(
                candidate_id=candidate.candidate_id,
                hook_strength=1.0,
                cliffhanger_strength=1.0,
                narrative_clarity=1.0,
                conflict_and_stakes=1.0,
                emotional_pull=1.0,
                script_visual_potential=1.0,
                boundary_suitability=1.0,
                overall_score=1.0,
                editorial_verdict="REJECT",
            )

        start_time = candidate.start_time
        end_time = candidate.end_time
        opening_window = [ev for ev in events if ev.start <= start_time + 3.0]
        closing_window = [ev for ev in events if ev.end >= end_time - 3.0]

        # 1. Hook Strength: Calculated strictly from opening_events (ev.start <= start_time + 3.0)
        # If no hook in the first 3s, score stays at baseline (3.0-4.0)
        opening_text = " ".join(f"{ev.text} {ev.tone or ''}" for ev in opening_window)
        opening_hooks = extract_matched_signals(opening_text, HOOK_PATTERNS)
        opening_emos = extract_matched_signals(opening_text, EMOTIONAL_PATTERNS)

        hook_score = 3.5
        if any(ev.event_type == "DIALOGUE" for ev in opening_window):
            hook_score += 1.5
        if opening_hooks:
            hook_score += min(3.5, len(opening_hooks) * 1.5 + 1.0)
        if opening_emos:
            hook_score += min(1.5, len(opening_emos) * 0.8)
        if any(ev.tone for ev in opening_window):
            hook_score += 0.5
        hook_strength = min(10.0, max(1.0, round(hook_score, 1)))

        # 2. Cliffhanger Strength: Calculated strictly from closing_events (ev.end >= end_time - 3.0)
        # Punctuation and cutoff keywords outside the final 3s provide zero bonus.
        closing_text = " ".join(f"{ev.text} {ev.tone or ''}" for ev in closing_window)
        closing_cliffs = extract_matched_signals(closing_text, CLIFFHANGER_PATTERNS)

        last_dialogue = next((ev for ev in reversed(closing_window) if ev.event_type == "DIALOGUE"), None)
        cliff_score = 3.5 if last_dialogue else 2.5
        if last_dialogue:
            last_text = last_dialogue.text.strip()
            if last_text.endswith("?"):
                cliff_score += 3.0
            elif last_text.endswith("!"):
                cliff_score += 2.0
            elif any(w in last_text.lower() for w in ["never", "wait", "stop", "who are you", "why", "too late", "please", "leave", "swore", "loved", "hand", "marry"]):
                cliff_score += 2.0
            else:
                cliff_score += 1.0
        elif any(ev.event_type in ("ACTION", "SOUND_FX", "CAMERA") for ev in closing_window):
            cliff_score += 1.5

        if closing_cliffs:
            cliff_bonus = min(4.5, len(closing_cliffs) * 1.5 + (1.0 if any(w in closing_text.lower() for w in ["cliffhanger", "swells", "cut to black", "fade to black"]) else 0.0))
            cliff_score += cliff_bonus

        cliffhanger_strength = min(10.0, max(1.0, round(cliff_score, 1)))

        # 3. Narrative Clarity
        dialogue_events = [ev for ev in events if ev.event_type == "DIALOGUE"]
        char_set = {ev.character for ev in dialogue_events if ev.character}
        clarity_score = 6.0
        if 1 <= len(char_set) <= 3:
            clarity_score += 2.0  # clean, easy-to-follow dynamics
        elif len(char_set) > 4:
            clarity_score -= 1.0  # too many voices in 30s
        narrative_clarity = min(10.0, max(1.0, round(clarity_score, 1)))

        # 4. Conflict & Stakes
        conflict_score = 5.0
        if len(opening_hooks) >= 1 or len(candidate.hook_signals) >= 1:
            conflict_score += 1.5
        if len(candidate.emotional_signals) >= 2:
            conflict_score += 1.5
        if any(w in opening_text.lower() or w in closing_text.lower() for w in ["altar", "betray", "traitor", "poison", "murder", "duke", "chapel", "chains", "soldier", "explosion", "bomb"]):
            conflict_score += 1.5
        conflict_and_stakes = min(10.0, max(1.0, round(conflict_score, 1)))

        # 5. Emotional Pull
        emo_score = 5.0
        if candidate.emotional_signals:
            emo_score += min(3.5, len(candidate.emotional_signals) * 1.0)
        emotional_pull = min(10.0, max(1.0, round(emo_score, 1)))

        # 6. Script Visual Potential
        action_events = [ev for ev in events if ev.event_type == "ACTION"]
        camera_events = [ev for ev in events if ev.event_type == "CAMERA"]
        visual_score = 6.0 + min(2.5, len(action_events) * 0.4 + len(camera_events) * 0.2)
        script_visual_potential = min(10.0, max(1.0, round(visual_score, 1)))

        # 7. Boundary Suitability
        boundary_score = 8.0
        # If starts and ends with dialogue/action/camera
        if events[0].event_type in ("DIALOGUE", "ACTION") and events[-1].event_type in ("DIALOGUE", "ACTION", "SOUND_FX", "CAMERA"):
            boundary_score += 1.5
        boundary_suitability = min(10.0, max(1.0, round(boundary_score, 1)))

        # Weighted overall score based on config.weights
        w = self.config.weights
        overall = round(
            hook_strength * w.hook
            + cliffhanger_strength * w.cliffhanger
            + narrative_clarity * w.clarity
            + conflict_and_stakes * w.conflict
            + emotional_pull * w.emotion
            + script_visual_potential * w.visual
            + boundary_suitability * w.boundary,
            2
        )

        # Editorial verdict
        if overall >= 8.0 and hook_strength >= 6.5 and cliffhanger_strength >= 6.5:
            verdict = "STRONG"
        elif overall >= 6.5 and hook_strength >= 6.0 and cliffhanger_strength >= 6.0:
            verdict = "GOOD"
        elif overall >= 5.0:
            verdict = "BORDERLINE"
        else:
            verdict = "REJECT"

        hook_ev_ids = [ev.event_id for ev in opening_window] or [events[0].event_id]
        cliff_ev_ids = [ev.event_id for ev in closing_window] or [events[-1].event_id]

        # Generate dramatic title template
        promo_title, title_rationale = generate_promo_title(candidate)

        evaluation = CandidateEvaluation(
            candidate_id=candidate.candidate_id,
            hook_strength=hook_strength,
            cliffhanger_strength=cliffhanger_strength,
            narrative_clarity=narrative_clarity,
            conflict_and_stakes=conflict_and_stakes,
            emotional_pull=emotional_pull,
            script_visual_potential=script_visual_potential,
            boundary_suitability=boundary_suitability,
            overall_score=overall,
            hook_evidence_event_ids=hook_ev_ids,
            cliffhanger_evidence_event_ids=cliff_ev_ids,
            hook_explanation=f"Opens directly on {hook_ev_ids[0]} within first 3 seconds.",
            cliffhanger_explanation=f"Closes on {cliff_ev_ids[-1]} within final 3 seconds.",
            standalone_explanation=f"Presents clear conflict between {', '.join(sorted(list(char_set))) or 'characters'}.",
            promo_title=promo_title,
            title_rationale=title_rationale,
            editorial_verdict=verdict,
        )

        # Grounding & quote extraction
        res = validate_candidate_evidence(candidate, evaluation)
        evaluation.opening_quote = res.opening_quote
        evaluation.closing_quote = res.closing_quote
        evaluation.quality_flags = res.issues
        evaluation.hook_evidence_event_ids = res.validated_hook_ids
        evaluation.cliffhanger_evidence_event_ids = res.validated_cliff_ids

        return evaluation


class GeminiEvaluator(BaseEvaluator):
    """
    Primary LLM narrative evaluator using google.genai.Client.
    Uses prompt templates, structured output, disk caching, and graceful
    fallback to RuleBasedEvaluator on missing key or network unavailability.
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
        self.fallback = RuleBasedEvaluator(config=config)
        self.cache_manager = cache_manager or CacheManager(config.cache_dir)

        # Determine prompt template
        if prompt_path and Path(prompt_path).exists():
            with open(prompt_path, "r", encoding="utf-8") as f:
                self.prompt_template = f.read()
        else:
            default_p = Path(__file__).resolve().parent.parent / "prompts" / "candidate_evaluation_v1.txt"
            if default_p.exists():
                with open(default_p, "r", encoding="utf-8") as f:
                    self.prompt_template = f.read()
            else:
                self.prompt_template = "Evaluate candidate {candidate_id}:\n{segment_text}"

        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        self.client = None
        if GENAI_AVAILABLE and self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key, http_options={'api_version': 'v1beta'})
            except Exception:
                self.client = None

    def evaluate(self, candidate: PromoCandidate) -> CandidateEvaluation:
        # Check cache first
        segment_text = candidate.summary_text()
        cache_key = self.cache_manager.generate_key(
            candidate_id=candidate.candidate_id,
            text=segment_text,
            model_name=self.model_name,
            prompt_version="eval_v1",
        )

        cached_data = self.cache_manager.get(cache_key)
        if cached_data:
            try:
                return CandidateEvaluation.model_validate(cached_data)
            except Exception:
                pass

        # If LLM client is not configured, use fallback
        if not self.client:
            eval_res = self.fallback.evaluate(candidate)
            self.cache_manager.set(cache_key, eval_res.model_dump())
            return eval_res

        # Format prompt
        prompt = self.prompt_template.format(
            candidate_id=candidate.candidate_id,
            episode_number=candidate.episode_number,
            start_ts=candidate.start_display,
            end_ts=candidate.end_display,
            duration=candidate.duration,
            segment_text=segment_text,
        )

        # Call Gemini with retry
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
                # Clean possible markdown wrapping
                cleaned_text = re.sub(r"^```(?:json)?\s*", "", raw_text.strip(), flags=re.I)
                cleaned_text = re.sub(r"\s*```$", "", cleaned_text.strip())
                data = json.loads(cleaned_text)

                evaluation = CandidateEvaluation.model_validate(data)

                # Grounding and quote extraction
                val_res = validate_candidate_evidence(candidate, evaluation)
                evaluation.opening_quote = val_res.opening_quote
                evaluation.closing_quote = val_res.closing_quote
                evaluation.quality_flags = val_res.issues
                evaluation.hook_evidence_event_ids = val_res.validated_hook_ids
                evaluation.cliffhanger_evidence_event_ids = val_res.validated_cliff_ids

                self.cache_manager.set(cache_key, evaluation.model_dump())
                return evaluation
            except Exception as e:
                if attempt == self.config.max_retries - 1:
                    # Fallback to rule-based
                    fallback_res = self.fallback.evaluate(candidate)
                    fallback_res.quality_flags.append(f"LLM evaluation failed ({str(e)}), used offline fallback.")
                    self.cache_manager.set(cache_key, fallback_res.model_dump())
                    return fallback_res
                time.sleep(self.config.retry_delay_seconds)

        return self.fallback.evaluate(candidate)


def generate_promo_title(
    candidate: PromoCandidate,
    prompt_path: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Generate a compelling marketing promo title and rationale for a candidate.
    Uses curated dramatic templates marked with '[Provisional Title]'.
    """
    events = candidate.events
    dialogue_events = [ev for ev in events if ev.event_type == "DIALOGUE"]
    full_text = " ".join(f"{ev.text} {ev.tone or ''}" for ev in events).lower()

    if any(re.search(pat, full_text, re.I) for pat in [r"\bexplos", r"\bbomb\b", r"\bdetonat", r"\bfireball\b"]):
        title_base = "The Cathedral Breach"
        rationale = "Focuses on explosive confrontation and perilous defiance in the breached cathedral."
    elif any(re.search(pat, full_text, re.I) for pat in [r"\bpoison", r"\barsenic\b"]):
        title_base = "The Arsenic Secret"
        rationale = "Emphasizes deadly intrigue and poison conspiracy."
    elif any(re.search(pat, full_text, re.I) for pat in [r"\baccept my hand\b", r"\bpropos", r"\bmarry me\b", r"\bbe my wife\b", r"\bwedding ring\b", r"\bvows?\b"]):
        title_base = "The Secret Proposal"
        rationale = "Highlights unexpected marriage proposal and dramatic romantic alliance."
    elif any(re.search(pat, full_text, re.I) for pat in [r"\baltar\b", r"\bbetrothed\b", r"\bwedding\b"]):
        title_base = "The Altar Betrayal"
        rationale = "Anchored on high-stakes betrayal and humiliation at the wedding altar."
    elif any(re.search(pat, full_text, re.I) for pat in [r"\bbetray", r"\btraitor\b", r"\babandon", r"\bshackles\b", r"\bchains\b"]):
        title_base = "The Traitor's Stand"
        rationale = "Centers on bitter betrayal, accusations of treason, and defiance in chains."
    elif any(re.search(pat, full_text, re.I) for pat in [r"\bdukes?\b", r"\bduchess\b", r"\bnobility\b", r"\bscandal\b"]):
        title_base = "The Duke's Secret"
        rationale = "Centers on royal identity discovery and high society scandal."
    else:
        raw_char = next((ev.character for ev in dialogue_events if ev.character), "Juliana")
        clean_char = re.sub(r"^(?:LADY|LORD|THE|FORMER)\s+", "", raw_char, flags=re.I).title()
        title_base = f"{clean_char}'s Defiance"
        rationale = f"Captures pivotal dramatic stand by {clean_char}."

    title = f"[Provisional Title] {title_base}"
    return title, rationale
