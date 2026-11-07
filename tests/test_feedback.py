"""Tests for Editorial Feedback and Human Review Module."""

import os
import shutil
import tempfile
import pytest
from promo_finder.feedback import EditorialFeedbackManager
from promo_finder.models import FinalPromoResult


@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_feedback_manager_log_and_metrics(temp_dir):
    csv_path = os.path.join(temp_dir, "feedback.csv")
    mgr = EditorialFeedbackManager(feedback_file=csv_path)

    # Initial metrics
    metrics = mgr.compute_metrics()
    assert metrics["total_reviews"] == 0
    assert metrics["approval_rate"] == 0.0

    # Log reviews
    mgr.log_review("C1", 1, 1, "APPROVED", "Editor Alice", "Great hook")
    mgr.log_review("C2", 1, 2, "REJECTED", "Editor Alice", "Weak ending")
    mgr.log_review("C3", 2, 3, "NEEDS_RECUT", "Editor Bob", "Trim opening")

    metrics2 = mgr.compute_metrics()
    assert metrics2["total_reviews"] == 3
    assert metrics2["approved"] == 1
    assert metrics2["rejected"] == 1
    assert metrics2["needs_recut"] == 1
    assert metrics2["approval_rate"] == 0.333

    # Load from disk with a new manager instance
    mgr2 = EditorialFeedbackManager(feedback_file=csv_path)
    assert len(mgr2.records) == 3
    assert mgr2.records[0].candidate_id == "C1"
    assert mgr2.records[0].decision == "APPROVED"
    assert mgr2.records[1].decision == "REJECTED"


def test_initialize_review_template(temp_dir):
    csv_path = os.path.join(temp_dir, "template.csv")
    mgr = EditorialFeedbackManager()

    promos = [
        FinalPromoResult(
            rank=1,
            candidate_id="C1",
            episode_number=1,
            start_time=10.0,
            end_time=35.0,
            start_display="00:10.00",
            end_display="00:35.00",
            duration_seconds=25.0,
            final_score=9.0,
            candidate_score=9.0,
            judge_score=9.0,
        ),
        FinalPromoResult(
            rank=2,
            candidate_id="C2",
            episode_number=2,
            start_time=15.0,
            end_time=45.0,
            start_display="00:15.00",
            end_display="00:45.00",
            duration_seconds=30.0,
            final_score=8.5,
            candidate_score=8.5,
            judge_score=8.5,
        ),
    ]

    mgr.initialize_review_template(promos, csv_path)
    assert os.path.exists(csv_path)

    loaded = mgr.load_from_csv(csv_path)
    assert len(loaded) == 2
    assert loaded[0].candidate_id == "C1"
    assert loaded[0].decision == "PENDING"
    assert loaded[1].candidate_id == "C2"
