"""Tests for Storage and Caching Module."""

import os
import shutil
import tempfile
import pytest
from promo_finder.storage import CacheManager


@pytest.fixture
def temp_cache_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_cache_manager_get_set(temp_cache_dir):
    mgr = CacheManager(cache_dir=temp_cache_dir)
    key = mgr.generate_key(
        candidate_id="CAND_01",
        text="Sample dialogue text",
        model_name="gemini-2.5-flash",
        prompt_version="v1",
    )
    assert len(key) == 64  # SHA256 hex string

    # Key should initially be missing
    assert mgr.get(key) is None

    # Set value and retrieve
    payload = {"overall_score": 8.5, "editorial_verdict": "STRONG"}
    mgr.set(key, payload)

    retrieved = mgr.get(key)
    assert retrieved is not None
    assert retrieved["overall_score"] == 8.5
    assert retrieved["editorial_verdict"] == "STRONG"

    # Reload new manager from same disk directory
    mgr2 = CacheManager(cache_dir=temp_cache_dir)
    retrieved2 = mgr2.get(key)
    assert retrieved2 == payload


def test_cache_manager_checkpoint(temp_cache_dir):
    mgr = CacheManager(cache_dir=temp_cache_dir)
    ckpt_path = os.path.join(temp_cache_dir, "test_checkpoint.json")

    # Missing checkpoint
    assert mgr.load_checkpoint(ckpt_path) is None

    # Save and reload checkpoint
    data = {"step": 4, "candidates_processed": 50}
    mgr.save_checkpoint(ckpt_path, data)

    loaded = mgr.load_checkpoint(ckpt_path)
    assert loaded is not None
    assert loaded["step"] == 4
    assert loaded["candidates_processed"] == 50


def test_compute_input_fingerprint(temp_cache_dir):
    from promo_finder.storage import compute_input_fingerprint
    f1 = os.path.join(temp_cache_dir, "ep1.txt")
    with open(f1, "w") as f:
        f.write("Episode 1 content")
    cfg = {"min_duration": 20.0, "max_duration": 60.0, "enable_llm": False}

    fp1 = compute_input_fingerprint(temp_cache_dir, cfg)
    assert len(fp1) == 64

    fp2 = compute_input_fingerprint(temp_cache_dir, cfg)
    assert fp1 == fp2

    with open(f1, "a") as f:
        f.write(" appended text")
    fp3 = compute_input_fingerprint(temp_cache_dir, cfg)
    assert fp1 != fp3

