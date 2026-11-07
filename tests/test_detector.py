"""Tests for Candidate Detector Module."""

import os
import pytest
from promo_finder.parser import parse_episode
from promo_finder.detector import generate_event_boundary_candidates, detect_candidates


SCRIPT_DIR = os.path.join(
    "I Married a Broken Soldier. He was a Duke-scripts (2)",
    "I Married a Broken Soldier. He was a Duke",
)


@pytest.fixture
def ep1():
    ep1_path = os.path.join(SCRIPT_DIR, "episode-001-Episode 1671703.txt")
    if not os.path.exists(ep1_path):
        pytest.skip("Episode 1 not found")
    return parse_episode(ep1_path)


def test_event_boundary_snapping(ep1):
    candidates = generate_event_boundary_candidates(ep1, min_dur=20.0, max_dur=60.0)
    assert len(candidates) > 0

    all_events = ep1.get_all_events()
    event_start_times = {ev.start for ev in all_events}
    event_end_times = {ev.end for ev in all_events}

    for cand in candidates:
        # Strict snapping check: candidate start must equal some event start
        assert cand.start_time in event_start_times, f"Candidate start {cand.start_time} not snapped to event start"
        # Strict snapping check: candidate end must equal some event end
        assert cand.end_time in event_end_times, f"Candidate end {cand.end_time} not snapped to event end"
        # Duration bound check
        assert 20.0 <= cand.duration <= 60.0, f"Candidate duration {cand.duration} out of [20.0, 60.0] bounds"


def test_opening_3s_dialogue_action(ep1):
    candidates = generate_event_boundary_candidates(ep1, min_dur=20.0, max_dur=60.0)
    for cand in candidates:
        opening_events = [
            ev for ev in cand.events
            if ev.start <= cand.start_time + 3.0 and ev.event_type in ("DIALOGUE", "ACTION")
        ]
        assert len(opening_events) > 0, f"Candidate {cand.candidate_id} missing dialogue/action in first 3s"


def test_detect_candidates_filtering(ep1):
    top_cands = detect_candidates(ep1, min_dur=20.0, max_dur=60.0, top_k=4)
    assert len(top_cands) <= 5
    assert len(top_cands) >= 1
    # Check candidates have heuristic score > 0
    for cand in top_cands:
        assert cand.heuristic_score > 0.0
        assert len(cand.segments) == 1
        assert len(cand.events) > 0


def test_detector_non_monotonic_endpoints():
    from promo_finder.models import Episode, Scene, ScreenplayEvent
    # Construct an episode where an earlier event has end > max_dur, but subsequent event ends within window
    events = [
        ScreenplayEvent(
            event_id="EP99_SC01_EV01",
            scene_id=1,
            event_type="DIALOGUE",
            character="ALEX",
            text="Listen closely to what I say.",
            start=0.0,
            end=5.0,
        ),
        ScreenplayEvent(
            event_id="EP99_SC01_EV02",
            scene_id=1,
            event_type="ACTION",
            text="Long background action spanning past duration boundary.",
            start=10.0,
            end=75.0,  # 75s > max_dur 60s
        ),
        ScreenplayEvent(
            event_id="EP99_SC01_EV03",
            scene_id=1,
            event_type="DIALOGUE",
            character="JULIANA",
            text="Will you help me stop this betrayal?",
            start=12.0,
            end=35.0,  # 35s - perfectly valid [20, 60] promo
        ),
    ]
    scene = Scene(scene_id=1, heading="INT. ROOM - DAY", start=0.0, end=75.0, events=events)
    ep = Episode(episode_number=99, scenes=[scene])

    candidates = generate_event_boundary_candidates(ep, min_dur=20.0, max_dur=60.0)
    # EV01 to EV03 should be detected despite EV02 having a non-monotonic end time > 60s
    assert any(c.end_time == 35.0 for c in candidates), "Non-monotonic endpoint candidate (ending at 35.0s) was skipped!"


def test_detector_camera_cliffhanger_cutoff():
    from promo_finder.models import Episode, Scene, ScreenplayEvent
    events = [
        ScreenplayEvent(
            event_id="EP41_SC01_EV034",
            scene_id=1,
            event_type="DIALOGUE",
            character="JULIANA",
            text="You needed an entire chapel to feel powerful over one chained woman?",
            start=58.0,
            end=60.5,
        ),
        ScreenplayEvent(
            event_id="EP41_SC01_EV052",
            scene_id=1,
            event_type="ACTION",
            text="Silhouetted armed figures emerge through the smoke and rubble of the breached doorway.",
            start=89.0,
            end=93.5,
        ),
        ScreenplayEvent(
            event_id="EP41_SC01_EV053",
            scene_id=1,
            event_type="CAMERA",
            text="Extreme close-up pushing in on Juliana's face as the score swells into an abrupt cliffhanger.",
            start=92.0,
            end=96.09,
        ),
    ]
    scene = Scene(scene_id=1, heading="INT. CATHEDRAL - DAY", start=50.0, end=100.0, events=events)
    ep = Episode(episode_number=41, scenes=[scene])

    candidates = generate_event_boundary_candidates(ep, min_dur=20.0, max_dur=60.0)
    assert any(c.start_time == 58.0 and c.end_time == 96.09 for c in candidates), "Candidate ending on CAMERA cliffhanger (96.09s) was not detected!"


