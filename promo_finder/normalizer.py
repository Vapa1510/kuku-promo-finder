"""
Timestamp, Label, and Text Normalizer.
Provides robust parsing and formatting for varied screenplay conventions.
"""

import re
from typing import Optional, Tuple


_TS_PATTERN = re.compile(r"(?:(\d+):)?(\d+)(?:\.(\d+))?")


def normalize_timestamp(ts_str: str) -> float:
    """
    Parse timestamp string into exact floating-point seconds.
    Accepts:
        '00:11.30', '(00:11.30)', '1:05.6', '01:05', '45.50', '45'
    """
    if not ts_str:
        raise ValueError("Empty timestamp string")

    # Clean enclosing brackets, parentheses, and whitespace
    cleaned = ts_str.strip().strip("()[]{}").strip()

    m = _TS_PATTERN.search(cleaned)
    if not m:
        raise ValueError(f"Cannot parse timestamp from: {ts_str!r}")

    mins_part, secs_part, frac_part = m.groups()
    minutes = int(mins_part) if mins_part is not None else 0
    seconds = int(secs_part)

    if frac_part is not None:
        # Standardize fractional seconds to hundredths
        frac_norm = frac_part.ljust(2, "0")[:2]
        frac_val = int(frac_norm) / 100.0
    else:
        frac_val = 0.0

    total_secs = round(minutes * 60 + seconds + frac_val, 2)
    return total_secs


def format_timestamp(seconds: float) -> str:
    """
    Convert seconds float into canonical 'MM:SS.ff' string.
    """
    if seconds < 0:
        seconds = 0.0
    mins = int(seconds) // 60
    rem = seconds - mins * 60
    whole_secs = int(rem)
    frac = int(round((rem - whole_secs) * 100))
    if frac >= 100:
        whole_secs += 1
        frac = 0
    if whole_secs >= 60:
        mins += whole_secs // 60
        whole_secs = whole_secs % 60
    return f"{mins:02d}:{whole_secs:02d}.{frac:02d}"


def normalize_label(label: str) -> str:
    """
    Normalize screenplay metadata labels for case-insensitive matching.
    Strips markdown asterisks, colons, and excess whitespace.
    Example: '**SCENE HEADING:**' -> 'scene heading'
    """
    cleaned = re.sub(r"[\*#_:\-]+", " ", label)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    return cleaned


def generate_event_id(episode_number: int, scene_number: int, event_idx: int) -> str:
    """
    Generate deterministic, immutable event ID.
    Example: EP01_SC01_EV004
    """
    return f"EP{episode_number:02d}_SC{scene_number:02d}_EV{event_idx:03d}"


def clean_text(text: str) -> str:
    """
    Clean screenplay dialogue/action text.
    Replaces curly/smart quotes with straight quotes and normalizes whitespace.
    """
    if not text:
        return ""
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("‘", "'").replace("’", "'")
    text = re.sub(r"[ \t]+", " ", text).strip()
    return text


_START_END_RE = re.compile(
    r"Start:\s*\(?([0-9:.]+)\)?\s*\|\s*End:\s*\(?([0-9:.]+)\)?",
    re.IGNORECASE
)


def extract_start_end(line: str) -> Optional[Tuple[float, float]]:
    """
    Extract (start_seconds, end_seconds) from line matching:
    'Start: (00:11.30) | End: (01:05.60)' or variations.
    """
    m = _START_END_RE.search(line)
    if m:
        try:
            start_sec = normalize_timestamp(m.group(1))
            end_sec = normalize_timestamp(m.group(2))
            return start_sec, end_sec
        except ValueError:
            return None
    return None
