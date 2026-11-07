"""Tests for Evidence and Grounding Validator."""

from promo_finder.models import ScreenplayEvent, PromoCandidate, PromoSegment, CandidateEvaluation
from promo_finder.evidence_validator import validate_candidate_evidence


def build_candidate_and_eval():
    events = [
        ScreenplayEvent(
            event_id="EP01_SC01_EV001",
            scene_id=1,
            event_type="DIALOGUE",
            character="MATRIARCH",
            tone="Cold",
            text="You should turn around, Juliana.",
            start=11.30,
            end=13.10,
        ),
        ScreenplayEvent(
            event_id="EP01_SC01_EV002",
            scene_id=1,
            event_type="ACTION",
            text="Juliana steps back in shock as guests stare.",
            start=13.20,
            end=20.00,
        ),
        ScreenplayEvent(
            event_id="EP01_SC01_EV003",
            scene_id=1,
            event_type="DIALOGUE",
            character="GERALD",
            tone="Harsh",
            text="I will never marry you!",
            start=20.10,
            end=35.00,
        ),
    ]
    seg = PromoSegment(
        episode_number=1,
        start_time=11.30,
        end_time=35.00,
        start_display="00:11.30",
        end_display="00:35.00",
        event_ids=[e.event_id for e in events],
    )
    cand = PromoCandidate(
        candidate_id="CAND_EV_01",
        episode_number=1,
        start_time=11.30,
        end_time=35.00,
        segments=[seg],
        duration=23.70,
        events=events,
    )
    evaluation = CandidateEvaluation(
        candidate_id="CAND_EV_01",
        hook_strength=8.0,
        cliffhanger_strength=8.5,
        narrative_clarity=7.5,
        conflict_and_stakes=8.0,
        emotional_pull=8.0,
        script_visual_potential=7.0,
        boundary_suitability=8.5,
        overall_score=8.0,
        hook_evidence_event_ids=["EP01_SC01_EV001"],
        cliffhanger_evidence_event_ids=["EP01_SC01_EV003"],
        hook_explanation="Opening confrontation by matriarch.",
        cliffhanger_explanation="Gerald rejects marriage publicly.",
    )
    return cand, evaluation


def test_valid_evidence_passes():
    cand, evaluation = build_candidate_and_eval()
    res = validate_candidate_evidence(cand, evaluation)

    assert res.is_valid
    assert len(res.issues) == 0
    assert 'MATRIARCH: "You should turn around, Juliana."' in res.opening_quote
    assert 'GERALD: "I will never marry you!"' in res.closing_quote


def test_hallucinated_event_id_detected():
    cand, evaluation = build_candidate_and_eval()
    # Hallucinated ID
    evaluation.hook_evidence_event_ids = ["EP99_SC99_EV999"]
    res = validate_candidate_evidence(cand, evaluation)

    assert not res.is_valid
    assert any("EP99_SC99_EV999" in issue for issue in res.issues)
    # Auto-corrected to valid opening event
    assert res.validated_hook_ids == ["EP01_SC01_EV001"]
