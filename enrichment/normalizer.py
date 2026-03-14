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
    "от 1 до 3 лет": "1-3 года",
    "от 1 года": "1-3 года",
    "от 1 года и более": "1-3 года",
    "1-3 лет": "1-3 года",
    "от 1 года до 3 лет": "1-3 года",
    "1–3 года": "1-3 года",
    "от 3 до 5 лет": "3-5 лет",
    "от 3 до 6 лет": "3-5 лет",
    "от 3 лет": "3-5 лет",
    "от 3+ лет": "3-5 лет",
    "3+ лет": "3-5 лет",
    "от 3 лет и более": "3-5 лет",
    "3-5 лет": "3-5 лет",
    "3-6 лет": "3-5 лет",
    "от 3 лет до 5 лет": "3-5 лет",
    "3–5 лет": "3-5 лет",
    "3–6 лет": "3-5 лет",
    "от 5 лет": "5+ лет",
    "от 5 лет и более": "5+ лет",
    "от 6 лет": "5+ лет",
    "от 6 лет и более": "5+ лет",
    "5+ лет": "5+ лет",
    "6+ лет": "5+ лет",
    "6+": "5+ лет",
    "более 5 лет": "5+ лет",
    "более 6 лет": "5+ лет",
}

_GRADE_FROM_EXPERIENCE = {
    "без опыта": "Junior",
    "до 1 года": "Junior",
    "1-3 года": "Middle",
    "3-5 лет": "Middle+",
    "5+ лет": "Senior",
}


def normalize_experience(raw_experience):
    """Приводит опыт к единому формату."""
    if raw_experience is None:
        return "не указан"

    value = str(raw_experience).strip().lower()
    if not value or value == "не указан":
        return "не указан"

    mapped = _EXPERIENCE_MAP.get(value)
    if mapped:
        return mapped

    numbers = [float(num.replace(",", ".")) for num in re.findall(r"\d+(?:[.,]\d+)?", value)]
    if not numbers:
        return value

    baseline = numbers[-1] if len(numbers) >= 2 else numbers[0]
    if baseline < 1:
        return "до 1 года"
    if baseline < 3:
        return "1-3 года"
    if baseline < 5:
        return "3-5 лет"
    return "5+ лет"


def grade_from_experience(normalized_experience):
    """Возвращает грейд на основе нормализованного опыта."""
    if not normalized_experience:
        return None
    if normalized_experience == "не указан":
        return None
    return _GRADE_FROM_EXPERIENCE.get(normalized_experience)
