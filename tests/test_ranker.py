"""Tests for Ranking, Deduplication, and Diversity Cap."""

from promo_finder.models import FinalPromoResult
from promo_finder.config import PromoFinderConfig
from promo_finder.ranker import calculate_iou, reconcile_final_score, rank_and_deduplicate


def make_result(cand_id, ep_num, start, end, final_score, passed=True):
    return FinalPromoResult(
        candidate_id=cand_id,
        episode_number=ep_num,
        start_time=start,
        end_time=end,
        start_display="00:00.00",
        end_display="00:30.00",
        duration_seconds=round(end - start, 2),
        final_score=final_score,
        candidate_score=final_score,
        judge_score=final_score,
        passed_quality_gates=passed,
    )


def test_calculate_iou():
    # Identical segments -> IoU = 1.0
    r1 = make_result("C1", 1, 10.0, 40.0, 8.0)
    r2 = make_result("C2", 1, 10.0, 40.0, 7.5)
    assert calculate_iou(r1, r2) == 1.0

    # Half overlap: [10, 40] and [25, 55] -> overlap=15, union=45 -> IoU = 15/45 = 0.333
    r3 = make_result("C3", 1, 25.0, 55.0, 7.0)
    assert round(calculate_iou(r1, r3), 3) == 0.333

    # Different episodes -> IoU = 0.0
    r_diff_ep = make_result("C4", 2, 10.0, 40.0, 8.0)
    assert calculate_iou(r1, r_diff_ep) == 0.0


def test_calculate_iou_multi_segment():
    from promo_finder.models import PromoSegment

    # Multi-segment candidate spanning [10, 25] and [80, 95] (total duration 30s)
    seg1 = PromoSegment(episode_number=1, start_time=10.0, end_time=25.0, start_display="00:10.00", end_display="00:25.00")
    seg2 = PromoSegment(episode_number=1, start_time=80.0, end_time=95.0, start_display="01:20.00", end_display="01:35.00")
    multi_res = FinalPromoResult(
        candidate_id="MULTI_1",
        episode_number=1,
        start_time=10.0,
        end_time=95.0,
        start_display="00:10.00",
        end_display="01:35.00",
        duration_seconds=30.0,
        final_score=8.5,
        candidate_score=8.5,
        judge_score=8.5,
        segments=[seg1, seg2],
        passed_quality_gates=True,
    )

    # Single segment candidate in the middle gap [40, 60]
    gap_res = make_result("GAP_CAND", 1, 40.0, 60.0, 8.0)

    # IoU must be exactly 0.0 because it lies in the middle gap where multi_res has no events
    assert calculate_iou(multi_res, gap_res) == 0.0

    # Candidate overlapping first segment only [15, 30] (dur 15s)
    # Overlap with seg1 [10, 25] is [15, 25] = 10s. Overlap with seg2 is 0.
    # Total overlap = 10s. Dur1 = 30s, Dur2 = 15s. Union = 30 + 15 - 10 = 35s. IoU = 10/35 = 0.2857
    ov_res = make_result("OV_CAND", 1, 15.0, 30.0, 8.0)
    assert round(calculate_iou(multi_res, ov_res), 3) == 0.286


def test_reconcile_final_score():
    config = PromoFinderConfig(evaluator_weight=0.35, judge_weight=0.65)
    # 0.35 * 8.0 + 0.65 * 9.0 = 2.80 + 5.85 = 8.65
    reconciled = reconcile_final_score(8.0, 9.0, config)
    assert reconciled == 8.65


def test_rank_and_deduplicate_iou_suppression():
    config = PromoFinderConfig(iou_threshold=0.40, max_per_episode=2, top_n=10)

    # C1 and C2 have heavy overlap (IoU = 20/30 = 0.667 > 0.40)
    r1 = make_result("C1", 1, 10.0, 40.0, 9.0)  # higher score
    r2 = make_result("C2", 1, 15.0, 40.0, 8.5)  # lower score, should be suppressed
    r3 = make_result("C3", 1, 60.0, 90.0, 8.0)  # non-overlapping in same episode

    selected, all_screened = rank_and_deduplicate([r1, r2, r3], config)

    selected_ids = [s.candidate_id for s in selected]
    assert "C1" in selected_ids
    assert "C2" not in selected_ids  # suppressed by IoU
    assert "C3" in selected_ids
    assert len(selected) == 2


