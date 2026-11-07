"""Tests for Independent LLM-as-a-Judge Module."""

from promo_finder.models import ScreenplayEvent, PromoCandidate, PromoSegment
from promo_finder.judge import RuleBasedJudge, LLMJudge
from promo_finder.config import DEFAULT_CONFIG


def make_tense_candidate():
    events = [
        ScreenplayEvent(
            event_id="EP01_SC01_EV010",
            scene_id=1,
            event_type="DIALOGUE",
            character="GERALD",
            tone="Cruel",
            text="You have no place in this family anymore!",
            start=10.0,
            end=18.0,
        ),
        ScreenplayEvent(
            event_id="EP01_SC01_EV011",
            scene_id=1,
            event_type="DIALOGUE",
            character="JULIANA",
            tone="Defiant",
            text="Who gave you the right to betray my mother's memory?",
            start=18.5,
            end=35.0,
        ),
    ]
    seg = PromoSegment(
        episode_number=1,
        start_time=10.0,
        end_time=35.0,
        start_display="00:10.00",
        end_display="00:35.00",
        event_ids=[e.event_id for e in events],
    )
    return PromoCandidate(
        candidate_id="CAND_TENSE_01",
        episode_number=1,
        start_time=10.0,
        end_time=35.0,
        segments=[seg],
        duration=25.0,
        events=events,
        heuristic_score=8.0,
        hook_signals=["betray"],
    )


def make_leaked_candidate():
    events = [
        ScreenplayEvent(
            event_id="EP01_SC01_EV020",
            scene_id=1,
            event_type="DIALOGUE",
            character="GERALD",
            tone="Angry",
            text="You ruined everything!",
            start=10.0,
            end=18.0,
        ),
        ScreenplayEvent(
            event_id="EP01_SC01_EV021",
            scene_id=1,
            event_type="DIALOGUE",
            character="JULIANA",
            tone="Calm",
            text="Don't worry, they apologized and all is forgiven safely now.",
            start=18.5,
            end=35.0,
        ),
    ]
    seg = PromoSegment(
        episode_number=1,
        start_time=10.0,
        end_time=35.0,
        start_display="00:10.00",
        end_display="00:35.00",
        event_ids=[e.event_id for e in events],
    )
    return PromoCandidate(
        candidate_id="CAND_LEAKED_01",
        episode_number=1,
        start_time=10.0,
        end_time=35.0,
        segments=[seg],
        duration=25.0,
        events=events,
        heuristic_score=6.0,
    )


def test_rule_based_judge_tense_verdict():
    cand = make_tense_candidate()
    judge = RuleBasedJudge(config=DEFAULT_CONFIG)
    eval_res = judge.judge(cand)

    assert eval_res.candidate_id == cand.candidate_id
    assert eval_res.judge_score >= 6.0
    assert eval_res.judge_verdict in ("STRONG", "GOOD")
    assert not eval_res.resolution_leaked
    assert eval_res.strengths != ""


def test_rule_based_judge_premature_resolution_leak():
    cand = make_leaked_candidate()
    judge = RuleBasedJudge(config=DEFAULT_CONFIG)
    eval_res = judge.judge(cand)

    assert eval_res.resolution_leaked
    assert eval_res.judge_verdict == "REJECT"
    assert "resolves" in eval_res.weaknesses.lower()


def test_llm_judge_offline_fallback():
    cand = make_tense_candidate()
    judge = LLMJudge(api_key=None, config=DEFAULT_CONFIG)
    eval_res = judge.judge(cand)

    assert eval_res.judge_score > 0.0
    assert eval_res.judge_verdict != ""
