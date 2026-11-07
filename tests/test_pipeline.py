"""End-to-End Pipeline Tests."""

import json
import os
import shutil
import tempfile
import pytest
from promo_finder.pipeline import run_pipeline
from promo_finder.config import PromoFinderConfig


SCRIPT_DIR = os.path.join(
    "I Married a Broken Soldier. He was a Duke-scripts (2)",
    "I Married a Broken Soldier. He was a Duke",
)


@pytest.fixture
def temp_output_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def small_input_dir():
    # Copy first 3 episodes to a temp directory for quick pipeline test
    d = tempfile.mkdtemp()
    for i in [1, 2, 3]:
        fname = f"episode-{i:03d}"
        for existing in os.listdir(SCRIPT_DIR):
            if existing.startswith(fname):
                shutil.copy(os.path.join(SCRIPT_DIR, existing), os.path.join(d, existing))
                break
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_pipeline_end_to_end_mock_offline(small_input_dir, temp_output_dir):
    config = PromoFinderConfig(
        top_n=5,
        min_duration=20.0,
        max_duration=60.0,
        enable_llm=False,  # deterministic offline mode
        candidates_per_episode=3,
    )

    top_promos = run_pipeline(
        input_folder=small_input_dir,
        output_folder=temp_output_dir,
        config=config,
        verbose=False,
    )

    assert len(top_promos) > 0
    assert len(top_promos) <= 5

    # Check that all 6 files are created
    expected_files = [
        "promo_results.json",
        "promo_results.csv",
        "all_screened_candidates.json",
        "model_responses.jsonl",
        "run_metadata.json",
        "human_feedback.csv",
    ]
    for ef in expected_files:
        p = os.path.join(temp_output_dir, ef)
        assert os.path.exists(p), f"Missing artifact: {ef}"
        assert os.path.getsize(p) > 0, f"Empty artifact: {ef}"

    # Verify JSON content
    with open(os.path.join(temp_output_dir, "promo_results.json"), "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "promos" in data
    assert len(data["promos"]) == len(top_promos)
    for promo in data["promos"]:
        assert promo["passed_quality_gates"] is True
        assert promo["rank"] >= 1
        assert 20.0 <= promo["duration_seconds"] <= 60.0
        assert promo["scores"]["hook_strength"] >= 6.0
        assert promo["scores"]["cliffhanger_strength"] >= 6.0
        assert promo["scores"]["narrative_clarity"] >= 5.0

    # Verify Audit trail content
    with open(os.path.join(temp_output_dir, "all_screened_candidates.json"), "r", encoding="utf-8") as f:
        screened_data = json.load(f)
    assert screened_data["total_screened"] >= len(top_promos)
    assert screened_data["total_passed"] >= len(top_promos)
