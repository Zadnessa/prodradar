"""Парсер вакансий Wildberries."""

from parsers.base import BaseParser
from parsers.utils import normalize_city
import config


class WildberriesParser(BaseParser):
    async def parse(self, session, existing_ids, city_mappings):
        headers = dict(config.REQUEST_HEADERS)
        headers["Referer"] = "https://career.rwb.ru/vacancies"
        url = "https://career.rwb.ru/crm-api/api/v1/pub/vacancies?limit=200&offset=0&direction_ids[]=9"

        async with session.get(url, headers=headers) as response:
            response.raise_for_status()
            payload = await response.json()

        vacancies = []
        for item in payload.get("data", {}).get("items", []):
            vacancy_id = f"wb_{item.get('id')}"
            employment_types = item.get("employment_types") or []
            work_format = ", ".join(t.get("title", "") for t in employment_types if t.get("title")) or "Не указан"
            title = (item.get("name", "") or "").strip()

            vacancies.append(
                {
                    "id": vacancy_id,
                    "company": "Wildberries",
                    "title": title,
                    "grade": None,
                    "city": normalize_city(city_mappings, item.get("city_title")),
                    "work_format": work_format,
                    "experience": item.get("experience_type_title") or "Не указан",
                    "url": f"https://career.rwb.ru/vacancies/{item.get('id')}",
                    "short_description": None,
                    "source_json": item,
                }
            )
        return vacancies
