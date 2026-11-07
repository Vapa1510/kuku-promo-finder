"""
Ranking, Quality Gates, and Export Module
=========================================
Applies hard promotional quality gates, temporal IoU deduplication, per-episode
diversity caps, and final score reconciliation. Exports structured JSON, CSV,
and full candidate screening audit trails.
"""

import csv
import json
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

from .models import PromoCandidate, CandidateEvaluation, JudgeEvaluation, FinalPromoResult
from .config import PromoFinderConfig, DEFAULT_CONFIG
from .evidence_validator import EvidenceValidationResult, validate_candidate_evidence


def check_quality_gates(
    candidate: PromoCandidate,
    evaluation: CandidateEvaluation,
    judge: JudgeEvaluation,
    config: PromoFinderConfig = DEFAULT_CONFIG,
    evidence_result: Optional[EvidenceValidationResult] = None,
) -> Tuple[bool, List[str]]:
    """
    Enforce hard promotional quality thresholds:
    - hook_strength >= min_hook (6.0)
    - cliffhanger_strength >= min_cliffhanger (6.0)
    - narrative_clarity >= min_clarity (5.0)
    - min_duration <= duration <= max_duration (20.0s - 60.0s)
    - judge_verdict != 'REJECT'
    - resolution_leaked == False
    - evidence_valid == True (if evidence_result passed or candidate has events)
    """
    reasons: List[str] = []
    gates = config.gates

    if evaluation.hook_strength < gates.min_hook:
        reasons.append(f"Hook strength {evaluation.hook_strength:.1f} < {gates.min_hook:.1f}")

    if evaluation.cliffhanger_strength < gates.min_cliffhanger:
        reasons.append(f"Cliffhanger strength {evaluation.cliffhanger_strength:.1f} < {gates.min_cliffhanger:.1f}")

    if evaluation.narrative_clarity < gates.min_clarity:
        reasons.append(f"Narrative clarity {evaluation.narrative_clarity:.1f} < {gates.min_clarity:.1f}")

    if candidate.duration < gates.min_duration:
        reasons.append(f"Duration {candidate.duration:.1f}s < {gates.min_duration:.1f}s")

    if candidate.duration > gates.max_duration:
        reasons.append(f"Duration {candidate.duration:.1f}s > {gates.max_duration:.1f}s")

    if judge.judge_verdict == "REJECT":
        reasons.append("Rejected by independent editorial judge")

    if gates.reject_resolution_leaked and judge.resolution_leaked:
        reasons.append("Premature narrative resolution leaked before ending")

    # Mandatory Evidence Gate
    if evidence_result is not None:
        if not evidence_result.is_valid:
            reasons.append(f"Evidence validation failed: {'; '.join(evidence_result.issues)}")
    elif candidate.events:
        ev_res = validate_candidate_evidence(candidate, evaluation)
        if not ev_res.is_valid:
            reasons.append(f"Evidence validation failed: {'; '.join(ev_res.issues)}")

    passed = len(reasons) == 0
    return passed, reasons


def calculate_iou(cand1: FinalPromoResult, cand2: FinalPromoResult) -> float:
    """
    Calculate temporal Intersection over Union (IoU) for two promo results in the same episode.
    Supports both single-segment and multi-segment candidates with exact interval arithmetic.
    """
    if cand1.episode_number != cand2.episode_number:
        return 0.0

    segs1 = [(s.start_time, s.end_time) for s in cand1.segments] if cand1.segments else [(cand1.start_time, cand1.end_time)]
    segs2 = [(s.start_time, s.end_time) for s in cand2.segments] if cand2.segments else [(cand2.start_time, cand2.end_time)]

    total_overlap = 0.0
    for s1_start, s1_end in segs1:
        for s2_start, s2_end in segs2:
            ov = max(0.0, min(s1_end, s2_end) - max(s1_start, s2_start))
            total_overlap += ov

    dur1 = sum(e - s for s, e in segs1)
    dur2 = sum(e - s for s, e in segs2)
    union = dur1 + dur2 - total_overlap

    return (total_overlap / union) if union > 0 else 0.0


