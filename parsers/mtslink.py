"""Парсер вакансий МТС Линк."""

import re
from datetime import datetime
from zoneinfo import ZoneInfo

from parsers.base import BaseParser


class MtsLinkParser(BaseParser):
    """Парсер продуктовых вакансий МТС Линк."""

    LIST_URL = "https://mts-link.ru/api/huntflow/vacancies"
    DETAIL_URL_TEMPLATE = "https://mts-link.ru/api/huntflow/vacancy/{raw_id}"
    REQUEST_HEADERS = {
        "Origin": "https://job.mts-link.ru",
        "Referer": "https://job.mts-link.ru/",
        "Accept": "*/*",
    }

    def __init__(self):
        self._raw_ids = {}

    @staticmethod
    def _build_published_at(created):
        if not isinstance(created, dict):
            return None

        raw_date = created.get("date")
        raw_timezone = created.get("timezone")
        if not raw_date or not raw_timezone:
            return None

        value = datetime.fromisoformat(str(raw_date))
        if value.tzinfo is None:
            if raw_timezone.startswith(("+", "-")):
                value = datetime.fromisoformat(value.isoformat() + raw_timezone)
            else:
                value = value.replace(tzinfo=ZoneInfo(raw_timezone))
        return value.isoformat()

    @staticmethod
    def _strip_html(value):
        return re.sub(r"<[^>]+>", "", str(value or "")).strip()

    async def parse(self, session, existing_ids, city_mappings):
        del existing_ids, city_mappings
        self._raw_ids = {}

        async with session.get(
            self.LIST_URL,
            headers=self.REQUEST_HEADERS,
        ) as response:
            response.raise_for_status()
            items = await response.json()

        # Публичный endpoint сайта не требует Bearer. Старый categoryId может
        # молча вернуть [], поэтому роли отбираются общим фильтром pipeline.
        if not isinstance(items, list):
            raise ValueError("МТС Линк: неожиданный формат списка вакансий")

        vacancies = []
        for item in items or []:
            if item.get("hidden"):
                continue

            raw_id = item.get("id")
            if raw_id is None:
                continue

            vacancy_id = f"mtslink_{raw_id}"
            self._raw_ids[vacancy_id] = str(raw_id)

            vacancies.append(
                {
                    "id": vacancy_id,
                    "company": "МТС Линк",
                    "title": (item.get("position") or "").strip(),
                    "grade": None,
                    "city": None,
                    "work_format": item.get("workFormat"),
                    "experience": item.get("workExperience"),
                    "published_at": self._build_published_at(item.get("created")),
                    "description": "",
                    "url": f"https://job.mts-link.ru/vacancy/?id={raw_id}",
                }
            )

        return vacancies

    async def enrich(self, session, vacancy):
        vacancy_id = vacancy.get("id")
        raw_id = self._raw_ids.get(vacancy_id) or str(vacancy_id or "").removeprefix("mtslink_")
        if not raw_id:
            return vacancy

        detail_url = self.DETAIL_URL_TEMPLATE.format(raw_id=raw_id)
        async with session.get(detail_url, headers=self.REQUEST_HEADERS) as response:
            response.raise_for_status()
            detail = await response.json()

        parts = []
        for key in ("body", "requirements", "conditions"):
            clean_part = self._strip_html(detail.get(key))
            if clean_part:
                parts.append(clean_part)

        new_description = "\n\n".join(parts).strip()
        current_description = vacancy.get("description") or ""
        if new_description and (not current_description or len(new_description) > len(current_description)):
            vacancy["description"] = new_description

        return vacancy
