"""Парсер вакансий Yandex."""

from parsers.base import BaseParser
import config


class YandexParser(BaseParser):
    URL = "https://yandex.ru/jobs/api/publications?public_professions=product-manager&page_size=100"

    async def parse(self, session, existing_ids, city_mappings):
        async with session.get(self.URL, headers=config.REQUEST_HEADERS) as response:
            response.raise_for_status()
            payload = await response.json()

        vacancies = []
        for item in payload.get("results", []):
            vacancy = item.get("vacancy", {})
            vacancy_cities = vacancy.get("cities") or item.get("cities") or []
            cities = ", ".join(c.get("name", "") for c in vacancy_cities if c.get("name")) or "Не указан"
            work_modes = ", ".join(m.get("name", "") for m in vacancy.get("work_modes", []) if m.get("name")) or "Не указан"
            title = (item.get("title", "") or "").strip()

            vacancies.append(
                {
                    "id": f"ya_{item.get('id')}",
                    "company": "Yandex",
                    "title": title,
                    "grade": None,
                    "city": cities,
                    "work_format": work_modes,
                    "experience": "не указан",
                    "url": f"https://yandex.ru/jobs/vacancies/{item.get('publication_slug_url')}",
                    "short_description": item.get("short_summary") or None,
                    "source_json": {
                        **item,
                        "public_service_name": (item.get("public_service") or {}).get("name"),
                    },
                }
            )

        return vacancies
