"""
Editorial Feedback and Human Review Module
==========================================
Manages editorial sign-off, approval/rejection logging, and review metrics.
Enables continuous alignment between human editorial judgment and AI scoring.
"""

import csv
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from .models import HumanReviewRecord, FinalPromoResult


class EditorialFeedbackManager:
    """Manages editorial review tracking and feedback records."""

    def __init__(self, feedback_file: Optional[str] = None):
        self.feedback_file = feedback_file
        self.records: List[HumanReviewRecord] = []
        if feedback_file and Path(feedback_file).exists():
            self.load_from_csv(feedback_file)

    def log_review(
        self,
        candidate_id: str,
        episode_number: int,
        rank: int,
        decision: str,  # APPROVED, REJECTED, NEEDS_RECUT
        reviewer_name: str,
        notes: str = "",
    ) -> HumanReviewRecord:
        """Record an editorial decision."""
        record = HumanReviewRecord(
            candidate_id=candidate_id,
            episode_number=episode_number,
            rank=rank,
            decision=decision.upper(),
            reviewer_name=reviewer_name,
            notes=notes,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
        self.records.append(record)
        if self.feedback_file:
            self.save_to_csv(self.feedback_file)
        return record

    def initialize_review_template(self, promos: List[FinalPromoResult], filepath: str) -> None:
        """Create empty feedback template for editors with pending status."""
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        fieldnames = ["candidate_id", "episode_number", "rank", "decision", "reviewer_name", "notes", "timestamp"]

        with open(filepath, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for p in promos:
                writer.writerow({
                    "candidate_id": p.candidate_id,
                    "episode_number": p.episode_number,
                    "rank": p.rank,
                    "decision": "PENDING",
                    "reviewer_name": "",
                    "notes": "",
                    "timestamp": "",
                })

    def save_to_csv(self, filepath: str) -> None:
        """Persist records to CSV."""
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        fieldnames = ["candidate_id", "episode_number", "rank", "decision", "reviewer_name", "notes", "timestamp"]
        with open(filepath, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in self.records:
                writer.writerow(r.model_dump())

    def load_from_csv(self, filepath: str) -> List[HumanReviewRecord]:
        """Load records from CSV."""
        self.records = []
        if not Path(filepath).exists():
            return []
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rec = HumanReviewRecord(
                    candidate_id=row.get("candidate_id", ""),
                    episode_number=int(row.get("episode_number", 0)),
                    rank=int(row.get("rank", 0)),
                    decision=row.get("decision", "PENDING"),
                    reviewer_name=row.get("reviewer_name", ""),
                    notes=row.get("notes", ""),
                    timestamp=row.get("timestamp", ""),
                )
                self.records.append(rec)
        return self.records

    def compute_metrics(self) -> Dict[str, Any]:
        """Compute editor review stats."""
        total = len(self.records)
        if total == 0:
            return {"total_reviews": 0, "approved": 0, "rejected": 0, "needs_recut": 0, "approval_rate": 0.0}

        approved = sum(1 for r in self.records if r.decision == "APPROVED")
        rejected = sum(1 for r in self.records if r.decision == "REJECTED")
        recut = sum(1 for r in self.records if r.decision == "NEEDS_RECUT")

        return {
            "total_reviews": total,
            "approved": approved,
            "rejected": rejected,
            "needs_recut": recut,
            "approval_rate": round(approved / total, 3) if total > 0 else 0.0,
        }