def test_rank_and_deduplicate_diversity_cap():
    config = PromoFinderConfig(iou_threshold=0.40, max_per_episode=2, top_n=10)

    # 4 distinct non-overlapping candidates from Episode 1
    r1 = make_result("C1", 1, 10.0, 30.0, 9.5)
    r2 = make_result("C2", 1, 40.0, 60.0, 9.0)
    r3 = make_result("C3", 1, 70.0, 90.0, 8.5)
    r4 = make_result("C4", 1, 100.0, 120.0, 8.0)
    # 1 candidate from Episode 2
    r5 = make_result("C5", 2, 10.0, 30.0, 7.5)

    selected, all_screened = rank_and_deduplicate([r1, r2, r3, r4, r5], config)

    # Episode 1 should have exactly 2 candidates despite having 4 qualified
    ep1_selected = [s for s in selected if s.episode_number == 1]
    assert len(ep1_selected) == 2
    assert selected[0].candidate_id == "C1"
    assert selected[1].candidate_id == "C2"
    assert any(s.candidate_id == "C5" for s in selected)


def test_offline_score_calibration():
    from promo_finder.models import PromoCandidate, CandidateEvaluation, JudgeEvaluation
    from promo_finder.ranker import build_final_promo_result
    cand = PromoCandidate(
        candidate_id="CAND_OFFLINE_01",
        episode_number=1,
        start_time=10.0,
        end_time=40.0,
        duration=30.0,
    )
    cand_eval = CandidateEvaluation(
        candidate_id="CAND_OFFLINE_01",
        hook_strength=7.5,
        cliffhanger_strength=7.0,
        narrative_clarity=7.0,
        conflict_and_stakes=7.5,
        emotional_pull=7.0,
        script_visual_potential=7.0,
        boundary_suitability=8.0,
        overall_score=7.35,
    )
    judge_eval = JudgeEvaluation(
        candidate_id="CAND_OFFLINE_01",
        judge_score=9.8,
        judge_verdict="STRONG",
        resolution_leaked=False,
    )

    # In offline mode, final score is driven 100% by CandidateEvaluation
    result_offline = build_final_promo_result(cand, cand_eval, judge_eval, llm_mode_active=False)
    assert result_offline.final_score == 7.35
    assert result_offline.final_score != 9.8

    # In LLM mode, composite formula is used
    result_llm = build_final_promo_result(cand, cand_eval, judge_eval, llm_mode_active=True)
    assert result_llm.final_score == 8.94


def test_benchmark_strict_one_to_one_matching(tmp_path):
    import json
    from evaluation.benchmark import run_benchmark

    gt_file = tmp_path / "gt.json"
    pred_file = tmp_path / "pred.json"

    gt_data = {
        "ground_truth_promos": [
            {
                "benchmark_id": "GT_01",
                "episode_number": 1,
                "target_start_seconds": 10.0,
                "target_end_seconds": 30.0,
            }
        ]
    }
    gt_file.write_text(json.dumps(gt_data))

    # Two predictions both matching GT_01
    pred_data = {
        "promos": [
            {"rank": 1, "episode_number": 1, "start_time": 10.0, "end_time": 30.0},
            {"rank": 2, "episode_number": 1, "start_time": 10.0, "end_time": 30.0},
        ]
    }
    pred_file.write_text(json.dumps(pred_data))

    res = run_benchmark(str(gt_file), str(pred_file), k_list=[2])
    # With strict 1-to-1 matching, only the first prediction should be counted as a hit
    assert res["metrics_at_k"]["K=2"]["hits"] == 1
    assert res["metrics_at_k"]["K=2"]["precision"] == 0.5


