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


def normalize_work_format(raw_value):
    """Приводит формат работы к стандартным значениям."""
    if raw_value is None:
        return "Не указан"

    value = str(raw_value).strip()
    if not value or value.lower() == "не указан":
        return "Не указан"

    normalized_parts = []
    for raw_part in value.lower().split(","):
        part = raw_part.strip()
        if not part:
            continue

        labels_with_positions = []

        def _first_position(keywords):
            positions = [part.find(keyword) for keyword in keywords if keyword in part]
            return min(positions) if positions else None

        office_position = _first_position(("офис", "на месте", "office"))
        remote_position = _first_position(("удал", "remote"))
        hybrid_position = _first_position(("гибр", "гибк", "комбин", "hybrid"))

        if office_position is not None:
            labels_with_positions.append((office_position, "Офис"))
        if remote_position is not None:
            labels_with_positions.append((remote_position, "Удалёнка"))
        if hybrid_position is not None:
            labels_with_positions.append((hybrid_position, "Гибрид"))

        for _, label in sorted(labels_with_positions, key=lambda item: item[0]):
            if label not in normalized_parts:
                normalized_parts.append(label)

    if not normalized_parts:
        return "Не указан"
    return ", ".join(normalized_parts)


def normalize_grade(raw_value):
    """Приводит грейд к стандартному формату."""
    if raw_value is None:
        return None

    value = str(raw_value).strip()
    if not value:
        return None

    normalized_parts = []
    for raw_part in value.split(","):
        part = raw_part.strip()
        if not part:
            continue

        normalized = part.title()
        if normalized in {"Lead", "Head", "Cpo"}:
            normalized = "Lead+"

        if normalized not in normalized_parts:
            normalized_parts.append(normalized)

    if not normalized_parts:
        return None
    if len(normalized_parts) == 1:
        return normalized_parts[0]
    return "-".join(normalized_parts)
