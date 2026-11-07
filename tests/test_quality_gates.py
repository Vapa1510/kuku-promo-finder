"""Tests for Promotional Quality Gates."""

from promo_finder.models import PromoCandidate, CandidateEvaluation, JudgeEvaluation
from promo_finder.config import PromoFinderConfig, QualityGates
from promo_finder.ranker import check_quality_gates


def make_test_triplet(
    hook=8.0,
    cliff=8.0,
    clarity=7.0,
    duration=30.0,
    judge_verdict="GOOD",
    res_leaked=False,
):
    cand = PromoCandidate(
        candidate_id="CAND_GATE_01",
        episode_number=1,
        start_time=10.0,
        end_time=10.0 + duration,
        duration=duration,
    )
    cand_eval = CandidateEvaluation(
        candidate_id="CAND_GATE_01",
        hook_strength=hook,
        cliffhanger_strength=cliff,
        narrative_clarity=clarity,
        conflict_and_stakes=7.0,
        emotional_pull=7.0,
        script_visual_potential=7.0,
        boundary_suitability=8.0,
        overall_score=7.5,
    )
    judge_eval = JudgeEvaluation(
        candidate_id="CAND_GATE_01",
        judge_score=7.5,
        judge_verdict=judge_verdict,
        resolution_leaked=res_leaked,
    )
    return cand, cand_eval, judge_eval


def test_quality_gates_pass():
    cand, cand_eval, judge_eval = make_test_triplet()
    passed, reasons = check_quality_gates(cand, cand_eval, judge_eval)
    assert passed
    assert len(reasons) == 0


def test_quality_gates_weak_hook():
    cand, cand_eval, judge_eval = make_test_triplet(hook=5.5)
    passed, reasons = check_quality_gates(cand, cand_eval, judge_eval)
    assert not passed
    assert any("Hook strength" in r for r in reasons)


def test_quality_gates_weak_cliffhanger():
    cand, cand_eval, judge_eval = make_test_triplet(cliff=5.8)
    passed, reasons = check_quality_gates(cand, cand_eval, judge_eval)
    assert not passed
    assert any("Cliffhanger strength" in r for r in reasons)


def test_quality_gates_low_clarity():
    cand, cand_eval, judge_eval = make_test_triplet(clarity=4.5)
    passed, reasons = check_quality_gates(cand, cand_eval, judge_eval)
    assert not passed
    assert any("Narrative clarity" in r for r in reasons)


def test_quality_gates_duration_bounds():
    cand_short, ce, je = make_test_triplet(duration=15.0)
    passed_s, reasons_s = check_quality_gates(cand_short, ce, je)
    assert not passed_s
    assert any("15.0s <" in r for r in reasons_s)

    cand_long, ce, je = make_test_triplet(duration=65.0)
    passed_l, reasons_l = check_quality_gates(cand_long, ce, je)
    assert not passed_l
    assert any("65.0s >" in r for r in reasons_l)


def test_quality_gates_judge_rejection():
    cand, cand_eval, judge_eval = make_test_triplet(judge_verdict="REJECT")
    passed, reasons = check_quality_gates(cand, cand_eval, judge_eval)
    assert not passed
    assert any("Rejected by independent" in r for r in reasons)


def test_quality_gates_resolution_leaked():
    cand, cand_eval, judge_eval = make_test_triplet(res_leaked=True)
    passed, reasons = check_quality_gates(cand, cand_eval, judge_eval)
    assert not passed
    assert any("resolution leaked" in r.lower() for r in reasons)


def test_evidence_gate_mandatory_rejection():
    from promo_finder.evidence_validator import EvidenceValidationResult
    cand, cand_eval, judge_eval = make_test_triplet()

    # Valid evidence passes
    valid_ev = EvidenceValidationResult(
        is_valid=True,
        issues=[],
        opening_quote="Hello",
        closing_quote="Goodbye",
        validated_hook_ids=["EV1"],
        validated_cliff_ids=["EV2"],
    )
    passed, reasons = check_quality_gates(cand, cand_eval, judge_eval, evidence_result=valid_ev)
    assert passed
    assert len(reasons) == 0

    # Invalid evidence fails mandatory gate
    invalid_ev = EvidenceValidationResult(
        is_valid=False,
        issues=["No screenplay events found in opening 3-second window."],
        opening_quote="",
        closing_quote="",
        validated_hook_ids=[],
        validated_cliff_ids=[],
    )
    passed, reasons = check_quality_gates(cand, cand_eval, judge_eval, evidence_result=invalid_ev)
    assert not passed
    assert any("Evidence validation failed" in r for r in reasons)
