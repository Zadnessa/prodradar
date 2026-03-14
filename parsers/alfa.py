"""Парсер вакансий Alfa-Bank."""

from parsers.base import BaseParser
import config


class AlfaParser(BaseParser):
    async def parse(self, session, existing_ids, city_mappings):
        url = "https://job.alfabank.ru/api/vacancies?businessLine=1020&take=100&search=продукт"
        async with session.get(url, headers=config.REQUEST_HEADERS) as response:
            response.raise_for_status()
            payload = await response.json()

        vacancies = []
        for item in payload.get("items", []):
            slug = item.get("slug") or ""
            parts = [p for p in slug.split("/") if p]
            raw_city = parts[0] if parts else ""
            city = city_mappings.get(("alfa_slug", raw_city), raw_city.replace("-", " ").title() if raw_city else "Не указан")
            title = (item.get("name", "") or "").strip()
            description = (item.get("descriptionText") or "").strip()
            vacancies.append(
                {
                    "id": f"alfa_{item.get('id')}",
                    "company": "Alfa-Bank",
                    "title": title,
                    "grade": None,
                    "city": city,
                    "work_format": "Не указан",
                    "experience": config.ALFA_EXPERIENCE_MAP.get(item.get("experienceId"), "Не указан"),
                    "url": f"https://job.alfabank.ru/vacancies/{item.get('id')}",
                    "short_description": description[:500] if description else None,
                    "source_json": item,
                }
            )
        return vacancies
