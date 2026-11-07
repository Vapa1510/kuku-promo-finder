"""
Promo Finder — Main Orchestrator and CLI Pipeline
=================================================
Orchestrates the complete hybrid AI promotional clip workflow:
Parse -> Detect -> Evaluate -> Evidence Check -> Editorial Judge -> Rank & Deduplicate -> Export.
"""

import argparse
import datetime
import json
import os
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

from .config import PromoFinderConfig, ScoringWeights, QualityGates, DEFAULT_CONFIG
from .parser import load_all_episodes
from .detector import detect_all_candidates
from .multi_segment_assembler import assemble_multi_segment_candidates
from .evaluator import GeminiEvaluator, RuleBasedEvaluator, BaseEvaluator
from .judge import LLMJudge, RuleBasedJudge, BaseJudge
from .evidence_validator import validate_candidate_evidence
from .ranker import (
    build_final_promo_result,
    rank_and_deduplicate,
    export_results_json,
    export_results_csv,
    export_screened_audit_json,
    export_model_responses_jsonl,
)
from .feedback import EditorialFeedbackManager
from .storage import CacheManager, compute_input_fingerprint
from .models import FinalPromoResult


def run_pipeline(
    input_folder: str,
    output_folder: str,
    config: Optional[PromoFinderConfig] = None,
    api_key: Optional[str] = None,
    resume: bool = False,
    verbose: bool = True,
) -> List[FinalPromoResult]:
    """
    Execute the complete Promo Finder pipeline.
    """
    start_total_time = time.time()
    config = config or DEFAULT_CONFIG
    output_dir = Path(output_folder)
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_mgr = CacheManager(config.cache_dir)
    checkpoint_file = os.path.join(config.cache_dir, "pipeline_checkpoint.json")

    def log(msg: str):
        if verbose:
            print(msg, flush=True)

    fingerprint = compute_input_fingerprint(input_folder, config.model_dump())

    log("=" * 70)
    log("ADVANCED PROMO FINDER — HYBRID AI EXTRACTION PIPELINE")
    log("=" * 70)
    log(f"Input configuration fingerprint: {fingerprint[:16]}...")
    log(f"Input screenplay directory : {input_folder}")
    log(f"Output directory            : {output_folder}")
    log(f"Duration bounds             : {config.min_duration:.1f}s - {config.max_duration:.1f}s")
    log(f"Quality Gates               : Hook >= {config.gates.min_hook}, Cliff >= {config.gates.min_cliffhanger}, Clarity >= {config.gates.min_clarity}")
    log(f"IoU Dedup Threshold         : {config.iou_threshold:.2f} | Max/Ep: {config.max_per_episode}")
    log(f"LLM mode enabled            : {config.enable_llm}")

    # ------------------------------------------------------------------
    # Step 1: Parse all episodes
    # ------------------------------------------------------------------
    step1_start = time.time()
    log("\n[1/6] Parsing Screenplays...")
    episodes = load_all_episodes(input_folder)
    if not episodes:
        raise ValueError(f"No valid screenplay .txt files found in: {input_folder}")

    total_events = sum(len(ep.get_all_events()) for ep in episodes)
    log(f"      Parsed {len(episodes)} episodes ({total_events} total screenplay events) in {time.time() - step1_start:.2f}s")

    # ------------------------------------------------------------------
    # Step 2: Detect boundary-snapped candidates
    # ------------------------------------------------------------------
    step2_start = time.time()
    log("\n[2/6] Detecting Event-Boundary-Snapped Candidates...")
    candidates = detect_all_candidates(
        episodes=episodes,
        min_dur=config.min_duration,
        max_dur=config.max_duration,
        per_episode=config.candidates_per_episode,
        include_exploratory=config.include_exploratory_candidate,
    )

    if config.enable_multisegment:
        log("      Assembling supplementary multi-segment narrative beats...")
        multi_cands = assemble_multi_segment_candidates(
            episodes=episodes,
            min_dur=config.min_duration,
            max_dur=config.max_duration,
        )
        candidates.extend(multi_cands)

    log(f"      Selected {len(candidates)} high-potential candidates across all episodes in {time.time() - step2_start:.2f}s")

    # ------------------------------------------------------------------
    # Step 3: Initialize Evaluator and Judge
    # ------------------------------------------------------------------
    effective_api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    use_live_llm = config.enable_llm and bool(effective_api_key)

    if use_live_llm:
        log(f"\n[3/6] Initializing Gemini GenAI Clients ({config.gemini_model} & {config.judge_model})...")
        evaluator: BaseEvaluator = GeminiEvaluator(
            api_key=effective_api_key,
            model_name=config.gemini_model,
            config=config,
            cache_manager=cache_mgr,
        )
        judge: BaseJudge = LLMJudge(
            api_key=effective_api_key,
            model_name=config.judge_model,
            config=config,
            cache_manager=cache_mgr,
        )
    else:
        log("\n[3/6] Initializing Deterministic Rule-Based Evaluator & Judge (Offline Mode)...")
        evaluator = RuleBasedEvaluator(config=config)
        judge = RuleBasedJudge(config=config)

    # ------------------------------------------------------------------
    # Step 4: Evaluate candidates, validate evidence, run editorial judge
    # ------------------------------------------------------------------
    step4_start = time.time()
    log(f"\n[4/6] Evaluating {len(candidates)} candidates and conducting independent editorial reviews...")

    final_results: List[FinalPromoResult] = []
    model_traces: List[Dict[str, Any]] = []

    if resume:
        cached_checkpoint = cache_mgr.load_checkpoint(checkpoint_file)
        if cached_checkpoint and cached_checkpoint.get("input_fingerprint") == fingerprint:
            if "final_results" in cached_checkpoint:
                log(f"      Resuming from checkpoint ({len(cached_checkpoint['final_results'])} candidates loaded)...")
                final_results = [FinalPromoResult.model_validate(r) for r in cached_checkpoint["final_results"]]
                model_traces = cached_checkpoint.get("model_traces", [])
        elif cached_checkpoint:
            log("      Checkpoint fingerprint mismatch (input screenplay files or config modified). Restarting clean...")

    if not final_results:
        for idx, cand in enumerate(candidates, 1):
            if idx % 25 == 0 or idx == len(candidates):
                log(f"      Processed {idx}/{len(candidates)} candidates...")

            # 4a. Primary narrative evaluation
            cand_eval = evaluator.evaluate(cand)

            # 4b. Evidence and timestamp validation check
            val_res = validate_candidate_evidence(cand, cand_eval)
            cand_eval.opening_quote = val_res.opening_quote
            cand_eval.closing_quote = val_res.closing_quote
            cand_eval.hook_evidence_event_ids = val_res.validated_hook_ids
            cand_eval.cliffhanger_evidence_event_ids = val_res.validated_cliff_ids
            for issue in val_res.issues:
                if issue not in cand_eval.quality_flags:
                    cand_eval.quality_flags.append(issue)

            # 4c. Independent Editorial Judge evaluation
            judge_eval = judge.judge(cand)

            # 4d. Build combined result & check quality gates
            result = build_final_promo_result(
                cand,
                cand_eval,
                judge_eval,
                config,
                evidence_result=val_res,
                llm_mode_active=use_live_llm,
            )
            final_results.append(result)

            # Trace record
            model_traces.append({
                "candidate_id": cand.candidate_id,
                "episode": cand.episode_number,
                "evaluator_verdict": cand_eval.editorial_verdict,
                "judge_verdict": judge_eval.judge_verdict,
                "final_score": result.final_score,
                "passed_gates": result.passed_quality_gates,
            })

            # Progressive checkpointing every 10 candidates
            if idx % 10 == 0 or idx == len(candidates):
                cache_mgr.save_checkpoint(checkpoint_file, {
                    "input_fingerprint": fingerprint,
                    "final_results": [r.model_dump() for r in final_results],
                    "model_traces": model_traces,
                })

    log(f"      Evaluated and judged {len(final_results)} candidates in {time.time() - step4_start:.2f}s")

    # ------------------------------------------------------------------
    # Step 5: Rank, apply IoU deduplication and episode diversity cap
    # ------------------------------------------------------------------
    step5_start = time.time()
    log(f"\n[5/6] Enforcing Quality Gates, IoU Deduplication (IoU <= {config.iou_threshold}), and Episode Caps (Max {config.max_per_episode}/ep)...")

    top_promos, all_screened = rank_and_deduplicate(final_results, config)

    log(f"      Filtered down to Top {len(top_promos)} qualified promos (from {len(all_screened)} total screened)")

    # ------------------------------------------------------------------
    # Step 6: Export results and audit files
    # ------------------------------------------------------------------
    log("\n[6/6] Exporting Artifacts...")

    json_path = str(output_dir / "promo_results.json")
    csv_path = str(output_dir / "promo_results.csv")
    screened_path = str(output_dir / "all_screened_candidates.json")
    traces_path = str(output_dir / "model_responses.jsonl")
    metadata_path = str(output_dir / "run_metadata.json")
    feedback_csv = str(output_dir / "human_feedback.csv")

    export_results_json(top_promos, json_path)
    export_results_csv(top_promos, csv_path)
    export_screened_audit_json(all_screened, screened_path)
    export_model_responses_jsonl(model_traces, traces_path)

    # Initialize human feedback CSV template
    fb_manager = EditorialFeedbackManager()
    fb_manager.initialize_review_template(top_promos, feedback_csv)

    total_pipeline_time = round(time.time() - start_total_time, 2)

    # Save run metadata
    run_meta = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_runtime_seconds": total_pipeline_time,
        "input_folder": str(input_folder),
        "output_folder": str(output_folder),
        "total_episodes_parsed": len(episodes),
        "total_candidates_detected": len(candidates),
        "total_candidates_screened": len(all_screened),
        "top_qualified_promos_count": len(top_promos),
        "configuration": config.model_dump(),
        "llm_mode_active": use_live_llm,
    }
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(run_meta, f, indent=2)

    log(f"      Exported top promos to       : {json_path}")
    log(f"      Exported CSV summary to      : {csv_path}")
    log(f"      Exported full audit trail to : {screened_path}")
    log(f"      Exported run metadata to     : {metadata_path}")
    log(f"      Exported feedback template to: {feedback_csv}")
    log("=" * 70)
    log(f"PIPELINE COMPLETED SUCCESSFULLY IN {total_pipeline_time:.2f}s")
    log("=" * 70)
    log("\nTOP 5 HIGHEST RANKED PROMO RECOMMENDATIONS:")
    for p in top_promos[:5]:
        log(f"  #{p.rank:02d} | Ep {p.episode_number:02d} [{p.start_display} - {p.end_display}] ({p.duration_seconds:.1f}s) | Score: {p.final_score:.2f} | {p.promo_title}")
        log(f"       Quote: {p.opening_quote[:75]}...")
        log(f"       Verdict: {p.editorial_verdict} (Judge: {p.judge_verdict})")

    return top_promos


