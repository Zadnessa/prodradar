"""Утилиты ранжирования вакансий."""

import re

from config import TITLE_EXACT_WHITELIST, TITLE_GREY_PATTERNS, TITLE_PREFILTER_REJECT, TITLE_REGEX_PATTERNS

_GRADE_MAP = {
    "junior": 0,
    "middle": 1,
    "middle+": 2,
    "middle-senior": 2,
    "senior": 3,
    "lead+": 4,
}


def _normalize_grade_value(grade: str | None) -> int | None:
    if not grade:
        return None
    normalized = grade.strip().lower()
    if "-" in normalized:
        normalized = normalized.split("-", 1)[0].strip()
    return _GRADE_MAP.get(normalized)


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


def grade_score(vacancy_grade: str | None, user_grades: list[str] | None) -> int:
    if not user_grades:
        return 0

    vacancy_value = _normalize_grade_value(vacancy_grade)
    if vacancy_value is None:
        return 0

    user_values = [value for value in (_normalize_grade_value(grade) for grade in user_grades) if value is not None]
    if not user_values:
        return 0

    distance = min(abs(vacancy_value - user_value) for user_value in user_values)
    return max(4 - distance, 0)


def rank_vacancies(vacancies: list[dict], user_grades: list[str] | None, title_boost_fn=None) -> list[dict]:
    boost = title_boost_fn or (lambda _title: 0)

    def _sort_key(vacancy: dict):
        title = vacancy.get("title", "")
        return (
            boost(title),
            title_confidence(title),
            grade_score(vacancy.get("grade"), user_grades),
            vacancy.get("published_at") or "",
        )

    return sorted(vacancies, key=_sort_key, reverse=True)
