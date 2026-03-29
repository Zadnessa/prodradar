"""Парсер вакансий Lamoda."""

import asyncio
import logging
import re

from bs4 import BeautifulSoup

import config
from parsers.base import BaseParser
from parsers.utils import normalize_city

logger = logging.getLogger(__name__)


class LamodaParser(BaseParser):
    async def parse(self, session, existing_ids, city_mappings):
        del existing_ids

        base_url = "https://job.lamoda.ru/api/hr/vacancies/compact"
        start = 0
        limit = 100
        vacancies = []

        while True:
            params = {
                "dir[0]": "upravlenie-proektami-i-produktami",
                "pagination[start]": start,
                "pagination[limit]": limit,
            }

            async with session.get(base_url, headers=config.REQUEST_HEADERS, params=params) as response:
                response.raise_for_status()
                payload = await response.json()

            items = payload.get("data") or []
            if not items:
                break

            for item in items:
                raw_id = item.get("id")
                slug = item.get("slug") or ""
                title = (item.get("name") or "").strip()
                city_raw = (item.get("location") or {}).get("name") or "Не указан"

                vacancies.append(
                    {
                        "id": f"lamoda_{raw_id}",
                        "company": "Lamoda",
                        "title": title,
                        "grade": None,
                        "city": normalize_city(city_mappings, city_raw),
                        "work_format": None,
                        "url": f"https://job.lamoda.ru/vacancies/{slug}",
                        "description": None,
                        "experience": None,
                        "published_at": item.get("externalPublicationDate"),
                        "_raw_id": raw_id,
                    }
                )

            meta = payload.get("meta") or {}
            total = int(meta.get("total", 0) or 0)
            current_start = int(meta.get("start", start) or start)
            current_limit = int(meta.get("limit", limit) or limit)

            if current_start + current_limit >= total:
                break

            start = current_start + current_limit

        return vacancies

    async def enrich(self, session, vacancy):
        raw_id = vacancy.get("_raw_id")
        if raw_id is None:
            vacancy.pop("_raw_id", None)
            return vacancy

        details_url = f"https://job.lamoda.ru/api/hr/vacancies/{raw_id}"
        try:
            async with session.get(details_url, headers=config.REQUEST_HEADERS) as response:
                response.raise_for_status()
                payload = await response.json()

            attributes = (payload.get("data") or {}).get("attributes") or {}
            parts = []
            for field in ("duties", "requirements", "conditions"):
                html_value = attributes.get(field)
                if not html_value:
                    continue

                text = BeautifulSoup(html_value, "html.parser").get_text(separator="\n", strip=True)
                if text:
                    parts.append(text)

            if parts:
                new_description = "\n\n".join(parts)
                new_description = re.sub(r"\n{3,}", "\n\n", new_description).strip()
                current_description = vacancy.get("description") or ""
                if (not current_description) or (len(new_description) > len(current_description)):
                    vacancy["description"] = new_description

            return vacancy
        except Exception as exc:
            logger.warning("Ошибка enrichment Lamoda для %s: %s", vacancy.get("id"), exc)
            return vacancy
        finally:
            vacancy.pop("_raw_id", None)
            await asyncio.sleep(0.3)
