"""
Benchmark Evaluation Module
===========================
Calculates Precision@K, Recall@K, NDCG@K, and Boundary Error against
human-annotated ground truth promotional segments.
"""

import argparse
import json
import math
from pathlib import Path
from typing import List, Dict, Any, Tuple


def calculate_segment_iou(start1: float, end1: float, start2: float, end2: float) -> float:
    """Intersection over Union for temporal intervals."""
    overlap = max(0.0, min(end1, end2) - max(start1, start2))
    union = max(end1, end2) - min(start1, start2)
    return overlap / union if union > 0 else 0.0


def is_match(
    pred: Dict[str, Any],
    gt: Dict[str, Any],
    min_iou: float = 0.45,
    start_tolerance: float = 3.5,
    end_tolerance: float = 3.5,
) -> bool:
    """
    Check if a predicted promo matches a ground truth promo.
    Matches if same episode and either IoU >= min_iou OR start/end within tolerance.
    """
    if pred["episode_number"] != gt["episode_number"]:
        return False

    pred_start = pred["start_time"]
    pred_end = pred["end_time"]
    gt_start = gt["target_start_seconds"]
    gt_end = gt["target_end_seconds"]

    iou = calculate_segment_iou(pred_start, pred_end, gt_start, gt_end)
    if iou >= min_iou:
        return True

    # Check acceptable range if present
    acc_start = gt.get("acceptable_start_range", [gt_start - start_tolerance, gt_start + start_tolerance])
    acc_end = gt.get("acceptable_end_range", [gt_end - end_tolerance, gt_end + end_tolerance])

    if (acc_start[0] <= pred_start <= acc_start[1]) and (acc_end[0] <= pred_end <= acc_end[1]):
        return True

    return False


def run_benchmark(
    ground_truth_path: str,
    predictions_path: str,
    k_list: List[int] = None,
) -> Dict[str, Any]:
    """Execute benchmark comparison and return metric dictionary."""
    k_list = k_list or [5, 10, 20, 30]

    with open(ground_truth_path, "r", encoding="utf-8") as f:
        gt_data = json.load(f)
    ground_truths = gt_data["ground_truth_promos"]
    total_gt = len(ground_truths)

    with open(predictions_path, "r", encoding="utf-8") as f:
        pred_data = json.load(f)
    predictions = pred_data.get("promos", [])

    results: Dict[str, Any] = {
        "total_ground_truth": total_gt,
        "total_predictions": len(predictions),
        "metrics_at_k": {},
    }

    start_errors = []
    end_errors = []

    # Map matched predictions to ground truth with strict 1-to-1 assignment
    claimed_gt_ids = set()
    binary_relevances = []

    for pred in predictions:
        matched_gt = None
        best_iou = -1.0
        for gt in ground_truths:
            if gt["benchmark_id"] in claimed_gt_ids:
                continue
            if is_match(pred, gt):
                iou = calculate_segment_iou(pred["start_time"], pred["end_time"], gt["target_start_seconds"], gt["target_end_seconds"])
                if iou > best_iou:
                    best_iou = iou
                    matched_gt = gt

        if matched_gt:
            claimed_gt_ids.add(matched_gt["benchmark_id"])
            start_errors.append(abs(pred["start_time"] - matched_gt["target_start_seconds"]))
            end_errors.append(abs(pred["end_time"] - matched_gt["target_end_seconds"]))
            binary_relevances.append(1)
        else:
            binary_relevances.append(0)

    # Compute Precision, Recall, NDCG at each K
    for k in k_list:
        k_preds = binary_relevances[:k]
        hits = sum(k_preds)
        precision = hits / k if k > 0 else 0.0

        # Unique GTs recalled up to rank k
        k_matched_gt = set()
        for pred in predictions[:k]:
            for gt in ground_truths:
                if is_match(pred, gt):
                    k_matched_gt.add(gt["benchmark_id"])
        recall = len(k_matched_gt) / total_gt if total_gt > 0 else 0.0

        # DCG@K
        dcg = sum((rel / math.log2(idx + 2)) for idx, rel in enumerate(k_preds))
        # IDCG@K (ideal DCG where all top min(k, total_gt) are hits)
        ideal_relevances = [1] * min(k, total_gt) + [0] * max(0, k - total_gt)
        idcg = sum((rel / math.log2(idx + 2)) for idx, rel in enumerate(ideal_relevances))
        ndcg = (dcg / idcg) if idcg > 0 else 0.0

        results["metrics_at_k"][f"K={k}"] = {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "ndcg": round(ndcg, 3),
            "hits": hits,
        }

    results["boundary_mae"] = {
        "start_seconds_mae": round(sum(start_errors) / len(start_errors), 2) if start_errors else 0.0,
        "end_seconds_mae": round(sum(end_errors) / len(end_errors), 2) if end_errors else 0.0,
    }

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate promo predictions against ground truth benchmark")
    parser.add_argument("--ground-truth", default="evaluation/ground_truth.json", help="Path to ground truth JSON")
    parser.add_argument("--predictions", default="outputs/promo_results.json", help="Path to predicted promo_results.json")
    parser.add_argument("--output", default="evaluation/benchmark_report.json", help="Path to save benchmark report")
    args = parser.parse_args()

    results = run_benchmark(args.ground_truth, args.predictions)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("=" * 60)
    print("PROMO BENCHMARK EVALUATION RESULTS")
    print("=" * 60)
    print(f"Total Ground Truth Promos : {results['total_ground_truth']}")
    print(f"Total Predictions         : {results['total_predictions']}")
    print("-" * 60)
    print(f"{'K':<6} | {'Precision':<10} | {'Recall':<10} | {'NDCG':<10} | {'Hits':<6}")
    print("-" * 60)
    for k_key, vals in results["metrics_at_k"].items():
        print(f"{k_key:<6} | {vals['precision']:<10.3f} | {vals['recall']:<10.3f} | {vals['ndcg']:<10.3f} | {vals['hits']:<6}")
    print("-" * 60)
    b_mae = results["boundary_mae"]
    print(f"Boundary MAE -- Start: {b_mae['start_seconds_mae']}s, End: {b_mae['end_seconds_mae']}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
