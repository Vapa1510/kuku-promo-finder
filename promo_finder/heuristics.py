"""
Heuristics Module for Context-Unbiased Candidate Pre-Filtering
=============================================================
Computes narrative signal scores strictly from local segment events (dialogue,
tones, actions, SFX). Does NOT use global episode loglines or continuity notes,
preventing context bias.
"""

import re
from typing import List, Tuple, Set
from .models import ScreenplayEvent, PromoCandidate


# Compiled word-boundary regexes to prevent false positives (e.g. 'rage' in 'courage', 'heir' in 'their')
HOOK_PATTERNS = [
    re.compile(r"\bbetray(?:al|ed|ing|s)?\b", re.I),
    re.compile(r"\bbetrothed\b", re.I),
    re.compile(r"\bwedding\b", re.I),
    re.compile(r"\baltar\b", re.I),
    re.compile(r"\babandon(?:ed|ing|s)?\b", re.I),
    re.compile(r"\bhumiliat(?:ed|ion|ing)\b", re.I),
    re.compile(r"\bscandal\b", re.I),
    re.compile(r"\bpoison(?:ed|ous)?\b", re.I),
    re.compile(r"\bmurder(?:ed|er|ing)?\b", re.I),
    re.compile(r"\bkill(?:ed|ing|s)?\b", re.I),
    re.compile(r"\bdeath\b", re.I),
    re.compile(r"\barrest(?:ed|ing)?\b", re.I),
    re.compile(r"\btraitor\b", re.I),
    re.compile(r"\bchains?\b", re.I),
    re.compile(r"\bshackles?\b", re.I),
    re.compile(r"\bthreat(?:en|ened|ening)?\b", re.I),
    re.compile(r"\bwarning\b", re.I),
    re.compile(r"\bconfront(?:ed|ing|ation)?\b", re.I),
    re.compile(r"\bexplos(?:ion|ive|e|ed)\b", re.I),
    re.compile(r"\bbomb\b", re.I),
    re.compile(r"\bsecret\b", re.I),
    re.compile(r"\breveal(?:ed|ing)?\b", re.I),
    re.compile(r"\bdisgrace\b", re.I),
    re.compile(r"\bduke\b", re.I),
    re.compile(r"\bduchess\b", re.I),
    re.compile(r"\bmarry\b", re.I),
    re.compile(r"\bmarriage\b", re.I),
    re.compile(r"\bbride\b", re.I),
    re.compile(r"\bgroom\b", re.I),
    re.compile(r"\bcathedral\b", re.I),
    re.compile(r"\bchapel\b", re.I),
    re.compile(r"\bcancel(?:ed|led|ing)?\b", re.I),
    re.compile(r"\binterfer(?:e|ed|ing)?\b", re.I),
    re.compile(r"\bdefenseless\b", re.I),
    re.compile(r"\bdetonat(?:e|ed|ing|ion)\b", re.I),
    re.compile(r"\bfireball\b", re.I),
]

EMOTIONAL_PATTERNS = [
    re.compile(r"\btears\b", re.I),
    re.compile(r"\bcry(?:ing|ies)?\b", re.I),
    re.compile(r"\bweep(?:ing|s)?\b", re.I),
    re.compile(r"\bsobb?ing\b", re.I),
    re.compile(r"\bdevastat(?:ed|ing)\b", re.I),
    re.compile(r"\bheartbroken\b", re.I),
    re.compile(r"\bfurious\b", re.I),
    re.compile(r"\bfury\b", re.I),
    re.compile(r"\brage\b", re.I),
    re.compile(r"\banger\b", re.I),
    re.compile(r"\boutraged\b", re.I),
    re.compile(r"\bseething\b", re.I),
    re.compile(r"\btrembl(?:ing|e|ed)\b", re.I),
    re.compile(r"\bshak(?:ing|y)\b", re.I),
    re.compile(r"\bgasp(?:ing|ed|s)?\b", re.I),
    re.compile(r"\bdesperat(?:e|ion)\b", re.I),
    re.compile(r"\bplead(?:ing|ed|s)?\b", re.I),
    re.compile(r"\bbeg(?:ging|ged)?\b", re.I),
    re.compile(r"\bdefian(?:t|ce)\b", re.I),
    re.compile(r"\bfierce\b", re.I),
    re.compile(r"\bhorror\b", re.I),
    re.compile(r"\bhorrif(?:ied|ying)\b", re.I),
    re.compile(r"\bterrif(?:ied|ying)\b", re.I),
    re.compile(r"\bafraid\b", re.I),
    re.compile(r"\bfear\b", re.I),
]