def reconcile_final_score(
    eval_score: float,
    judge_score: float,
    config: PromoFinderConfig = DEFAULT_CONFIG,
    llm_mode_active: Optional[bool] = None,
) -> float:
    """
    Reconcile final score:
    - If llm_mode_active is False: return eval_score directly (100% CandidateEvaluation).
    - Otherwise (default / llm_mode_active=True): config.evaluator_weight * eval_score + config.judge_weight * judge_score.
    """
    if llm_mode_active is False:
        return round(eval_score, 2)
    final = config.evaluator_weight * eval_score + config.judge_weight * judge_score
    return round(final, 2)


def build_final_promo_result(
    candidate: PromoCandidate,
    evaluation: CandidateEvaluation,
    judge: JudgeEvaluation,
    config: PromoFinderConfig = DEFAULT_CONFIG,
    evidence_result: Optional[EvidenceValidationResult] = None,
    llm_mode_active: Optional[bool] = None,
) -> FinalPromoResult:
    """Combine candidate, evaluation, and judge data into FinalPromoResult."""
    if evidence_result is None and candidate.events:
        evidence_result = validate_candidate_evidence(candidate, evaluation)

    passed, gate_reasons = check_quality_gates(candidate, evaluation, judge, config, evidence_result=evidence_result)
    is_llm = llm_mode_active if llm_mode_active is not None else config.enable_llm
    final_score = reconcile_final_score(evaluation.overall_score, judge.judge_score, config, llm_mode_active=is_llm)

    scores_dict = {
        "hook_strength": evaluation.hook_strength,
        "cliffhanger_strength": evaluation.cliffhanger_strength,
        "narrative_clarity": evaluation.narrative_clarity,
        "conflict_and_stakes": evaluation.conflict_and_stakes,
        "emotional_pull": evaluation.emotional_pull,
        "script_visual_potential": evaluation.script_visual_potential,
        "boundary_suitability": evaluation.boundary_suitability,
        "evaluator_overall": evaluation.overall_score,
        "judge_score": judge.judge_score,
    }

    events_summary = [
        f"[{ev.start:.2f}-{ev.end:.2f}] {ev.event_id} | {ev.event_type}"
        + (f" ({ev.character})" if ev.character else "")
        + f": {ev.text[:60]}"
        for ev in candidate.events
    ]

    return FinalPromoResult(
        rank=0,
        candidate_id=candidate.candidate_id,
        episode_number=candidate.episode_number,
        start_time=candidate.start_time,
        end_time=candidate.end_time,
        start_display=candidate.start_display,
        end_display=candidate.end_display,
        duration_seconds=candidate.duration,
        final_score=final_score,
        candidate_score=evaluation.overall_score,
        judge_score=judge.judge_score,
        scores=scores_dict,
        editorial_verdict=evaluation.editorial_verdict,
        judge_verdict=judge.judge_verdict,
        promo_title=evaluation.promo_title,
        hook_explanation=evaluation.hook_explanation,
        cliffhanger_explanation=evaluation.cliffhanger_explanation,
        standalone_explanation=evaluation.standalone_explanation,
        opening_quote=evaluation.opening_quote,
        closing_quote=evaluation.closing_quote,
        strengths=judge.strengths,
        weaknesses=judge.weaknesses,
        segments=candidate.segments,
        events_summary=events_summary,
        quality_flags=evaluation.quality_flags,
        passed_quality_gates=passed,
        gate_reasons=gate_reasons,
        human_review_status="pending",
    )


