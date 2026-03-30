"""Парсер вакансий ДомКлик."""

import logging
import re

from bs4 import BeautifulSoup

import config
from parsers.base import BaseParser

logger = logging.getLogger(__name__)


class DomClickParser(BaseParser):
    async def parse(self, session, existing_ids, city_mappings):
        del existing_ids, city_mappings

        url = "https://rabota-bff.domclick.ru/api/v1/vacancies"
        headers = {
            **config.REQUEST_HEADERS,
            "Referer": "https://career.domclick.ru/",
        }

        async with session.get(url, headers=headers) as response:
            if response.status == 404:
                return []
            response.raise_for_status()
            payload = await response.json()

        vacancies = []
        for item in payload.get("data") or []:
            area_name = (item.get("area") or {}).get("name") or "Не указан"
            schedule_name = (item.get("schedule") or {}).get("name") or "Не указан"
            experience_name = (item.get("experience") or {}).get("name") or "не указан"

            vacancies.append(
                {
                    "id": str(item.get("id")),
                    "company": "ДомКлик",
                    "title": (item.get("name") or "").strip(),
                    "grade": None,
                    "city": area_name,
                    "work_format": schedule_name,
                    "url": f"https://career.domclick.ru/vacancy/{item.get('slug') or ''}",
                    "description": None,
                    "experience": experience_name,
                    "published_at": None,
                }
            )

        return vacancies

    async def enrich(self, session, vacancy):
        vacancy_id = vacancy.get("id")
        if not vacancy_id:
            return vacancy

        url = f"https://rabota-bff.domclick.ru/api/v1/vacancies/{vacancy_id}"
        headers = {
            **config.REQUEST_HEADERS,
            "Referer": "https://career.domclick.ru/",
        }

        try:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                payload = await response.json()

            description_html = ((payload.get("data") or {}).get("description") or "").strip()
            if not description_html:
                return vacancy

            description_text = BeautifulSoup(description_html, "html.parser").get_text("\n", strip=True)
            description_text = re.sub(r"(?:\s*#[\wа-яА-ЯёЁ-]+)+\s*$", "", description_text).strip()
            if not description_text:
                return vacancy

            current_description = vacancy.get("description") or ""
            if len(description_text) > len(current_description):
                vacancy["description"] = description_text
            return vacancy
        except Exception as exc:
            logger.warning("Ошибка enrichment ДомКлик для %s: %s", vacancy.get("id"), exc)
            return vacancy