CLIFFHANGER_PATTERNS = [
    re.compile(r"\bfade to black\b", re.I),
    re.compile(r"\bcut to black\b", re.I),
    re.compile(r"\bcliffhanger\b", re.I),
    re.compile(r"\bswells?\b", re.I),
    re.compile(r"\bsilhouette\b", re.I),
    re.compile(r"\bemerges?\b", re.I),
    re.compile(r"\bsmoke\b", re.I),
    re.compile(r"\bdarkness\b", re.I),
    re.compile(r"\bstunned\b", re.I),
    re.compile(r"\bshocked\b", re.I),
    re.compile(r"\bbreathless\b", re.I),
    re.compile(r"\bwho are you\b", re.I),
    re.compile(r"\bnever\b", re.I),
    re.compile(r"\btoo late\b", re.I),
    re.compile(r"\bstop\b", re.I),
    re.compile(r"\bwait\b", re.I),
    re.compile(r"\bplease\b", re.I),
    re.compile(r"\baccept my hand\b", re.I),
    re.compile(r"\bmarry me\b", re.I),
    re.compile(r"\bpropos(?:e|ed|al|ing)\b", re.I),
    re.compile(r"\bring\b", re.I),
    re.compile(r"\bmy wife\b", re.I),
    re.compile(r"\bswore\b", re.I),
]


def extract_matched_signals(text: str, patterns: List[re.Pattern]) -> List[str]:
    """Find unique matched terms using word-boundary regex patterns."""
    found: Set[str] = set()
    for pat in patterns:
        m = pat.search(text)
        if m:
            found.add(m.group(0).lower())
    return sorted(list(found))


def score_events_heuristics(
    events: List[ScreenplayEvent],
    duration: float,
) -> Tuple[float, List[str], List[str], List[str]]:
    """
    Score a sequence of events based strictly on internal content.
    Returns:
        (heuristic_score_0_to_10, hook_signals, cliff_signals, emo_signals)
    """
    if not events or duration <= 0:
        return 0.0, [], [], []

    # Aggregate text strictly according to temporal windows
    start_t = events[0].start
    end_t = events[-1].end
    opening_cutoff = start_t + 3.0
    closing_cutoff = max(start_t, end_t - 3.0)

    # Strictly opening 3.0s
    opening_events = [ev for ev in events if ev.start <= opening_cutoff]
    opening_text = " ".join(f"{ev.text} {ev.tone or ''}" for ev in opening_events)

    # Strictly closing 3.0s
    closing_events = [ev for ev in events if ev.end >= closing_cutoff]
    closing_text = " ".join(f"{ev.text} {ev.tone or ''}" for ev in closing_events)

    # Emotional signals across segment
    text_content = " ".join(f"{ev.text} {ev.tone or ''}" for ev in events)
    emo_signals = extract_matched_signals(text_content, EMOTIONAL_PATTERNS)

    # 1. Opening hook score (0-10) strictly from opening 3.0s
    hook_signals = extract_matched_signals(opening_text, HOOK_PATTERNS)
    opening_emo_matches = extract_matched_signals(opening_text, EMOTIONAL_PATTERNS)
    hook_score = min(10.0, len(hook_signals) * 3.5 + len(opening_emo_matches) * 2.0 + (3.0 if hook_signals else 1.0))

    # 2. Cliffhanger score (0-10) strictly from closing 3.0s
    cliff_signals = extract_matched_signals(closing_text, CLIFFHANGER_PATTERNS)
    has_question_at_end = any(ev.text.strip().endswith("?") for ev in closing_events)
    has_exclamation_at_end = any(ev.text.strip().endswith("!") for ev in closing_events)
    ending_has_dialogue = any(ev.event_type == "DIALOGUE" for ev in closing_events)
    base_cliff = 3.5 if ending_has_dialogue else 2.0
    cliff_score = min(
        10.0,
        base_cliff
        + len(cliff_signals) * 2.5
        + (3.0 if has_question_at_end else (2.0 if has_exclamation_at_end else 0.0))
    )

    # 3. Dialogue density & Character dynamics
    dialogue_events = [ev for ev in events if ev.event_type == "DIALOGUE"]
    action_events = [ev for ev in events if ev.event_type == "ACTION"]
    characters = {ev.character for ev in dialogue_events if ev.character}

    # Ideal promo: 4 to 10 dialogue lines, at least 2 interacting characters
    diag_count_score = min(5.0, len(dialogue_events) * 0.8)
    char_dynamics_score = min(3.0, len(characters) * 1.5)
    action_score = min(2.0, len(action_events) * 0.5)
    density_score = diag_count_score + char_dynamics_score + action_score

    # 4. Emotional intensity score (0-10)
    emo_score = min(10.0, len(emo_signals) * 2.5 + (2.0 if len(emo_signals) > 0 else 0.0))

    # Composite heuristic score (0.0 to 10.0)
    raw_score = (
        hook_score * 0.35
        + cliff_score * 0.30
        + emo_score * 0.20
        + density_score * 0.15
    )

    final_score = round(min(10.0, max(0.0, raw_score)), 2)
    return final_score, hook_signals, cliff_signals, emo_signals


def precompute_event_signals(events: List[ScreenplayEvent]) -> Tuple[List[Set[str]], List[Set[str]], List[Set[str]]]:
    """Precompute matched signal sets for each individual event once."""
    hooks_list: List[Set[str]] = []
    cliffs_list: List[Set[str]] = []
    emos_list: List[Set[str]] = []

    for ev in events:
        text = f"{ev.text} {ev.tone or ''}"
        hooks_list.append(set(extract_matched_signals(text, HOOK_PATTERNS)))
        cliffs_list.append(set(extract_matched_signals(text, CLIFFHANGER_PATTERNS)))
        emos_list.append(set(extract_matched_signals(text, EMOTIONAL_PATTERNS)))

    return hooks_list, cliffs_list, emos_list