def build_parser() -> argparse.ArgumentParser:
    """Construct CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Advanced Hybrid AI Promo Finder for Screenplay Dramas"
    )
    parser.add_argument("-i", "--input", default=None, help="Input directory containing screenplay .txt files")
    parser.add_argument("-o", "--output", default="outputs", help="Output directory for generated results")
    parser.add_argument("--top", type=int, default=30, help="Number of top promos to recommend (default: 30)")
    parser.add_argument("--min-duration", type=float, default=20.0, help="Minimum promo duration in seconds (default: 20.0)")
    parser.add_argument("--max-duration", type=float, default=60.0, help="Maximum promo duration in seconds (default: 60.0)")
    parser.add_argument("--min-hook", type=float, default=6.0, help="Minimum hook strength quality gate (default: 6.0)")
    parser.add_argument("--min-cliff", type=float, default=6.0, help="Minimum cliffhanger strength quality gate (default: 6.0)")
    parser.add_argument("--min-clarity", type=float, default=5.0, help="Minimum narrative clarity quality gate (default: 5.0)")
    parser.add_argument("--iou-threshold", type=float, default=0.40, help="Temporal IoU overlap deduplication threshold (default: 0.40)")
    parser.add_argument("--max-per-episode", type=int, default=2, help="Maximum promos per episode in top list (default: 2)")
    parser.add_argument("--candidates-per-episode", type=int, default=4, help="Heuristic candidates detected per episode (default: 4)")
    parser.add_argument("--resume", action="store_true", help="Resume pipeline from intermediate checkpoint")
    parser.add_argument("--enable-llm", action="store_true", help="Enable live Gemini LLM evaluator and judge")
    parser.add_argument("--gemini-api-key", default=None, help="Gemini API Key (overrides GEMINI_API_KEY env var)")
    parser.add_argument("--model", default="gemini-3.5-flash", help="Model name for candidate evaluation")
    parser.add_argument("--judge-model", default="gemini-3.5-flash", help="Model name for independent judge")
    parser.add_argument("--enable-multisegment", action="store_true", help="Enable multi-segment cross-scene assembly")
    parser.add_argument("--import-feedback", default=None, help="Import editorial feedback CSV and compute metrics")
    parser.add_argument("--cache-dir", default=".cache", help="Disk cache directory")
    parser.add_argument("--quiet", action="store_true", help="Suppress verbose console output")
    return parser


def main() -> int:
    """CLI Entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if args.import_feedback:
        print(f"\nImporting editorial feedback from: {args.import_feedback}")
        mgr = EditorialFeedbackManager(args.import_feedback)
        metrics = mgr.compute_metrics()
        print("=" * 60)
        print("EDITORIAL FEEDBACK METRICS SUMMARY")
        print("=" * 60)
        print(f"Total Reviewed Candidates : {metrics['total_reviews']}")
        print(f"Approved Promos           : {metrics['approved']}")
        print(f"Rejected Promos           : {metrics['rejected']}")
        print(f"Needs Recut               : {metrics['needs_recut']}")
        print(f"Approval Rate             : {metrics['approval_rate'] * 100:.1f}%")
        print("=" * 60)
        return 0

    input_path = args.input
    if not input_path:
        default_dir = os.path.join("I Married a Broken Soldier. He was a Duke-scripts (2)", "I Married a Broken Soldier. He was a Duke")
        if os.path.exists(default_dir):
            input_path = default_dir
        else:
            parser.error("the following arguments are required: -i/--input")

    gates = QualityGates(
        min_hook=args.min_hook,
        min_cliffhanger=args.min_cliff,
        min_clarity=args.min_clarity,
        min_duration=args.min_duration,
        max_duration=args.max_duration,
    )

    config = PromoFinderConfig(
        min_duration=args.min_duration,
        max_duration=args.max_duration,
        candidates_per_episode=args.candidates_per_episode,
        gates=gates,
        top_n=args.top,
        iou_threshold=args.iou_threshold,
        max_per_episode=args.max_per_episode,
        enable_llm=args.enable_llm,
        gemini_model=args.model,
        judge_model=args.judge_model,
        enable_multisegment=args.enable_multisegment,
        cache_dir=args.cache_dir,
    )

    try:
        run_pipeline(
            input_folder=input_path,
            output_folder=args.output,
            config=config,
            api_key=args.gemini_api_key,
            resume=args.resume,
            verbose=not args.quiet,
        )
        return 0
    except Exception as e:
        print(f"\nERROR: Pipeline execution failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
