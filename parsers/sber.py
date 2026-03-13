"""Парсер вакансий Sber."""

from parsers.base import BaseParser
from parsers.utils import normalize_city
import config


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
            title = item.get("title", "")
            if not any(keyword in title.lower() for keyword in keywords):
                continue
            vacancies.append(
                {
                    "id": f"sber_{item.get('internalId')}",
                    "company": "Sber",
                    "title": title,
                    "grade": None,
                    "city": normalize_city(city_mappings, item.get("city")),
                    "work_format": "Не указан",
                    "experience": config.SBER_EXPERIENCE_MAP.get(item.get("experienceId"), "Не указан"),
                    "url": f"https://rabota.sber.ru/search/{item.get('internalId')}",
                    "short_description": None,
                    "source_json": item,
                }
            )
        return vacancies
