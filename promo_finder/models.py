"""
Complete Pydantic Schemas for Screenplay Parsing, Promo Detection,
Evaluation, Editorial Judgment, and Ranking.
"""

from typing import Optional, List, Dict
from pydantic import BaseModel, Field

from .normalizer import format_timestamp


class ScreenplayEvent(BaseModel):
    """A single atomic screenplay event (dialogue, action, camera, SFX)."""
    event_id: str
    scene_id: int
    event_type: str  # DIALOGUE, ACTION, CAMERA, SOUND_FX
    character: Optional[str] = None
    tone: Optional[str] = None
    text: str = ""
    start: float  # seconds
    end: float  # seconds
    source_line: int = 0

    @property
    def duration(self) -> float:
        return round(self.end - self.start, 2)


class Scene(BaseModel):
    """A scene within an episode containing events."""
    scene_id: int
    heading: str
    start: float  # seconds
    end: float  # seconds
    events: List[ScreenplayEvent] = Field(default_factory=list)

    @property
    def duration(self) -> float:
        return round(self.end - self.start, 2)


class Episode(BaseModel):
    """A fully parsed episode with scenes and events."""
    episode_number: int
    logline: str = ""
    continuity_notes: str = ""
    scenes: List[Scene] = Field(default_factory=list)
    source_file: str = ""

    @property
    def total_duration(self) -> float:
        if not self.scenes:
            return 0.0
        return round(self.scenes[-1].end - self.scenes[0].start, 2)

    def get_all_events(self) -> List[ScreenplayEvent]:
        """Return all events across scenes in chronological order."""
        events: List[ScreenplayEvent] = []
        for sc in self.scenes:
            events.extend(sc.events)
        return events


class PromoSegment(BaseModel):
    """A continuous piece of audio/screenplay in a promo (1 per single clip, 2-3 in multi-segment)."""
    episode_number: int
    start_time: float
    end_time: float
    start_display: str
    end_display: str
    event_ids: List[str] = Field(default_factory=list)

    @property
    def duration(self) -> float:
        return round(self.end_time - self.start_time, 2)


class PromoCandidate(BaseModel):
    """A potential promotional clip candidate composed of one or more segments."""
    candidate_id: str
    episode_number: int
    start_time: float
    end_time: float
    segments: List[PromoSegment] = Field(default_factory=list)
    duration: float
    events: List[ScreenplayEvent] = Field(default_factory=list)
    heuristic_score: float = 0.0
    hook_signals: List[str] = Field(default_factory=list)
    cliffhanger_signals: List[str] = Field(default_factory=list)
    emotional_signals: List[str] = Field(default_factory=list)

    @property
    def start_display(self) -> str:
        return format_timestamp(self.start_time)

    @property
    def end_display(self) -> str:
        return format_timestamp(self.end_time)

    def summary_text(self) -> str:
        """Render screenplay events cleanly for evaluation."""
        lines: List[str] = []
        for ev in self.events:
            dur_str = f"[{ev.start:.2f}s - {ev.end:.2f}s]"
            if ev.event_type == "DIALOGUE":
                char_str = f"{ev.character}" + (f" ({ev.tone})" if ev.tone else "")
                lines.append(f"{dur_str} {ev.event_id} | {char_str}: \"{ev.text}\"")
            elif ev.event_type == "ACTION":
                lines.append(f"{dur_str} {ev.event_id} | ACTION: {ev.text}")
            elif ev.event_type == "CAMERA":
                lines.append(f"{dur_str} {ev.event_id} | CAMERA: {ev.text}")
            elif ev.event_type == "SOUND_FX":
                lines.append(f"{dur_str} {ev.event_id} | SFX: {ev.text}")
        return "\n".join(lines)


class CandidateEvaluation(BaseModel):
    """Detailed narrative evaluation produced by primary evaluator."""
    candidate_id: str
    hook_strength: float = Field(..., ge=0.0, le=10.0)
    cliffhanger_strength: float = Field(..., ge=0.0, le=10.0)
    narrative_clarity: float = Field(..., ge=0.0, le=10.0)
    conflict_and_stakes: float = Field(..., ge=0.0, le=10.0)
    emotional_pull: float = Field(..., ge=0.0, le=10.0)
    script_visual_potential: float = Field(..., ge=0.0, le=10.0)
    boundary_suitability: float = Field(..., ge=0.0, le=10.0)
    overall_score: float = Field(..., ge=0.0, le=10.0)

    # Grounding & Evidence
    hook_evidence_event_ids: List[str] = Field(default_factory=list)
    cliffhanger_evidence_event_ids: List[str] = Field(default_factory=list)
    hook_explanation: str = ""
    cliffhanger_explanation: str = ""
    standalone_explanation: str = ""
    promo_title: str = ""
    title_rationale: str = ""
    editorial_verdict: str = "GOOD"  # STRONG, GOOD, BORDERLINE, REJECT
    opening_quote: str = ""
    closing_quote: str = ""
    quality_flags: List[str] = Field(default_factory=list)


class JudgeEvaluation(BaseModel):
    """Independent editorial judgment from second-pass LLM or rule-based judge."""
    candidate_id: str
    judge_score: float = Field(..., ge=0.0, le=10.0)
    judge_verdict: str  # STRONG, GOOD, BORDERLINE, REJECT
    strengths: str = ""
    weaknesses: str = ""
    comparative_notes: str = ""
    resolution_leaked: bool = False


class FinalPromoResult(BaseModel):
    """Final ranked promo ready for presentation, export, and review."""
    rank: int = 0
    candidate_id: str
    episode_number: int
    start_time: float
    end_time: float
    start_display: str
    end_display: str
    duration_seconds: float
    final_score: float
    candidate_score: float
    judge_score: float
    scores: Dict[str, float] = Field(default_factory=dict)
    editorial_verdict: str = ""
    judge_verdict: str = ""
    promo_title: str = ""
    hook_explanation: str = ""
    cliffhanger_explanation: str = ""
    standalone_explanation: str = ""
    opening_quote: str = ""
    closing_quote: str = ""
    strengths: str = ""
    weaknesses: str = ""
    segments: List[PromoSegment] = Field(default_factory=list)
    events_summary: List[str] = Field(default_factory=list)
    quality_flags: List[str] = Field(default_factory=list)
    passed_quality_gates: bool = True
    gate_reasons: List[str] = Field(default_factory=list)
    human_review_status: str = "pending"


class HumanReviewRecord(BaseModel):
    """Editorial sign-off / feedback on a promo candidate."""
    candidate_id: str
    episode_number: int
    rank: int
    decision: str  # APPROVED, REJECTED, NEEDS_RECUT, PENDING
    reviewer_name: str
    notes: str = ""
    timestamp: str = ""
