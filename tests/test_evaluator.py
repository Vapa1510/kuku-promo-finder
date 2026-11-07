"""Tests for Evaluator Module."""

from promo_finder.models import ScreenplayEvent, PromoCandidate, PromoSegment
from promo_finder.evaluator import RuleBasedEvaluator, GeminiEvaluator
from promo_finder.config import DEFAULT_CONFIG


def make_sample_candidate():
    events = [
        ScreenplayEvent(
            event_id="EP01_SC01_EV010",
            scene_id=1,
            event_type="DIALOGUE",
            character="MATRIARCH",
            tone="Cold, Commanding",
            text="You should turn around, Juliana.",
            start=11.30,
            end=13.10,
            source_line=43,
        ),
        ScreenplayEvent(
            event_id="EP01_SC01_EV011",
            scene_id=1,
            event_type="DIALOGUE",
            character="LADY JULIANA",
            tone="Confused, Breathless",
            text="Why? Gerald is waiting for me at the altar.",
            start=13.50,
            end=17.50,
            source_line=47,
        ),
        ScreenplayEvent(
            event_id="EP01_SC01_EV012",
            scene_id=1,
            event_type="DIALOGUE",
            character="GERALD",
            tone="Arrogant",
            text="Not anymore. Clarissa is my true betrothed!",
            start=18.00,
            end=38.00,
            source_line=55,
        ),
    ]

    seg = PromoSegment(
        episode_number=1,
        start_time=11.30,
        end_time=38.00,
        start_display="00:11.30",
        end_display="00:38.00",
        event_ids=[e.event_id for e in events],
    )

    return PromoCandidate(
        candidate_id="CAND_EP01_001",
        episode_number=1,
        start_time=11.30,
        end_time=38.00,
        segments=[seg],
        duration=26.70,
        events=events,
        heuristic_score=8.5,
        hook_signals=["altar", "betrothed"],
    )


def test_rule_based_evaluator_scores():
    cand = make_sample_candidate()
    evaluator = RuleBasedEvaluator(config=DEFAULT_CONFIG)
    evaluation = evaluator.evaluate(cand)

    assert evaluation.candidate_id == cand.candidate_id
    assert 0.0 <= evaluation.hook_strength <= 10.0
    assert 0.0 <= evaluation.cliffhanger_strength <= 10.0
    assert 0.0 <= evaluation.narrative_clarity <= 10.0
    assert 0.0 <= evaluation.conflict_and_stakes <= 10.0
    assert 0.0 <= evaluation.overall_score <= 10.0
    assert evaluation.editorial_verdict in ("STRONG", "GOOD", "BORDERLINE", "REJECT")
    assert len(evaluation.hook_evidence_event_ids) > 0
    assert len(evaluation.cliffhanger_evidence_event_ids) > 0
    assert evaluation.opening_quote != ""
    assert evaluation.closing_quote != ""


def test_gemini_evaluator_offline_fallback():
    cand = make_sample_candidate()
    # No API key provided -> falls back gracefully
    evaluator = GeminiEvaluator(api_key=None, config=DEFAULT_CONFIG)
    evaluation = evaluator.evaluate(cand)

    assert evaluation.candidate_id == cand.candidate_id
    assert evaluation.overall_score > 0.0
    assert evaluation.editorial_verdict != ""


def test_title_generation_templates():
    from promo_finder.evaluator import generate_promo_title
    cand = make_sample_candidate()
    title, rationale = generate_promo_title(cand)

    assert "[Provisional Title]" in title
    assert any(expected in title for expected in ["The Altar Betrayal", "The Secret Proposal", "The Cathedral Breach"])
    assert len(rationale) > 10

