"""Tests for Screenplay Parser Module."""

import os
import pytest
from promo_finder.parser import parse_episode, load_all_episodes


SCRIPT_DIR = os.path.join(
    "I Married a Broken Soldier. He was a Duke-scripts (2)",
    "I Married a Broken Soldier. He was a Duke",
)


def test_parse_episode_1():
    ep1_path = os.path.join(SCRIPT_DIR, "episode-001-Episode 1671703.txt")
    if not os.path.exists(ep1_path):
        pytest.skip(f"Script file not found: {ep1_path}")

    ep = parse_episode(ep1_path)
    assert ep.episode_number == 1
    assert "Juliana" in ep.logline
    assert len(ep.scenes) >= 1

    events = ep.get_all_events()
    assert len(events) >= 50

    first_ev = events[0]
    assert first_ev.event_id == "EP01_SC01_EV001"
    assert first_ev.start >= 0.0
    assert first_ev.end > first_ev.start

    # Check that dialogue events have characters
    dialogue_events = [ev for ev in events if ev.event_type == "DIALOGUE"]
    assert len(dialogue_events) > 10
    assert any(ev.character == "LADY JULIANA" or "JULIANA" in (ev.character or "") for ev in dialogue_events)


def test_parse_episode_6_uppercase():
    ep6_path = os.path.join(SCRIPT_DIR, "episode-006-Episode 1671708.txt")
    if not os.path.exists(ep6_path):
        pytest.skip(f"Script file not found: {ep6_path}")

    ep = parse_episode(ep6_path)
    assert ep.episode_number == 6
    assert len(ep.scenes) >= 1

    events = ep.get_all_events()
    assert len(events) >= 50
    assert events[0].event_id.startswith("EP06_SC")


def test_parse_episode_41():
    ep41_path = os.path.join(SCRIPT_DIR, "episode-041-Episode 1686801.txt")
    if not os.path.exists(ep41_path):
        pytest.skip(f"Script file not found: {ep41_path}")

    ep = parse_episode(ep41_path)
    assert ep.episode_number == 41
    events = ep.get_all_events()
    assert len(events) > 0


def test_load_all_episodes():
    if not os.path.exists(SCRIPT_DIR):
        pytest.skip("Screenplays directory not found")

    episodes = load_all_episodes(SCRIPT_DIR)
    assert len(episodes) == 50
    # Ensure they are sorted 1 to 50
    assert episodes[0].episode_number == 1
    assert episodes[-1].episode_number == 50
