"""GSM-7 and UCS-2 segment counting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

GSM7_BASIC = (
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
GSM7_EXTENSION = frozenset("^{}\\[~]|€")

GSM7_SINGLE_LIMIT = 160
GSM7_MULTI_LIMIT = 153
UCS2_SINGLE_LIMIT = 70
UCS2_MULTI_LIMIT = 67


@dataclass(frozen=True, slots=True)
class SegmentInfo:
    charset: Literal["GSM-7", "UCS-2"]
    units: int
    segments: int
    single_part_limit: int
    multi_part_limit: int


def _is_gsm7(text: str) -> bool:
    return all(character in GSM7_BASIC or character in GSM7_EXTENSION for character in text)


def count_segments(text: str) -> SegmentInfo:
    """Count SMS segments for a message, including joined multipart limits."""

    if not text:
        return SegmentInfo("GSM-7", 0, 0, GSM7_SINGLE_LIMIT, GSM7_MULTI_LIMIT)

    if _is_gsm7(text):
        units = sum(2 if character in GSM7_EXTENSION else 1 for character in text)
        if units <= GSM7_SINGLE_LIMIT:
            return SegmentInfo("GSM-7", units, 1, GSM7_SINGLE_LIMIT, GSM7_MULTI_LIMIT)
        segments = (units + GSM7_MULTI_LIMIT - 1) // GSM7_MULTI_LIMIT
        return SegmentInfo("GSM-7", units, segments, GSM7_SINGLE_LIMIT, GSM7_MULTI_LIMIT)

    units = len(text.encode("utf-16-be")) // 2
    if units <= UCS2_SINGLE_LIMIT:
        return SegmentInfo("UCS-2", units, 1, UCS2_SINGLE_LIMIT, UCS2_MULTI_LIMIT)
    segments = (units + UCS2_MULTI_LIMIT - 1) // UCS2_MULTI_LIMIT
    return SegmentInfo("UCS-2", units, segments, UCS2_SINGLE_LIMIT, UCS2_MULTI_LIMIT)
