"""
Evidence and Grounding Validator Module
=======================================
Verifies that all LLM evaluation claims, evidence Event IDs, and extracted quotes
strictly map to actual screenplay events and occur within the required time
windows (opening 3 seconds and closing 3 seconds).
"""

from typing import List, Tuple, Dict
from .models import ScreenplayEvent, PromoCandidate, CandidateEvaluation


class EvidenceValidationResult:
    """Outcome of grounding and evidence verification."""
    def __init__(
        self,
        is_valid: bool,
        issues: List[str],
        opening_quote: str,
        closing_quote: str,
        validated_hook_ids: List[str],
        validated_cliff_ids: List[str],
    ):
        self.is_valid = is_valid
        self.issues = issues
        self.opening_quote = opening_quote
        self.closing_quote = closing_quote
        self.validated_hook_ids = validated_hook_ids
        self.validated_cliff_ids = validated_cliff_ids


def validate_candidate_evidence(
    candidate: PromoCandidate,
    evaluation: CandidateEvaluation,
) -> EvidenceValidationResult:
    """
    Validate that:
    1. All hook_evidence_event_ids exist in candidate.events.
    2. At least one hook evidence event starts within [candidate.start_time, candidate.start_time + 3.0s].
    3. All cliffhanger_evidence_event_ids exist in candidate.events.
    4. At least one cliffhanger evidence event ends within [candidate.end_time - 3.0s, candidate.end_time].
    5. Extracts verbatim opening dialogue/action quote and closing quote.
    """
    issues: List[str] = []
    event_map: Dict[str, ScreenplayEvent] = {ev.event_id: ev for ev in candidate.events}

    # 1. Verify Hook Evidence Event IDs
    valid_hook_ids: List[str] = []
    opening_window_end = candidate.start_time + 3.0
    hook_in_opening_window = False

    for ev_id in evaluation.hook_evidence_event_ids:
        if ev_id not in event_map:
            issues.append(f"Hook evidence event ID '{ev_id}' not found in candidate events.")
        else:
            valid_hook_ids.append(ev_id)
            ev = event_map[ev_id]
            if ev.start <= opening_window_end:
                hook_in_opening_window = True

    # Fallback to actual first events if LLM failed to provide valid IDs
    if not valid_hook_ids or not hook_in_opening_window:
        early_events = [ev for ev in candidate.events if ev.start <= opening_window_end]
        if early_events:
            valid_hook_ids = [early_events[0].event_id]
            if not hook_in_opening_window and evaluation.hook_evidence_event_ids:
                issues.append("Hook evidence events did not fall within initial 3 seconds; auto-corrected to first event.")
        else:
            issues.append("No screenplay events found in opening 3-second window.")

    # 2. Verify Cliffhanger Evidence Event IDs
    valid_cliff_ids: List[str] = []
    closing_window_start = max(candidate.start_time, candidate.end_time - 3.0)
    cliff_in_closing_window = False

    for ev_id in evaluation.cliffhanger_evidence_event_ids:
        if ev_id not in event_map:
            issues.append(f"Cliffhanger evidence event ID '{ev_id}' not found in candidate events.")
        else:
            valid_cliff_ids.append(ev_id)
            ev = event_map[ev_id]
            if ev.end >= closing_window_start:
                cliff_in_closing_window = True

    # Fallback to actual final events if LLM failed to provide valid IDs
    if not valid_cliff_ids or not cliff_in_closing_window:
        late_events = [ev for ev in candidate.events if ev.end >= closing_window_start]
        if late_events:
            valid_cliff_ids = [late_events[-1].event_id]
            if not cliff_in_closing_window and evaluation.cliffhanger_evidence_event_ids:
                issues.append("Cliffhanger evidence events did not fall within final 3 seconds; auto-corrected to final event.")
        else:
            issues.append("No screenplay events found in closing 3-second window.")

    # 3. Extract opening quote strictly from dialogue or action in opening 3.0s
    opening_events = [ev for ev in candidate.events if ev.start <= opening_window_end]
    opening_quote = ""
    for ev in opening_events:
        if ev.event_type == "DIALOGUE" and ev.text:
            opening_quote = f"{ev.character}: \"{ev.text}\""
            break
        elif ev.event_type == "ACTION" and not opening_quote and ev.text:
            opening_quote = ev.text

    if not opening_quote:
        issues.append("No dialogue or action event found in opening 3-second window.")

    # 4. Extract closing quote strictly from dialogue or action in closing 3.0s
    closing_events = [ev for ev in candidate.events if ev.end >= closing_window_start]
    closing_quote = ""
    for ev in reversed(closing_events):
        if ev.event_type == "DIALOGUE" and ev.text:
            closing_quote = f"{ev.character}: \"{ev.text}\""
            break
        elif ev.event_type == "ACTION" and not closing_quote and ev.text:
            closing_quote = ev.text

    if not closing_quote:
        issues.append("No dialogue or action event found in closing 3-second window.")

    is_valid = len(issues) == 0

    return EvidenceValidationResult(
        is_valid=is_valid,
        issues=issues,
        opening_quote=opening_quote,
        closing_quote=closing_quote,
        validated_hook_ids=valid_hook_ids,
        validated_cliff_ids=valid_cliff_ids,
    )
