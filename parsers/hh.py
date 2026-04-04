"""Парсер вакансий HeadHunter."""

import asyncio
import logging

from bs4 import BeautifulSoup

from parsers.base import BaseParser
from parsers.utils import normalize_city


logger = logging.getLogger(__name__)


class HHParser(BaseParser):
    LIST_URL = "https://api.hh.ru/vacancies"
    DETAIL_URL = "https://api.hh.ru/vacancies/{raw_id}"
    HEADERS = {
        "HH-User-Agent": "VacancyBot/1.0 (mois.pave@gmail.com)",
    }

    async def parse(self, session, existing_ids, city_mappings):
        del existing_ids

        vacancies = []
        page = 0

        while True:
            params = {
                "employer_id": 1455,
                "page": page,
                "per_page": 100,
            }
            async with session.get(self.LIST_URL, params=params, headers=self.HEADERS) as response:
                response.raise_for_status()
                payload = await response.json()

            items = payload.get("items") or []
            for item in items:
                work_formats = item.get("work_format") or []
                work_format = ", ".join(
                    fmt.get("name", "").strip() for fmt in work_formats if (fmt.get("name") or "").strip()
                )

                vacancies.append(
                    {
                        "id": f"hh_{item.get('id')}",
                        "company": "HeadHunter",
                        "title": (item.get("name") or "").strip(),
                        "grade": None,
                        "city": normalize_city(city_mappings, ((item.get("area") or {}).get("name"))),
                        "work_format": work_format or "Не указан",
                        "experience": ((item.get("experience") or {}).get("name")) or "не указан",
                        "published_at": item.get("published_at"),
                        "description": None,
                        "url": item.get("alternate_url"),
                    }
                )

            page += 1
            if page >= (payload.get("pages") or 0):
                break
            await asyncio.sleep(0.3)

        return vacancies

    async def enrich(self, session, vacancy):
        should_sleep = False
        try:
            vacancy_id = vacancy.get("id") or ""
            raw_id = vacancy_id.removeprefix("hh_")
            if not raw_id:
                return vacancy

            should_sleep = True
            async with session.get(self.DETAIL_URL.format(raw_id=raw_id), headers=self.HEADERS) as response:
                response.raise_for_status()
                payload = await response.json()

            description_html = (payload.get("description") or "").strip()
            if not description_html:
                return vacancy

            description_text = BeautifulSoup(description_html, "html.parser").get_text("\n", strip=True)
            current_description = vacancy.get("description") or ""
            if description_text and len(description_text) > len(current_description):
                vacancy["description"] = description_text
        except Exception as exc:
            logger.warning("Ошибка enrichment HeadHunter для %s: %s", vacancy.get("id"), exc)
        finally:
            if should_sleep:
                await asyncio.sleep(0.5)

        return vacancy
