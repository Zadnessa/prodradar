"""Парсер вакансий Ozon."""

import asyncio
import logging

from bs4 import BeautifulSoup

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
                    "grade": None,
                    "city": normalize_city(city_mappings, item.get("city")),
                    "work_format": work_format,
                    "experience": item.get("experience") or "Не указан",
                    "url": f"https://career.ozon.ru/vacancy/{item.get('hhId')}",
                    "short_description": None,
                    "source_json": {**item, "department": item.get("department")},
                }
            )
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
                vacancy["work_format"] = ", ".join(payload.get("workFormat"))
        except Exception as exc:
            logging.warning("Ozon enrich ошибка для %s: %s", vacancy.get("id"), exc)
        finally:
            if should_sleep:
                await asyncio.sleep(0.3)

        return vacancy