def score_precomputed_events(
    events: List[ScreenplayEvent],
    start_idx: int,
    end_idx: int,
    duration: float,
    hooks_list: List[Set[str]],
    cliffs_list: List[Set[str]],
    emos_list: List[Set[str]],
) -> Tuple[float, List[str], List[str], List[str]]:
    """Fast scoring using precomputed per-event signal sets."""
    if duration <= 0:
        return 0.0, [], [], []

    start_t = events[start_idx].start
    end_t = events[end_idx].end
    opening_cutoff = start_t + 3.0
    closing_cutoff = max(start_t, end_t - 3.0)

    all_emos: Set[str] = set()
    opening_hooks: Set[str] = set()
    opening_emos: Set[str] = set()
    closing_cliffs: Set[str] = set()

    for idx in range(start_idx, end_idx + 1):
        ev = events[idx]
        all_emos.update(emos_list[idx])
        if ev.start <= opening_cutoff:
            opening_hooks.update(hooks_list[idx])
            opening_emos.update(emos_list[idx])
        if ev.end >= closing_cutoff:
            closing_cliffs.update(cliffs_list[idx])

    hook_score = min(10.0, len(opening_hooks) * 3.5 + len(opening_emos) * 2.0 + (3.0 if opening_hooks else 1.0))

    closing_events = [events[idx] for idx in range(start_idx, end_idx + 1) if events[idx].end >= closing_cutoff]
    has_question_at_end = any(ev.text.strip().endswith("?") for ev in closing_events)
    has_exclamation_at_end = any(ev.text.strip().endswith("!") for ev in closing_events)
    ending_has_dialogue = any(ev.event_type == "DIALOGUE" for ev in closing_events)
    base_cliff = 3.5 if ending_has_dialogue else 2.0
    cliff_score = min(
        10.0,
        base_cliff
        + len(closing_cliffs) * 2.5
        + (3.0 if has_question_at_end else (2.0 if has_exclamation_at_end else 0.0))
    )

    dialogue_count = sum(1 for idx in range(start_idx, end_idx + 1) if events[idx].event_type == "DIALOGUE")
    action_count = sum(1 for idx in range(start_idx, end_idx + 1) if events[idx].event_type == "ACTION")
    characters = {events[idx].character for idx in range(start_idx, end_idx + 1) if events[idx].event_type == "DIALOGUE" and events[idx].character}

    diag_count_score = min(5.0, dialogue_count * 0.8)
    char_dynamics_score = min(3.0, len(characters) * 1.5)
    action_score = min(2.0, action_count * 0.5)
    density_score = diag_count_score + char_dynamics_score + action_score

    emo_score = min(10.0, len(all_emos) * 2.5 + (2.0 if len(all_emos) > 0 else 0.0))

    raw_score = (
        hook_score * 0.35
        + cliff_score * 0.30
        + emo_score * 0.20
        + density_score * 0.15
    )

    final_score = round(min(10.0, max(0.0, raw_score)), 2)
    return final_score, sorted(list(opening_hooks)), sorted(list(closing_cliffs)), sorted(list(all_emos))


def filter_top_candidates(
    candidates: List[PromoCandidate],
    top_k: int = 4,
    include_exploratory: bool = True,
) -> List[PromoCandidate]:
    """
    Select top candidates for an episode using heuristic scores and IoU spacing.
    Ensures diverse candidates without redundant overlapping windows.
    """
    if not candidates:
        return []

    # Sort descending by heuristic score
    sorted_cands = sorted(candidates, key=lambda c: c.heuristic_score, reverse=True)
    selected: List[PromoCandidate] = []

    for cand in sorted_cands:
        # Check overlap with already selected
        overlap_found = False
        for s in selected:
            ov_start = max(cand.start_time, s.start_time)
            ov_end = min(cand.end_time, s.end_time)
            overlap = max(0.0, ov_end - ov_start)
            union = max(cand.end_time, s.end_time) - min(cand.start_time, s.start_time)
            iou = (overlap / union) if union > 0 else 0.0

            if iou > 0.40:
                overlap_found = True
                break

        if not overlap_found:
            selected.append(cand)
            if len(selected) >= top_k:
                break

    # If exploratory slot requested and we have room, add a candidate from the end of the episode (climax)
    if include_exploratory and len(selected) < top_k + 1:
        # Look for the latest ending candidate not overlapping
        late_cands = sorted(candidates, key=lambda c: c.end_time, reverse=True)
        for lc in late_cands:
            if lc not in selected:
                # check iou
                if not any(
                    (max(0.0, min(lc.end_time, s.end_time) - max(lc.start_time, s.start_time)) /
                     (max(lc.end_time, s.end_time) - min(lc.start_time, s.start_time))) > 0.40
                    for s in selected
                ):
                    selected.append(lc)
                    break

    return selected
