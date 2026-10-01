"""Парсер вакансий МТС Линк."""

import re
import os

from parsers.base import BaseParser


class MtsLinkParser(BaseParser):
    """Парсер продуктовых вакансий МТС Линк."""

    LIST_URL = "https://mts-link.ru/api/huntflow/vacancies"
    DETAIL_URL_TEMPLATE = "https://mts-link.ru/api/huntflow/vacancy/{raw_id}"
    LIST_PARAMS = {"categoryId": 221722}
    REQUEST_HEADERS = {
        "Origin": "https://job.mts-link.ru",
        "Referer": "https://job.mts-link.ru/",
        "Accept": "*/*",
    }

    def __init__(self):
        self._raw_ids = {}

    def _build_headers(self):
        token = os.getenv("MTSLINK_BEARER_TOKEN")
        if not token:
            raise ValueError("МТС Линк: MTSLINK_BEARER_TOKEN не задан")
        return {**self.REQUEST_HEADERS, "Authorization": f"Bearer {token}"}

    @staticmethod
    def _build_published_at(created):
        if not isinstance(created, dict):
            return None

        raw_date = created.get("date")
        raw_timezone = created.get("timezone")
        if not raw_date or not raw_timezone:
            return None

        date_base = str(raw_date).split(".", maxsplit=1)[0].strip()
        if " " not in date_base:
            return None

        return f"{date_base.replace(' ', 'T', 1)}{raw_timezone}"

    @staticmethod
    def _strip_html(value):
        return re.sub(r"<[^>]+>", "", str(value or "")).strip()

    async def parse(self, session, existing_ids, city_mappings):
        del existing_ids, city_mappings
        self._raw_ids = {}

        async with session.get(
            self.LIST_URL,
            params=self.LIST_PARAMS,
            headers=self._build_headers(),
        ) as response:
            response.raise_for_status()
            items = await response.json()

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
        raw_id = self._raw_ids.get(vacancy_id)
        if not raw_id:
            return vacancy

        detail_url = self.DETAIL_URL_TEMPLATE.format(raw_id=raw_id)
        async with session.get(detail_url, headers=self._build_headers()) as response:
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
