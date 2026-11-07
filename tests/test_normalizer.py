"""Tests for Timestamp, Label, and Text Normalizer."""

import pytest
from promo_finder.normalizer import (
    normalize_timestamp,
    format_timestamp,
    normalize_label,
    generate_event_id,
    clean_text,
    extract_start_end,
)


def test_normalize_timestamp_standard():
    assert normalize_timestamp("00:11.30") == 11.30
    assert normalize_timestamp("(00:11.30)") == 11.30
    assert normalize_timestamp("01:05.60") == 65.60
    assert normalize_timestamp("02:18.00") == 138.00


def test_normalize_timestamp_variations():
    assert normalize_timestamp("1:05.6") == 65.60
    assert normalize_timestamp("45.50") == 45.50
    assert normalize_timestamp("30") == 30.00
    assert normalize_timestamp("[00:05.20]") == 5.20


def test_normalize_timestamp_errors():
    with pytest.raises(ValueError):
        normalize_timestamp("")
    with pytest.raises(ValueError):
        normalize_timestamp("invalid_time")


def test_format_timestamp():
    assert format_timestamp(11.30) == "00:11.30"
    assert format_timestamp(65.60) == "01:05.60"
    assert format_timestamp(0.0) == "00:00.00"
    assert format_timestamp(138.00) == "02:18.00"


def test_format_timestamp_rollover():
    # 59.996s should roll over to 01:00.00 instead of 00:60.00
    assert format_timestamp(59.996) == "01:00.00"
    # 12.996s should roll over to 00:13.00 instead of 00:12.100
    assert format_timestamp(12.996) == "00:13.00"
    # 119.998s should roll over to 02:00.00
    assert format_timestamp(119.998) == "02:00.00"


def test_normalize_label():
    assert normalize_label("**SCENE HEADING:**") == "scene heading"
    assert normalize_label("Scene heading:") == "scene heading"
    assert normalize_label("SCENE START:") == "scene start"
    assert normalize_label("Scene end:") == "scene end"
    assert normalize_label("ACTIONS AND DIALOGUE:") == "actions and dialogue"


def test_generate_event_id():
    assert generate_event_id(1, 1, 4) == "EP01_SC01_EV004"
    assert generate_event_id(6, 2, 15) == "EP06_SC02_EV015"
    assert generate_event_id(41, 3, 102) == "EP41_SC03_EV102"


def test_clean_text():
    raw = '  “You should turn around, Juliana.”  '
    cleaned = clean_text(raw)
    assert cleaned == '"You should turn around, Juliana."'


def test_extract_start_end():
    line = "Start: (00:11.30) | End: (01:05.60)"
    se = extract_start_end(line)
    assert se == (11.30, 65.60)

    line2 = "Start: 00:01.00 | End: 00:04.80"
    se2 = extract_start_end(line2)
    assert se2 == (1.00, 4.80)

    assert extract_start_end("Random dialogue line") is None
