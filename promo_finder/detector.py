"""
Candidate Detector Module
=========================
Generates event-boundary-snapped promotional candidates from parsed screenplay
episodes. All candidate start and end times snap strictly to actual dialogue or
action events, guaranteeing no sliced sentences or floating seconds.
"""

from typing import List, Tuple
from .models import Episode, ScreenplayEvent, PromoSegment, PromoCandidate
from .heuristics import (
    score_events_heuristics,
    filter_top_candidates,
    precompute_event_signals,
    score_precomputed_events,
)
from .normalizer import format_timestamp


def generate_event_boundary_candidates(
    episode: Episode,
    min_dur: float = 20.0,
    max_dur: float = 60.0,
    max_pre_filter_candidates: int = 60,
) -> List[PromoCandidate]:
    """
    Generate candidates snapped strictly to event boundaries.
    Start event must be DIALOGUE or ACTION.
    End event must be DIALOGUE, ACTION, or meaningful SFX/CAMERA cutoff.
    Duration must satisfy min_dur <= (end_time - start_time) <= max_dur.
    Opening 3 seconds must contain active dialogue or action.
    Optimized with precomputed per-event signals for sub-second execution.
    """
    all_events = episode.get_all_events()
    if not all_events:
        return []

    # Precompute per-event signal sets once for all events in episode
    hooks_list, cliffs_list, emos_list = precompute_event_signals(all_events)

    valid_start_indices = [
        i for i, ev in enumerate(all_events)
        if ev.event_type in ("DIALOGUE", "ACTION")
    ]

    candidate_tuples = []

    for start_idx in valid_start_indices:
        start_ev = all_events[start_idx]
        start_time = start_ev.start

        for end_idx in range(start_idx, len(all_events)):
            end_ev = all_events[end_idx]

            # Scope continuous candidate generation within the same scene
            if end_ev.scene_id != start_ev.scene_id:
                break

            # Only break when start time of end_ev exceeds window ceiling
            # (guarantees all subsequent events also start beyond max_dur)
            if end_ev.start > start_time + max_dur:
                break

            end_time = end_ev.end
            duration = round(end_time - start_time, 2)

            if duration < min_dur or duration > max_dur:
                continue

            if end_ev.event_type not in ("DIALOGUE", "ACTION", "SOUND_FX", "CAMERA"):
                continue

            # start_ev is already guaranteed to be DIALOGUE or ACTION starting at start_time
            # For non-dialogue/action end events (CAMERA / SOUND_FX), verify closing 3.0s has dialogue or action for quotes
            if end_ev.event_type not in ("DIALOGUE", "ACTION"):
                closing_cutoff = max(start_time, end_time - 3.0)
                if not any(all_events[k].event_type in ("DIALOGUE", "ACTION") and all_events[k].end >= closing_cutoff for k in range(end_idx - 1, start_idx - 1, -1)):
                    continue

            # Instant precomputed heuristic scoring
            h_score, hooks, cliffs, emos = score_precomputed_events(
                all_events, start_idx, end_idx, duration, hooks_list, cliffs_list, emos_list
            )
            candidate_tuples.append((
                h_score,
                start_time,
                end_time,
                duration,
                start_idx,
                end_idx,
                hooks,
                cliffs,
                emos,
            ))

    if not candidate_tuples:
        return []

    # Sort descending by heuristic score
    candidate_tuples.sort(key=lambda t: t[0], reverse=True)

    # Instantiate Pydantic models for top candidates
    candidates: List[PromoCandidate] = []
    cand_counter = 1

    for t in candidate_tuples[:max_pre_filter_candidates]:
        h_score, start_time, end_time, duration, start_idx, end_idx, hooks, cliffs, emos = t
        sliced_events = all_events[start_idx : end_idx + 1]
        event_ids = [ev.event_id for ev in sliced_events]

        seg = PromoSegment(
            episode_number=episode.episode_number,
            start_time=start_time,
            end_time=end_time,
            start_display=format_timestamp(start_time),
            end_display=format_timestamp(end_time),
            event_ids=event_ids,
        )

        cand_id = f"CAND_EP{episode.episode_number:02d}_{cand_counter:03d}"
        cand_counter += 1

        cand = PromoCandidate(
            candidate_id=cand_id,
            episode_number=episode.episode_number,
            start_time=start_time,
            end_time=end_time,
            segments=[seg],
            duration=duration,
            events=sliced_events,
            heuristic_score=h_score,
            hook_signals=hooks,
            cliffhanger_signals=cliffs,
            emotional_signals=emos,
        )
        candidates.append(cand)

    return candidates


def detect_candidates(
    episode: Episode,
    min_dur: float = 20.0,
    max_dur: float = 60.0,
    top_k: int = 4,
    include_exploratory: bool = True,
) -> List[PromoCandidate]:
    """
    Detect and pre-filter promo candidates for a single episode.
    Returns the top diverse candidates ranked by context-unbiased heuristic score.
    """
    all_candidates = generate_event_boundary_candidates(episode, min_dur, max_dur)
    return filter_top_candidates(
        all_candidates,
        top_k=top_k,
        include_exploratory=include_exploratory,
    )


def detect_all_candidates(
    episodes: List[Episode],
    min_dur: float = 20.0,
    max_dur: float = 60.0,
    per_episode: int = 4,
    include_exploratory: bool = True,
) -> List[PromoCandidate]:
    """
    Detect candidates across all episodes.
    """
    all_filtered: List[PromoCandidate] = []
    for ep in episodes:
        cands = detect_candidates(
            ep,
            min_dur=min_dur,
            max_dur=max_dur,
            top_k=per_episode,
            include_exploratory=include_exploratory,
        )
        all_filtered.extend(cands)
    return all_filtered
