"""Парсер вакансий Sber."""

import re

from parsers.base import BaseParser
from parsers.utils import normalize_city
import config


_MD_PATTERNS = [
    (r"```.*?```", " "),
    (r"`([^`]*)`", r"\1"),
    (r"!\[[^\]]*\]\([^)]*\)", " "),
    (r"\[([^\]]+)\]\([^)]*\)", r"\1"),
    (r"[*_~>#-]", " "),
]


def _clean_markdown(text):
    cleaned = text or ""
    for pattern, repl in _MD_PATTERNS:
        cleaned = re.sub(pattern, repl, cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


class SberParser(BaseParser):
    async def parse(self, session, existing_ids, city_mappings):
        url = (
            "https://rabota.sber.ru/public/app-candidate-public-api-gateway/api/v1/publications"
            "?skip=0&take=200&profAreas=56555ea9-92d9-4d66-b4bf-ba74a850dbdb"
        )
        async with session.get(url, headers=config.REQUEST_HEADERS) as response:
            response.raise_for_status()
            payload = await response.json()

        keywords = ("product", "продакт", "продукт", "cpo")
        vacancies = []
        for item in payload.get("data", {}).get("vacancies", []):
            title = (item.get("title", "") or "").strip()
            if not any(keyword in title.lower() for keyword in keywords):
                continue

            duties_clean = _clean_markdown(item.get("duties") or "")
            short_description = duties_clean[:500] if duties_clean else None

            vacancies.append(
                {
                    "id": f"sber_{item.get('internalId')}",
                    "company": "Сбер",
                    "title": title,
                    "grade": None,
                    "city": normalize_city(city_mappings, item.get("city")),
                    "work_format": "Не указан",
                    "experience": config.SBER_EXPERIENCE_MAP.get(item.get("experienceId"), "Не указан"),
                    "url": f"https://rabota.sber.ru/search/{item.get('internalId')}",
                    "short_description": short_description,
                    "source_json": {
                        **item,
                        "introduction": item.get("introduction"),
                        "duties": item.get("duties"),
                        "requirements": item.get("requirements"),
                        "conditions": item.get("conditions"),
                    },
                }
            )
        return vacancies
