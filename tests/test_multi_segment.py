"""Tests for Multi-Segment Promo Assembler."""

import os
import pytest
from promo_finder.parser import parse_episode
from promo_finder.multi_segment_assembler import assemble_episode_beats


SCRIPT_DIR = os.path.join(
    "I Married a Broken Soldier. He was a Duke-scripts (2)",
    "I Married a Broken Soldier. He was a Duke",
)


def test_multi_segment_assembly_ep6():
    ep6_path = os.path.join(SCRIPT_DIR, "episode-006-Episode 1671708.txt")
    if not os.path.exists(ep6_path):
        pytest.skip("Episode 6 script not found")

    ep = parse_episode(ep6_path)
    assert len(ep.scenes) >= 2

    candidates = assemble_episode_beats(ep, min_dur=20.0, max_dur=60.0)
    assert len(candidates) > 0

    for cand in candidates:
        assert cand.duration >= 20.0
        assert cand.duration <= 60.0
        # Multi-segment should contain at least 2 distinct segments
        assert len(cand.segments) >= 2
        # Check that segments come from different scenes
        seg_events_map = {ev.event_id: ev.scene_id for ev in cand.events}
        scene_ids_in_cand = set(seg_events_map.values())
        assert len(scene_ids_in_cand) >= 2
        # Provenance check
        for seg in cand.segments:
            assert seg.start_time >= 0.0
            assert seg.end_time > seg.start_time
            assert len(seg.event_ids) > 0


def test_multi_segment_assembly_3_beats():
    ep3_path = os.path.join(SCRIPT_DIR, "episode-003-Episode 1671705.txt")
    if not os.path.exists(ep3_path):
        pytest.skip("Episode 3 script not found")

    ep = parse_episode(ep3_path)
    assert len(ep.scenes) >= 3

    candidates = assemble_episode_beats(ep, min_dur=20.0, max_dur=60.0)
    assert len(candidates) > 0

    # Ensure at least one candidate has 2 or 3 segments with valid duration
    for cand in candidates:
        assert 20.0 <= cand.duration <= 60.0
        assert len(cand.segments) in (2, 3)
        assert cand.duration == round(sum(s.duration for s in cand.segments), 2)
