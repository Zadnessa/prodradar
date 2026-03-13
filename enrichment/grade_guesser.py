"""Определение грейда по заголовку вакансии."""

import re


def guess_grade_from_title(title):
    """Возвращает грейд только при точном вхождении ключевых слов."""
    if not title:
        return None

    text = title.lower()
    patterns = {
        r"\bjunior\b": "Junior",
        r"\bintern\b": "Junior",
        r"\bmiddle\b": "Middle",
        r"\bsenior\b": "Senior",
        r"\blead\b": "Lead",
        r"\bстажер\b": "Junior",
        r"\bстажёр\b": "Junior",
    }

    for pattern, grade in patterns.items():
        if re.search(pattern, text):
            return grade
    return None
