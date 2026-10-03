"""Парсер вакансий Dodo."""

import asyncio
import logging
import re

from bs4 import BeautifulSoup

import config
from parsers.base import BaseParser
from parsers.utils import normalize_city

logger = logging.getLogger(__name__)


class DodoParser(BaseParser):
    def __init__(self):
        self._api_url = None

    async def parse(self, session, existing_ids, city_mappings):
        del existing_ids
        # Адрес backend берём из публичной Nuxt-конфигурации, как фронтенд сайта.
        async with session.get("https://dodoteam.ru/vacancies", headers=config.REQUEST_HEADERS) as response:
            response.raise_for_status()
            html = await response.text()
        match = re.search(r'apiURL\s*:\s*["\'](https://[^"\']+)["\']', html)
        if not match:
            raise ValueError("Dodo: apiURL не найден в публичной конфигурации")
        self._api_url = match.group(1).rstrip('/')
        url = self._api_url + "/api/v1/vacancies"
        async with session.get(url, headers=config.REQUEST_HEADERS) as response:
            response.raise_for_status()
            payload = await response.json()

        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise ValueError("Dodo: неожиданный формат списка вакансий")

        vacancies = []
        for group in payload.get("data", []):
            for item in group.get("items", []):
                subspeciality = (item.get("subspeciality") or "").lower()
                if "product" not in subspeciality:
                    continue

                vacancy_id = item.get("id")
                work_format_items = item.get("work_format") or []
                work_format = ", ".join(work_format_items) if work_format_items else "Не указан"

                vacancy = {
                    "id": f"dodo_{vacancy_id}",
                    "company": "Dodo",
                    "title": (item.get("position") or "").strip(),
                    "grade": None,
                    "city": normalize_city(city_mappings, item.get("vacancy_location") or ""),
                    "work_format": work_format,
                    "experience": "Не указан",
                    "url": f"https://dodoteam.ru/vacancy?vacancyId={vacancy_id}",
                    "published_at": None,
                    "description": None,
                    "source_json": item,
                }
                vacancies.append(vacancy)

        return vacancies

    async def enrich(self, session, vacancy):
        raw_id = str(vacancy.get("id", "")).removeprefix("dodo_")
        if not raw_id:
            return vacancy

        if not self._api_url:
            raise ValueError("Dodo: сначала должен быть выполнен parse()")
        url = f"{self._api_url}/api/v1/pages/vacancy/{raw_id}"
        try:
            async with session.get(url, headers=config.REQUEST_HEADERS) as response:
                response.raise_for_status()
                payload = await response.json()

            content = payload.get("data", {}).get("page", {}).get("content", [])

            if not vacancy.get("grade"):
                for block in content:
                    if block.get("type") == "vacancy_main":
                        grade = (block.get("data") or {}).get("grade")
                        if grade:
                            vacancy["grade"] = grade
                        break

            text_block_types = {
                "vacancy_text",
                "vacancy_expectation",
                "vacancy_you_will",
                "vacancy_benefits",
            }
            parts = []
            for block in content:
                if block.get("type") not in text_block_types:
                    continue
                html_text = (block.get("data") or {}).get("text")
                if not html_text:
                    continue
                text = BeautifulSoup(html_text, "html.parser").get_text("\n", strip=True)
                if text:
                    parts.append(text)

            if parts:
                new_description = "\n\n".join(parts)
                current_description = vacancy.get("description") or ""
                if len(new_description) > len(current_description):
                    vacancy["description"] = new_description

            return vacancy
        except Exception as exc:
            logger.warning("Ошибка enrichment Dodo для %s: %s", vacancy.get("id"), exc)
            return vacancy
        finally:
            await asyncio.sleep(0.3)
