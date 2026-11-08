from __future__ import annotations

import pytest

from tunza.messaging.segments import count_segments


@pytest.mark.parametrize(
    ("text", "charset", "units", "segments"),
    [
        ("", "GSM-7", 0, 0),
        ("hello", "GSM-7", 5, 1),
        ("a" * 160, "GSM-7", 160, 1),
        ("a" * 161, "GSM-7", 161, 2),
        ("€", "GSM-7", 2, 1),
        ("a" * 159 + "€", "GSM-7", 161, 2),
        ("你", "UCS-2", 1, 1),
        ("你" * 70, "UCS-2", 70, 1),
        ("你" * 71, "UCS-2", 71, 2),
        ("你" * 134, "UCS-2", 134, 2),
        ("你" * 135, "UCS-2", 135, 3),
        ("😀", "UCS-2", 2, 1),
    ],
)
def test_count_segments(text: str, charset: str, units: int, segments: int) -> None:
    result = count_segments(text)
    assert result.charset == charset
    assert result.units == units
    assert result.segments == segments


def test_joined_message_limits_are_exposed() -> None:
    gsm = count_segments("hello")
    assert gsm.single_part_limit == 160
    assert gsm.multi_part_limit == 153

    ucs2 = count_segments("你好")
    assert ucs2.single_part_limit == 70
    assert ucs2.multi_part_limit == 67


def test_luganda_text_with_special_characters_switches_to_ucs2() -> None:
    result = count_segments("Tukusanyukidde — mumbeere nga bulungi")
    assert result.charset == "UCS-2"
