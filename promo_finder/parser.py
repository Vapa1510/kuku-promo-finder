"""
Screenplay Parser Module
========================
Extracts structured data from screenplay text files. Assigns stable event IDs,
normalizes timestamps and labels, handles uppercase/lowercase format variations,
and records source file line numbers.
"""

import os
import re
from typing import Optional, List, Tuple

from .models import ScreenplayEvent, Scene, Episode
from .normalizer import (
    normalize_timestamp,
    format_timestamp,
    normalize_label,
    generate_event_id,
    clean_text,
    extract_start_end,
)


_BLOCK_HEADER_RE = re.compile(
    r"^\*\*([A-Za-z0-9 /.'()\-]+?)(?:\s*\(([^)]*)\))?\s*:\*\*$"
)


def _classify_event_type(header: str) -> str:
    """Classify the event type from the bold block header."""
    h = header.strip().upper()
    if h.startswith("CAMERA"):
        return "CAMERA"
    if h.startswith("ACTION"):
        return "ACTION"
    if h.startswith("SOUND"):
        return "SOUND_FX"
    return "DIALOGUE"


def _extract_character_and_tone(header: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract (character, tone) from a header like:
    '**LADY JULIANA (Trembling, Pleading):**'
    """
    m = _BLOCK_HEADER_RE.match(header.strip())
    if not m:
        return None, None

    raw_name = m.group(1).strip()
    tone = m.group(2).strip() if m.group(2) else None

    # Strip voice-over / off-screen tags
    raw_name = re.sub(r"\s*\((?:O\.?S\.?|V\.?O\.?)\)\s*$", "", raw_name).strip()
    etype = _classify_event_type(raw_name)

    if etype == "DIALOGUE":
        return raw_name, tone
    return None, tone


def parse_episode(filepath: str) -> Episode:
    """Parse a single screenplay text file into an Episode object."""
    with open(filepath, "r", encoding="utf-8") as fh:
        raw = fh.read()

    lines = raw.splitlines()

    # --- Header fields (case-insensitive) ---
    ep_number = 0
    logline = ""
    continuity = ""

    for line in lines[:20]:
        stripped = line.strip()
        low = stripped.lower()
        if low.startswith("episode number:"):
            num_match = re.search(r"(\d+)", stripped)
            if num_match:
                ep_number = int(num_match.group(1))
        elif low.startswith("episode logline:"):
            logline = stripped.split(":", 1)[1].strip()
        elif low.startswith("continuity notes:"):
            continuity = stripped.split(":", 1)[1].strip()

    # Fallback to filename if ep_number not parsed
    if ep_number == 0:
        fname_match = re.search(r"episode-?(\d+)", os.path.basename(filepath), re.IGNORECASE)
        if fname_match:
            ep_number = int(fname_match.group(1))

    episode = Episode(
        episode_number=ep_number,
        logline=clean_text(logline),
        continuity_notes=clean_text(continuity),
        source_file=os.path.basename(filepath),
    )

    # --- Scene splitting ---
    scene_starts: List[Tuple[int, int]] = []  # (line_index, scene_number)
    for idx, line in enumerate(lines):
        stripped = line.strip()
        m = re.match(r"^SCENE\s+(\d+)\s*$", stripped, re.IGNORECASE)
        if m:
            scene_starts.append((idx, int(m.group(1))))

    for si, (start_idx, scene_num) in enumerate(scene_starts):
        end_idx = scene_starts[si + 1][0] if si + 1 < len(scene_starts) else len(lines)
        scene_lines = lines[start_idx:end_idx]
        scene = _parse_scene_block(
            scene_lines=scene_lines,
            scene_num=scene_num,
            ep_number=ep_number,
            file_line_offset=start_idx + 1,
        )
        if scene:
            episode.scenes.append(scene)

    return episode


def _parse_scene_block(
    scene_lines: List[str],
    scene_num: int,
    ep_number: int,
    file_line_offset: int,
) -> Optional[Scene]:
    """Parse lines belonging to one scene into a Scene object."""
    heading = ""
    scene_start = 0.0
    scene_end = 0.0

    # Extract scene header metadata (case-insensitive & label-normalized)
    for line in scene_lines[:15]:
        stripped = line.strip()
        if ":" not in stripped:
            continue
        key, val = stripped.split(":", 1)
        norm_key = normalize_label(key)

        if norm_key == "scene heading":
            heading = clean_text(val)
        elif norm_key == "scene start":
            try:
                scene_start = normalize_timestamp(val)
            except ValueError:
                pass
        elif norm_key == "scene end":
            try:
                scene_end = normalize_timestamp(val)
            except ValueError:
                pass

    scene = Scene(
        scene_id=scene_num,
        heading=heading,
        start=scene_start,
        end=scene_end,
    )

    event_counter = 1
    i = 0
    while i < len(scene_lines):
        line = scene_lines[i].strip()
        header_match = re.match(r"^\*\*(.+?):\*\*$", line)

        if header_match:
            header_text = f"**{header_match.group(1)}:**"
            # Look for timestamp line (immediately following or with minimal whitespace)
            se = None
            ts_line_idx = i + 1
            if ts_line_idx < len(scene_lines):
                se = extract_start_end(scene_lines[ts_line_idx])

            if se:
                evt_start, evt_end = se
                text_parts = []
                j = ts_line_idx + 1

                while j < len(scene_lines):
                    sl = scene_lines[j].strip()
                    if sl == "" or re.match(r"^\*\*.+:\*\*$", sl) or re.match(r"^SCENE\s+\d+", sl, re.IGNORECASE):
                        break
                    # Strip surrounding quotes from dialogue/action
                    cleaned_line = sl.strip('"').strip("'")
                    text_parts.append(cleaned_line)
                    j += 1

                raw_header = header_match.group(1).strip()
                etype = _classify_event_type(raw_header)
                char_name, tone = _extract_character_and_tone(header_text)

                event_id = generate_event_id(ep_number, scene_num, event_counter)
                event_counter += 1

                event_text = clean_text(" ".join(text_parts)) if text_parts else clean_text(raw_header)
                line_number = file_line_offset + i

                event = ScreenplayEvent(
                    event_id=event_id,
                    scene_id=scene_num,
                    event_type=etype,
                    character=char_name,
                    tone=tone,
                    text=event_text,
                    start=evt_start,
                    end=evt_end,
                    source_line=line_number,
                )
                scene.events.append(event)
                i = j
                continue
        i += 1

    return scene


def load_all_episodes(folder: str) -> List[Episode]:
    """Load and parse all episode .txt files from folder, sorted by episode number."""
    episodes: List[Episode] = []
    for fname in sorted(os.listdir(folder)):
        if fname.endswith(".txt"):
            fpath = os.path.join(folder, fname)
            ep = parse_episode(fpath)
            episodes.append(ep)
    episodes.sort(key=lambda e: e.episode_number)
    return episodes