def rank_and_deduplicate(
    results: List[FinalPromoResult],
    config: PromoFinderConfig = DEFAULT_CONFIG,
) -> Tuple[List[FinalPromoResult], List[FinalPromoResult]]:
    """
    Ranks candidates, applies quality gates, temporal IoU deduplication,
    and per-episode diversity caps.
    Returns:
        (top_qualified_promos, all_screened_audit)
    """
    # Sort all by final_score descending
    all_sorted = sorted(results, key=lambda r: r.final_score, reverse=True)

    qualified_pool = [r for r in all_sorted if r.passed_quality_gates]
    rejected_pool = [r for r in all_sorted if not r.passed_quality_gates]

    # IoU deduplication and Diversity Cap on qualified candidates
    selected: List[FinalPromoResult] = []
    ep_counts: Dict[int, int] = {}

    for cand in qualified_pool:
        # Check episode cap
        current_ep_count = ep_counts.get(cand.episode_number, 0)
        if current_ep_count >= config.max_per_episode:
            cand.gate_reasons.append(f"Suppressed by episode diversity cap (max {config.max_per_episode}/ep)")
            continue

        # Check IoU against already selected from the same episode
        iou_conflict = False
        for s in selected:
            if s.episode_number == cand.episode_number:
                iou = calculate_iou(cand, s)
                if iou > config.iou_threshold:
                    iou_conflict = True
                    cand.gate_reasons.append(f"Suppressed by IoU overlap ({iou:.2f} > {config.iou_threshold:.2f}) with {s.candidate_id}")
                    break

        if not iou_conflict:
            selected.append(cand)
            ep_counts[cand.episode_number] = current_ep_count + 1

            if len(selected) >= config.top_n:
                break

    # Mark remaining unselected candidates in qualified pool
    selected_ids = {s.candidate_id for s in selected}
    for cand in qualified_pool:
        if cand.candidate_id not in selected_ids and not cand.gate_reasons:
            cand.gate_reasons.append(f"Excluded from Top {config.top_n} (rank cutoff)")

    # Assign ranks to top qualified
    for i, p in enumerate(selected, 1):
        p.rank = i

    return selected, all_sorted


def export_results_json(promos: List[FinalPromoResult], filepath: str) -> None:
    """Export top qualified promos to JSON."""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "total_promos": len(promos),
        "promos": [p.model_dump() for p in promos],
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def export_results_csv(promos: List[FinalPromoResult], filepath: str) -> None:
    """Export top qualified promos to CSV."""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "rank", "candidate_id", "episode_number", "start_display", "end_display",
        "duration_seconds", "final_score", "candidate_score", "judge_score",
        "promo_title", "editorial_verdict", "judge_verdict",
        "opening_quote", "closing_quote", "hook_explanation", "cliffhanger_explanation",
        "strengths", "weaknesses", "human_review_status",
    ]
    with open(filepath, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for p in promos:
            row = {
                "rank": p.rank,
                "candidate_id": p.candidate_id,
                "episode_number": p.episode_number,
                "start_display": p.start_display,
                "end_display": p.end_display,
                "duration_seconds": p.duration_seconds,
                "final_score": p.final_score,
                "candidate_score": p.candidate_score,
                "judge_score": p.judge_score,
                "promo_title": p.promo_title,
                "editorial_verdict": p.editorial_verdict,
                "judge_verdict": p.judge_verdict,
                "opening_quote": p.opening_quote,
                "closing_quote": p.closing_quote,
                "hook_explanation": p.hook_explanation,
                "cliffhanger_explanation": p.cliffhanger_explanation,
                "strengths": p.strengths,
                "weaknesses": p.weaknesses,
                "human_review_status": p.human_review_status,
            }
            writer.writerow(row)


def export_screened_audit_json(all_screened: List[FinalPromoResult], filepath: str) -> None:
    """Export full candidate screening audit trail with pass/rejection reasons."""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "total_screened": len(all_screened),
        "total_passed": sum(1 for r in all_screened if r.passed_quality_gates),
        "total_rejected": sum(1 for r in all_screened if not r.passed_quality_gates),
        "candidates": [r.model_dump() for r in all_screened],
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def export_model_responses_jsonl(responses: List[Dict[str, Any]], filepath: str) -> None:
    """Export raw model prompt/response traces."""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        for resp in responses:
            f.write(json.dumps(resp) + "\n")
