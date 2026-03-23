"""Парсер вакансий Ozon."""

import asyncio
import logging

from bs4 import BeautifulSoup

from parsers.base import BaseParser
from parsers.utils import normalize_city
import config


class OzonParser(BaseParser):
    @staticmethod
    def _normalize_work_format_values(values):
        normalized_values = []
        for value in values or []:
            if isinstance(value, str):
                normalized_values.append(value.replace("\xa0", " "))
            else:
                normalized_values.append(value)
        return normalized_values

    async def parse(self, session, existing_ids, city_mappings):
        base_url = "https://job-api.ozon.ru/v2/vacancy"
        page = 1
        vacancies = []

        while True:
            params = {
                "professionalRoles": 73,
                "meta.limit": 50,
                "meta.page": page,
            }
            async with session.get(base_url, headers=config.REQUEST_HEADERS, params=params) as response:
                response.raise_for_status()
                payload = await response.json()

            for item in payload.get("items", []):
                if item.get("vacancyType") != "external_vacancy":
                    continue
                title = (item.get("title", "") or "").strip()
                work_format_values = self._normalize_work_format_values(item.get("workFormat", []))
                work_format = ", ".join(work_format_values) or "Не указан"
                vacancies.append(
                    {
                        "id": f"ozon_{item.get('hhId')}",
                        "company": "Ozon",
                        "title": title,
                        "grade": None,
                        "city": normalize_city(city_mappings, item.get("city")),
                        "work_format": work_format,
                        "experience": item.get("experience") or "Не указан",
                        "url": f"https://career.ozon.ru/vacancy/{item.get('hhId')}",
                        "short_description": None,
                        "source_json": {**item, "department": item.get("department")},
                    }
                )

            meta = payload.get("meta") or {}
            current_page = int(meta.get("page", page) or page)
            total_pages = int(meta.get("totalPages", current_page) or current_page)
            if current_page >= total_pages:
                break
            page = current_page + 1

        return vacancies

    async def enrich(self, session, vacancy):
        should_sleep = False
        try:
            raw_id = (vacancy.get("id") or "").replace("ozon_", "", 1)
            if not raw_id.isdigit():
                return vacancy

            details_url = f"https://job-api.ozon.ru/vacancy/{raw_id}"
            should_sleep = True
            async with session.get(details_url, headers=config.REQUEST_HEADERS) as response:
                response.raise_for_status()
                payload = await response.json()

            if not vacancy.get("short_description"):
                descr_html = payload.get("descr") or ""
                description = BeautifulSoup(descr_html, "html.parser").get_text(" ", strip=True)
                if description:
                    vacancy["short_description"] = description[:500]

            experience = (vacancy.get("experience") or "").strip().lower()
            if experience in {"", "не указан"} and payload.get("exp"):
                vacancy["experience"] = payload.get("exp")

            if not vacancy.get("work_format") and payload.get("workFormat"):
                vacancy["work_format"] = ", ".join(self._normalize_work_format_values(payload.get("workFormat", [])))

            if not vacancy.get("published_at") and payload.get("publishedAt"):
                vacancy["published_at"] = payload.get("publishedAt")

            if payload.get("slug"):
                vacancy["url"] = f"https://career.ozon.ru/vacancy/{payload.get('slug')}/"
        except Exception as exc:
            logging.warning("Ozon enrich ошибка для %s: %s", vacancy.get("id"), exc)
        finally:
            if should_sleep:
                await asyncio.sleep(0.3)

        return vacancy
