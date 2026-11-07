"""Tests for Context-Unbiased Heuristics Module."""

from promo_finder.models import ScreenplayEvent
from promo_finder.heuristics import (
    score_events_heuristics,
    extract_matched_signals,
    HOOK_PATTERNS,
    EMOTIONAL_PATTERNS,
)


def test_word_boundary_regex_no_false_positives():
    # 'courage' should not match 'rage'
    # 'their' should not match 'heir'
    safe_text = "She had great courage and gave their soldiers full encouragement."
    matched_hooks = extract_matched_signals(safe_text, HOOK_PATTERNS)
    matched_emos = extract_matched_signals(safe_text, EMOTIONAL_PATTERNS)

    assert "rage" not in matched_hooks
    assert "rage" not in matched_emos
    assert "heir" not in matched_hooks


def test_word_boundary_regex_true_positives():
    dramatic_text = "You betrayed me at the wedding altar! You are a traitor to the Duke!"
    matched_hooks = extract_matched_signals(dramatic_text, HOOK_PATTERNS)

    assert "betrayed" in matched_hooks
    assert "wedding" in matched_hooks
    assert "altar" in matched_hooks
    assert "traitor" in matched_hooks
    assert "duke" in matched_hooks


def test_context_unbiased_scoring():
    # Build events sequence with no logline or continuity
    events = [
        ScreenplayEvent(
            event_id="EP01_SC01_EV001",
            scene_id=1,
            event_type="DIALOGUE",
            character="GERALD",
            tone="Cruel",
            text="You should turn around, Juliana. The wedding is canceled.",
            start=11.30,
            end=15.00,
            source_line=45,
        ),
        ScreenplayEvent(
            event_id="EP01_SC01_EV002",
            scene_id=1,
            event_type="DIALOGUE",
            character="JULIANA",
            tone="Tearful, Devastated",
            text="Gerald, why are you holding Clarissa's hand?",
            start=15.20,
            end=20.00,
            source_line=50,
        ),
        ScreenplayEvent(
            event_id="EP01_SC01_EV003",
            scene_id=1,
            event_type="DIALOGUE",
            character="GERALD",
            tone="Cold",
            text="Because she is my bride now. Leave this cathedral at once!",
            start=20.50,
            end=35.00,
            source_line=55,
        ),
    ]

    score, hooks, cliffs, emos = score_events_heuristics(events, duration=23.70)
    assert score >= 6.0
    assert "wedding" in hooks
    assert len(emos) >= 1


def test_heuristics_temporal_windowing():
    # Hook keyword in middle of clip (t=10s) should NOT be captured as opening hook
    events_middle_hook = [
        ScreenplayEvent(
            event_id="EV01",
            scene_id=1,
            event_type="DIALOGUE",
            character="JULIANA",
            text="Good morning to you, Gerald.",
            start=0.0,
            end=2.5,
        ),
        ScreenplayEvent(
            event_id="EV02",
            scene_id=1,
            event_type="DIALOGUE",
            character="GERALD",
            text="This is an altar betrayal and murder!",
            start=10.0,
            end=14.0,
        ),
        ScreenplayEvent(
            event_id="EV03",
            scene_id=1,
            event_type="DIALOGUE",
            character="JULIANA",
            text="I will take my leave now.",
            start=25.0,
            end=28.0,
        ),
    ]

    score, hooks, cliffs, emos = score_events_heuristics(events_middle_hook, duration=28.0)
    assert "betrayal" not in hooks
    assert "altar" not in hooks
    assert "murder" not in hooks
    assert len(cliffs) == 0

    # When hook is in the opening 3 seconds:
    events_opening_hook = [
        ScreenplayEvent(
            event_id="EV01",
            scene_id=1,
            event_type="DIALOGUE",
            character="JULIANA",
            text="You betrayed me at the altar!",
            start=0.0,
            end=2.5,
        ),
        ScreenplayEvent(
            event_id="EV02",
            scene_id=1,
            event_type="DIALOGUE",
            character="GERALD",
            text="I don't care.",
            start=10.0,
            end=14.0,
        ),
        ScreenplayEvent(
            event_id="EV03",
            scene_id=1,
            event_type="DIALOGUE",
            character="JULIANA",
            text="Wait! Who are you?",
            start=25.0,
            end=28.0,
        ),
    ]
    score2, hooks2, cliffs2, emos2 = score_events_heuristics(events_opening_hook, duration=28.0)
    assert "betrayed" in hooks2
    assert "altar" in hooks2
    assert "who are you" in cliffs2 or "wait" in cliffs2
    assert score2 > score

