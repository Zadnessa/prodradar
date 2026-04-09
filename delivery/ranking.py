"""Утилиты ранжирования вакансий."""

import re

from config import TITLE_EXACT_WHITELIST, TITLE_GREY_PATTERNS, TITLE_PREFILTER_REJECT, TITLE_REGEX_PATTERNS


def classify_title(title: str) -> str | None:
    t = title.strip().lower()
    for pattern in TITLE_PREFILTER_REJECT:
        if pattern in t:
            return None
    for pattern in TITLE_EXACT_WHITELIST:
        if pattern in t:
            return "exact"
    for pattern in TITLE_REGEX_PATTERNS:
        if re.search(pattern, t):
            return "regex"
    for pattern, is_regex in TITLE_GREY_PATTERNS:
        if is_regex:
            if re.search(pattern, t):
                return "grey"
        elif pattern in t:
            return "grey"
    return None


def title_confidence(title: str) -> int:
    zone = classify_title(title)
    confidence_map = {
        "exact": 3,
        "regex": 2,
        "grey": 1,
    }
    return confidence_map.get(zone, 0)
