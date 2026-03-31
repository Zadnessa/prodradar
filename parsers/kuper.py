"""Парсер вакансий Купера."""

import logging
import re

import config
from parsers.base import BaseParser


class KuperParser(BaseParser):
    """Парсер вакансий Купера (SberMarket)."""

    LIST_URL = "https://vacancies-api.sbermarket.ru/api/vacancy_pagination/"
    DETAIL_URL_TEMPLATE = "https://vacancies-api.sbermarket.ru/api/vacancy/{friendly_url}"
    GROUP_ID = "186247de-f72e-469e-9da3-db468f9b6197"

    def __init__(self):
        self._friendly_urls = {}

    @staticmethod
    def _extract_category_data(payload, category_name):
        result = payload.get("result") or []
        for item in result:
            if item.get("category") == category_name:
                return item.get("data")
        return None

    @staticmethod
    def _normalize_grade(raw_grades):
        if not raw_grades:
            return None

        grade_values = []
        for raw_grade in raw_grades:
            value = (raw_grade or "").strip().title()
            if not value:
                continue
            if value in {"Team Lead", "Unit Lead", "Engineering Manager"}:
                value = "Lead+"
            grade_values.append(value)

        if not grade_values:
            return None
        if len(grade_values) == 1:
            return grade_values[0]
        return "-".join(grade_values)

    @staticmethod
    def _strip_tags(text):
        if not text:
            return ""
        cleaned = re.sub(r"<[^>]+>", " ", text)
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip()

    async def parse(self, session, existing_ids, city_mappings):
        del existing_ids, city_mappings
        vacancies = []
        self._friendly_urls = {}

        page = 1
        total_pages = 1

        while page <= total_pages:
            params = {"page": page, "group": self.GROUP_ID}
            async with session.get(self.LIST_URL, headers=config.REQUEST_HEADERS, params=params) as response:
                response.raise_for_status()
                payload = await response.json()

            vacancy_items = self._extract_category_data(payload, "vacancies") or []
            pagination = self._extract_category_data(payload, "pagination") or {}
            total_pages = int(pagination.get("pages") or total_pages)

            for item in vacancy_items:
                vacancy_id = str(item.get("id"))
                friendly_url = item.get("friendlyUrl")
                if not vacancy_id or not friendly_url:
                    continue

                work_format_values = [str(value).strip() for value in (item.get("wf") or []) if str(value).strip()]
                experience_years = item.get("workExperience")
                self._friendly_urls[vacancy_id] = friendly_url

                vacancies.append(
                    {
                        "id": vacancy_id,
                        "company": "Купер",
                        "title": (item.get("title") or "").strip(),
                        "grade": self._normalize_grade(item.get("grade") or []),
                        "city": item.get("city") or "Не указан",
                        "work_format": ", ".join(work_format_values) if work_format_values else "Не указан",
                        "experience": f"от {experience_years} лет" if experience_years is not None else "не указан",
                        "published_at": None,
                        "url": f"https://team.kuper.ru/vacancies/{friendly_url}",
                        "description": "",
                    }
                )

            page += 1

        return vacancies

    async def enrich(self, session, vacancy):
        vacancy_id = vacancy.get("id")
        friendly_url = self._friendly_urls.get(vacancy_id)
        if not friendly_url:
            return vacancy

        detail_url = self.DETAIL_URL_TEMPLATE.format(friendly_url=friendly_url)
        async with session.get(detail_url, headers=config.REQUEST_HEADERS) as response:
            if response.status != 200:
                logging.warning(
                    "Kuper detail вернул %s для %s",
                    response.status,
                    vacancy.get("id"),
                )
                return vacancy
            payload = await response.json()

        description_parts = []
        for field_name in ("descriptionVacancy", "responsibilities", "requirements", "terms"):
            field_payload = payload.get(field_name) or {}
            value = field_payload.get("value")
            if value:
                description_parts.append(value)

        if not description_parts:
            return vacancy

        new_description = self._strip_tags("\n\n".join(description_parts))
        current_description = vacancy.get("description") or ""
        if new_description and (not current_description or len(new_description) > len(current_description)):
            vacancy["description"] = new_description

        return vacancy
