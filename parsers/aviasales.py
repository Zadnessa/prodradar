"""Парсер вакансий Авиасейлс."""

import json
import logging
import re

from bs4 import BeautifulSoup

import config
from parsers.base import BaseParser


class AviasalesParser(BaseParser):
    """Парсер вакансий Aviasales."""

    LIST_URL = "https://vacancies-app.aviasales.ru/api/vacancies?specializations=Product+managment&language=ru"
    DETAIL_URL_TEMPLATE = "https://aviasales.ru/about/vacancies/{raw_id}"
    KNOWN_KEYS = {"id", "position", "tags", "team", "workPlace"}
    ROUTER_DATA_RE = re.compile(r"window\._ROUTER_DATA\s*=\s*(\{.*?\})\s*(?:</script>|;)", re.DOTALL)

    @staticmethod
    def _strip_tags(html):
        if not html:
            return ""
        return BeautifulSoup(html, "html.parser").get_text(" ", strip=True).strip()

    @staticmethod
    def _extract_vacancy_payload(router_data):
        loader_data = router_data.get("loaderData") if isinstance(router_data, dict) else None
        if not isinstance(loader_data, dict):
            return None

        for _, value in loader_data.items():
            if isinstance(value, dict) and "vacancy" in value and isinstance(value.get("vacancy"), dict):
                return value.get("vacancy")
        return None

    async def parse(self, session, existing_ids, city_mappings):
        del existing_ids, city_mappings
        async with session.get(self.LIST_URL, headers=config.REQUEST_HEADERS) as response:
            response.raise_for_status()
            payload = await response.json()

        if not isinstance(payload, list):
            logging.warning("Aviasales: неожиданный формат ответа списка вакансий")
            return []

        workplace_count = sum(1 for item in payload if item.get("workPlace") is not None)
        if workplace_count > 0:
            logging.warning(
                "Aviasales: workPlace заполнен у %s вакансий, проверить маппинг work_format",
                workplace_count,
            )

        all_keys = set()
        for item in payload:
            if isinstance(item, dict):
                all_keys.update(item.keys())
        new_keys = sorted(all_keys - self.KNOWN_KEYS)
        if new_keys:
            logging.warning("Aviasales: обнаружены новые ключи в API: %s", new_keys)

        vacancies = []
        for item in payload:
            raw_id = item.get("id")
            if raw_id is None:
                continue

            vacancies.append(
                {
                    "id": f"aviasales_{raw_id}",
                    "title": (item.get("position") or "").strip(),
                    "company": "Авиасейлс",
                    "grade": None,
                    "city": None,
                    "work_format": "remote" if item.get("workPlace") is None else str(item.get("workPlace")),
                    "experience": None,
                    "published_at": None,
                    "description": None,
                    "url": self.DETAIL_URL_TEMPLATE.format(raw_id=raw_id),
                }
            )
        return vacancies

    async def enrich(self, session, vacancy):
        raw_id = (vacancy.get("id") or "").replace("aviasales_", "", 1)
        if not raw_id:
            return vacancy

        headers = dict(config.REQUEST_HEADERS)
        headers["Accept-Language"] = "ru"
        detail_url = self.DETAIL_URL_TEMPLATE.format(raw_id=raw_id)
        async with session.get(detail_url, headers=headers) as response:
            if response.status != 200:
                logging.warning("Aviasales enrich: HTTP %s для %s", response.status, vacancy.get("id"))
                return vacancy
            html = await response.text()

        match = self.ROUTER_DATA_RE.search(html)
        if not match:
            logging.warning("Aviasales enrich: не найден window._ROUTER_DATA для %s", vacancy.get("id"))
            return vacancy

        try:
            router_data = json.loads(match.group(1))
        except json.JSONDecodeError:
            logging.warning("Aviasales enrich: не удалось распарсить window._ROUTER_DATA для %s", vacancy.get("id"))
            return vacancy

        vacancy_payload = self._extract_vacancy_payload(router_data)
        if not vacancy_payload:
            logging.warning("Aviasales enrich: не найден объект vacancy в loaderData для %s", vacancy.get("id"))
            return vacancy

        parts = []
        for field in ("description", "todo", "requirements", "conditions"):
            cleaned = self._strip_tags(vacancy_payload.get(field))
            if cleaned:
                parts.append(cleaned)

        if not parts:
            return vacancy

        new_description = "\n\n".join(parts).strip()
        current_description = vacancy.get("description") or ""
        if new_description and (not current_description or len(new_description) > len(current_description)):
            vacancy["description"] = new_description

        return vacancy
