"""Парсер вакансий Yandex."""

from enrichment.grade_guesser import guess_grade_from_title
from parsers.base import BaseParser
import config


class YandexParser(BaseParser):
    async def parse(self, session, existing_ids, city_mappings):
        url = "https://yandex.ru/jobs/api/publications?public_professions=product-manager&page_size=100"
        async with session.get(url, headers=config.REQUEST_HEADERS) as response:
            response.raise_for_status()
            payload = await response.json()

        vacancies = []
        for item in payload.get("results", []):
            vacancy = item.get("vacancy", {})
            cities = ", ".join(c.get("name", "") for c in vacancy.get("cities", []) if c.get("name")) or "Не указан"
            work_modes = ", ".join(m.get("name", "") for m in vacancy.get("work_modes", []) if m.get("name")) or "Не указан"
            title = (item.get("title", "") or "").strip()
            grade = guess_grade_from_title(title)
            experience_map = {"Junior": "1-3 лет", "Middle": "3-5 лет", "Senior": "5+ лет", "Lead": "5+ лет"}
            vacancies.append(
                {
                    "id": f"ya_{item.get('id')}",
                    "company": "Yandex",
                    "title": title,
                    "grade": grade,
                    "city": cities,
                    "work_format": work_modes,
                    "experience": experience_map.get(grade, "Не указан"),
                    "url": f"https://yandex.ru/jobs/vacancies/{item.get('publication_slug_url')}",
                    "short_description": item.get("short_summary") or None,
                    "source_json": {
                        **item,
                        "public_service_name": (item.get("public_service") or {}).get("name"),
                    },
                }
            )
        return vacancies
