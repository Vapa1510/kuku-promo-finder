"""
Multi-Segment Promo Assembler Module
====================================
Stitches 2 to 3 coherent narrative beats across scenes or episodes within
the 20 to 60-second limit, preserving discrete timecodes and full provenance
for vertical video trailers.
"""

from typing import List, Optional
from .models import Episode, ScreenplayEvent, PromoSegment, PromoCandidate
from .normalizer import format_timestamp
from .heuristics import score_events_heuristics


def assemble_episode_beats(
    episode: Episode,
    min_dur: float = 20.0,
    max_dur: float = 60.0,
) -> List[PromoCandidate]:
    """
    Assemble 2-beat or 3-beat promotional cuts from within an episode across different scenes.
    Beat 1: Opening hook (scene 1 or inciting dialogue) [8-20s]
    Beat 2: Climax or confrontation beat [8-22s]
    Beat 3: Unresolved cliffhanger ending beat [8-20s]
    """
    if len(episode.scenes) < 2:
        return []

    scenes = episode.scenes

    # Extract short coherent narrative beats from each scene
    scene_beats = []
    for sc in scenes:
        dialogue_events = [ev for ev in sc.events if ev.event_type in ("DIALOGUE", "ACTION")]
        if not dialogue_events:
            continue

        sc_beat_candidates = []
        for i in range(len(dialogue_events)):
            s_ev = dialogue_events[i]
            for j in range(i, min(i + 8, len(dialogue_events))):
                e_ev = dialogue_events[j]
                dur = round(e_ev.end - s_ev.start, 2)
                if 8.0 <= dur <= 22.0:
                    ev_slice = [ev for ev in sc.events if s_ev.start <= ev.start and ev.end <= e_ev.end]
                    ends_with_dialogue = any(ev.event_type == "DIALOGUE" for ev in ev_slice[-2:])
                    has_question = any(ev.text.strip().endswith("?") for ev in ev_slice[-2:])
                    has_exclamation = any(ev.text.strip().endswith("!") for ev in ev_slice[-2:])
                    cliff_potential = has_question or has_exclamation or ends_with_dialogue
                    score, _, _, _ = score_events_heuristics(ev_slice, dur)

                    seg = PromoSegment(
                        episode_number=episode.episode_number,
                        start_time=s_ev.start,
                        end_time=e_ev.end,
                        start_display=format_timestamp(s_ev.start),
                        end_display=format_timestamp(e_ev.end),
                        event_ids=[ev.event_id for ev in ev_slice],
                    )
                    sc_beat_candidates.append((score, (sc.scene_id, seg, ev_slice, cliff_potential)))
                    break  # One beat per start index

        sc_beat_candidates.sort(key=lambda t: t[0], reverse=True)
        for _, b in sc_beat_candidates[:3]:
            scene_beats.append(b)

    generated_cands: List[PromoCandidate] = []
    cand_counter = 1

    # 1. 2-Beat combinations across distinct scenes
    for i in range(len(scene_beats)):
        sc_id_1, seg1, evs1, _ = scene_beats[i]
        for j in range(i + 1, len(scene_beats)):
            sc_id_2, seg2, evs2, cliff_pot2 = scene_beats[j]
            if sc_id_1 >= sc_id_2:
                continue

            total_dur = round(seg1.duration + seg2.duration, 2)
            if min_dur <= total_dur <= max_dur:
                combined_events = evs1 + evs2
                h_score, hooks, cliffs, emos = score_events_heuristics(combined_events, total_dur)
                if cliff_pot2:
                    h_score = min(10.0, h_score + 0.5)

                cand_id = f"MULTI_EP{episode.episode_number:02d}_{cand_counter:03d}"
                cand_counter += 1

                candidate = PromoCandidate(
                    candidate_id=cand_id,
                    episode_number=episode.episode_number,
                    start_time=seg1.start_time,
                    end_time=seg2.end_time,
                    segments=[seg1, seg2],
                    duration=total_dur,
                    events=combined_events,
                    heuristic_score=h_score,
                    hook_signals=hooks,
                    cliffhanger_signals=cliffs,
                    emotional_signals=emos,
                )
                generated_cands.append(candidate)

    # 2. 3-Beat combinations across 3 distinct scenes in chronological order
    if len(scenes) >= 3:
        for i in range(len(scene_beats)):
            sc_id_1, seg1, evs1, _ = scene_beats[i]
            for j in range(i + 1, len(scene_beats)):
                sc_id_2, seg2, evs2, _ = scene_beats[j]
                if sc_id_1 >= sc_id_2:
                    continue
                for k in range(j + 1, len(scene_beats)):
                    sc_id_3, seg3, evs3, cliff_pot3 = scene_beats[k]
                    if sc_id_2 >= sc_id_3:
                        continue

                    total_dur = round(seg1.duration + seg2.duration + seg3.duration, 2)
                    if min_dur <= total_dur <= max_dur:
                        combined_events = evs1 + evs2 + evs3
                        h_score, hooks, cliffs, emos = score_events_heuristics(combined_events, total_dur)
                        if cliff_pot3:
                            h_score = min(10.0, h_score + 0.5)

                        cand_id = f"MULTI_EP{episode.episode_number:02d}_{cand_counter:03d}"
                        cand_counter += 1

                        candidate = PromoCandidate(
                            candidate_id=cand_id,
                            episode_number=episode.episode_number,
                            start_time=seg1.start_time,
                            end_time=seg3.end_time,
                            segments=[seg1, seg2, seg3],
                            duration=total_dur,
                            events=combined_events,
                            heuristic_score=h_score,
                            hook_signals=hooks,
                            cliffhanger_signals=cliffs,
                            emotional_signals=emos,
                        )
                        generated_cands.append(candidate)

    if not generated_cands:
        return []

    # Sort descending by heuristic score and return top candidates
    generated_cands.sort(key=lambda c: c.heuristic_score, reverse=True)
    return generated_cands[:4]


def assemble_multi_segment_candidates(
    episodes: List[Episode],
    min_dur: float = 20.0,
    max_dur: float = 60.0,
    max_per_ep: int = 2,
) -> List[PromoCandidate]:
    """Assemble multi-segment candidates across the episode collection."""
    all_multi: List[PromoCandidate] = []
    for ep in episodes:
        cands = assemble_episode_beats(ep, min_dur, max_dur)
        all_multi.extend(cands[:max_per_ep])
    return all_multi
