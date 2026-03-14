"""Парсер вакансий Ozon."""

from enrichment.grade_guesser import guess_grade_from_title
from parsers.base import BaseParser
from parsers.utils import normalize_city
import config


class OzonParser(BaseParser):
    async def parse(self, session, existing_ids, city_mappings):
        url = "https://job-api.ozon.ru/v2/vacancy?professionalRoles=73&meta.limit=100"
        async with session.get(url, headers=config.REQUEST_HEADERS) as response:
            response.raise_for_status()
            payload = await response.json()

        vacancies = []
        for item in payload.get("items", []):
            if item.get("vacancyType") != "external_vacancy":
                continue
            title = (item.get("title", "") or "").strip()
            work_format = ", ".join(item.get("workFormat", [])) or "Не указан"
            vacancies.append(
                {
                    "id": f"ozon_{item.get('hhId')}",
                    "company": "Ozon",
                    "title": title,
                    "grade": guess_grade_from_title(title),
                    "city": normalize_city(city_mappings, item.get("city")),
                    "work_format": work_format,
                    "experience": item.get("experience") or "Не указан",
                    "url": f"https://career.ozon.ru/vacancy/{item.get('hhId')}",
                    "short_description": None,
                    "source_json": {**item, "department": item.get("department")},
                }
            )
        return vacancies
