"""Парсер вакансий СберЗдоровье."""

import asyncio
import logging
import re

import config
from parsers.base import BaseParser


logger = logging.getLogger(__name__)


class SberHealthParser(BaseParser):
    """Парсер продуктовых вакансий СберЗдоровья."""

    LIST_URL_TEMPLATE = "https://vacancy.sberhealth.ru/_next/data/{build_id}/index.json"
    DETAIL_URL_TEMPLATE = "https://vacancy.sberhealth.ru/_next/data/{build_id}/vacancies/{raw_id}.json"

    def __init__(self):
        self._build_id = None

    @staticmethod
    def _strip_html(value):
        text = re.sub(r"<[^>]+>", " ", str(value or ""))
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @staticmethod
    def _extract_experience(requirements):
        match = re.search(r"(?:от|более)\s*(\d+)\s*(?:лет|года|год|г)", requirements or "", flags=re.IGNORECASE)
        if not match:
            return None

        years = int(match.group(1))
        if years <= 1:
            return "до 1 года"
        if years in (2, 3):
            return "1-3 года"
        if years in (4, 5):
            return "3-5 лет"
        return "5+ лет"

    @staticmethod
    def _extract_work_format(conditions):
        value = (conditions or "").lower()
        if "гибрид" in value:
            return "Гибрид"
        if "удалённ" in value or "удален" in value:
            return "Удалёнка"
        if "офис" in value:
            return "Офис"
        return None

    async def parse(self, session, existing_ids, city_mappings, browser_secrets=None):
        del existing_ids, city_mappings

        build_id = None
        if browser_secrets:
            build_id = browser_secrets.get("sberhealth_build_id")

        if not build_id:
            raise RuntimeError("СберЗдоровье: buildId не получен из браузерного этапа")

        self._build_id = build_id
        logger.info("СберЗдоровье parse: buildId=%s", build_id)

        headers = {**config.REQUEST_HEADERS, "Accept": "application/json"}
        list_url = self.LIST_URL_TEMPLATE.format(build_id=build_id)
        async with session.get(list_url, headers=headers) as response:
            response.raise_for_status()
            payload = await response.json()

        items = payload.get("pageProps", {}).get("vacancies", [])
        logger.info("СберЗдоровье parse: список получен, status=%s, вакансий=%s", response.status, len(items))
        vacancies = []

        for item in items:
            raw_id = item.get("id")
            if raw_id is None:
                continue

            published_at = (item.get("createdAt") or "")[:10] or None
            vacancies.append(
                {
                    "id": f"sberhealth_{raw_id}",
                    "company": "СберЗдоровье",
                    "title": (item.get("position") or "").strip(),
                    "grade": None,
                    "city": item.get("locationName"),
                    "work_format": None,
                    "url": f"https://vacancy.sberhealth.ru/vacancies/{raw_id}",
                    "description": None,
                    "experience": None,
                    "published_at": published_at,
                }
            )

        return vacancies

    async def enrich(self, session, vacancy):
        raw_id = str(vacancy.get("id") or "").removeprefix("sberhealth_")
        if not self._build_id or not raw_id:
            return vacancy

        headers = {**config.REQUEST_HEADERS, "Accept": "application/json"}
        detail_url = self.DETAIL_URL_TEMPLATE.format(build_id=self._build_id, raw_id=raw_id)

        try:
            async with session.get(detail_url, headers=headers) as response:
                response.raise_for_status()
                payload = await response.json()

            detail = payload.get("pageProps", {}).get("vacancy", {})
            team_description = self._strip_html(detail.get("teamDescription"))
            body = self._strip_html(detail.get("body"))
            requirements = self._strip_html(detail.get("requirements"))
            conditions = self._strip_html(detail.get("conditions"))

            new_description = "\n\n".join(
                part for part in (team_description, body, requirements, conditions) if part
            ).strip()
            new_experience = self._extract_experience(requirements)
            new_work_format = self._extract_work_format(conditions)

            current_description = vacancy.get("description") or ""
            if new_description and (not current_description or len(new_description) > len(current_description)):
                vacancy["description"] = new_description

            if not (vacancy.get("experience") or "").strip() and new_experience:
                vacancy["experience"] = new_experience

            if not (vacancy.get("work_format") or "").strip() and new_work_format:
                vacancy["work_format"] = new_work_format
        except Exception as exc:
            logger.warning("СберЗдоровье enrichment %s: %s", vacancy.get("id"), exc)
        finally:
            await asyncio.sleep(0.3)

        return vacancy
