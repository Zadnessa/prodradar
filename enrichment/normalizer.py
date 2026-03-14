"""Нормализация опыта и определение грейда."""

import re


_EXPERIENCE_MAP = {
    "без опыта / стажер": "без опыта",
    "без опыта / стажёр": "без опыта",
    "без опыта": "без опыта",
    "стажер": "без опыта",
    "стажёр": "без опыта",
    "intern": "без опыта",
    "нет опыта": "без опыта",
    "до 1 года": "до 1 года",
    "менее 1 года": "до 1 года",
    "less than 1 year": "до 1 года",
    "от 1 до 3 лет": "1–3 года",
    "1-3 лет": "1–3 года",
    "от 1 года до 3 лет": "1–3 года",
    "1–3 года": "1–3 года",
    "от 3 до 5 лет": "3–5 лет",
    "от 3 до 6 лет": "3–5 лет",
    "3-5 лет": "3–5 лет",
    "3-6 лет": "3–5 лет",
    "от 3 лет до 5 лет": "3–5 лет",
    "3–5 лет": "3–5 лет",
    "3–6 лет": "3–5 лет",
    "от 5 лет": "5+ лет",
    "от 6 лет": "5+ лет",
    "5+ лет": "5+ лет",
    "6+": "5+ лет",
    "более 5 лет": "5+ лет",
}

_GRADE_FROM_EXPERIENCE = {
    "без опыта": "Junior",
    "до 1 года": "Junior",
    "1–3 года": "Middle",
    "3–5 лет": "Middle+",
    "5+ лет": "Senior",
}

_LEAD_PATTERNS = [
    r"\blead\b",
    r"\bhead\s+of\b",
    r"\bhead\b",
    r"\bруководитель\b",
    r"\bдиректор\b",
    r"\bcpo\b",
    r"\bchief\b",
]


def normalize_experience(raw_experience):
    """Приводит опыт к единому формату."""
    if raw_experience is None:
        return "не указан"

    value = str(raw_experience).strip().lower()
    if not value or value == "не указан":
        return "не указан"

    return _EXPERIENCE_MAP.get(value, value)


def grade_from_experience(normalized_experience):
    """Возвращает грейд на основе нормализованного опыта."""
    if not normalized_experience:
        return None
    if normalized_experience == "не указан":
        return None
    return _GRADE_FROM_EXPERIENCE.get(normalized_experience)


def grade_from_title(title):
    """Определяет только руководящие позиции из заголовка."""
    if not title:
        return None

    text = str(title).strip().lower()
    for pattern in _LEAD_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return "Lead+"
    return None
