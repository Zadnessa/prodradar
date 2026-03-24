"""Парсер вакансий Yandex."""

import asyncio
import logging

from parsers.base import BaseParser
import config


class YandexParser(BaseParser):
    URL = "https://yandex.ru/jobs/api/publications?public_professions=product-manager&page_size=100"

    async def parse(self, session, existing_ids, city_mappings):
        del existing_ids
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
                    "company": "Яндекс",
                    "title": title,
                    "grade": None,
                    "city": cities,
                    "work_format": work_modes,
                    "experience": "не указан",
                    "url": f"https://yandex.ru/jobs/vacancies/{item.get('publication_slug_url')}",
                    "description": item.get("short_summary") or None,
                    "source_json": {
                        **item,
                        "public_service_name": (item.get("public_service") or {}).get("name"),
                    },
                }
            )

        return vacancies

    async def enrich(self, session, vacancy):
        should_sleep = False
        try:
            raw_id = (vacancy.get("id") or "").replace("ya_", "", 1)
            if not raw_id.isdigit():
                return vacancy

            details_url = f"https://yandex.ru/jobs/api/publications/{raw_id}"
            should_sleep = True
            async with session.get(details_url, headers=config.REQUEST_HEADERS) as response:
                response.raise_for_status()
                payload = await response.json()

            vacancy_details = payload.get("vacancy") or {}

            if not vacancy.get("grade"):
                grade_map = {
                    "intern": "Junior",
                    "junior": "Junior",
                    "middle": "Middle",
                    "senior": "Senior",
                }
                min_level = (vacancy_details.get("pro_level_min_display") or "").split(".")[-1].strip().lower()
                max_level = (vacancy_details.get("pro_level_max_display") or "").split(".")[-1].strip().lower()
                min_grade = grade_map.get(min_level)
                max_grade = grade_map.get(max_level)

                if min_grade:
                    if not max_grade or min_grade == max_grade:
                        vacancy["grade"] = min_grade
                    else:
                        vacancy["grade"] = f"{min_grade}-{max_grade}"

            current_description = vacancy.get("description") or ""
            parts = [
                payload.get("short_summary"),
                payload.get("duties"),
                payload.get("key_qualifications"),
                payload.get("additional_requirements"),
                payload.get("conditions"),
            ]
            description = "\n\n".join((part or "").strip() for part in parts if (part or "").strip())
            if description and len(description) > len(current_description):
                vacancy["description"] = description

            published_at = payload.get("published_at")
            if not vacancy.get("published_at") and published_at:
                vacancy["published_at"] = published_at
        except Exception as exc:
            logging.warning("Yandex enrich ошибка для %s: %s", vacancy.get("id"), exc)
        finally:
            if should_sleep:
                await asyncio.sleep(0.3)

        return vacancy
