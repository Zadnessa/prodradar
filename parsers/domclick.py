"""Парсер вакансий ДомКлик."""

import logging
import re
from urllib.parse import quote, urlsplit

from bs4 import BeautifulSoup

import config
from parsers.base import BaseParser

logger = logging.getLogger(__name__)


class DomClickParser(BaseParser):
    LIST_URL = "https://career.domclick.ru/api/v1/vacancy/"
    DETAIL_URL = "https://career.domclick.ru/api/v1/vacancy/detail/{slug}/"
    WORK_FORMAT_MAP = {"ON_SITE": "Офис", "REMOTE": "Удалёнка", "HYBRID": "Гибрид"}

    def __init__(self):
        self._slugs = {}

    @staticmethod
    def _headers():
        return {
            **config.REQUEST_HEADERS,
            "Referer": "https://career.domclick.ru/vacancies",
            "Accept": "application/json",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
        }

    async def parse(self, session, existing_ids, city_mappings):
        del existing_ids, city_mappings
        self._slugs = {}
        vacancies = []
        offset, limit = 0, 100
        seen_ids = set()
        while True:
            async with session.get(self.LIST_URL, headers=self._headers(),
                                   params={"limit": limit, "offset": offset}) as response:
                response.raise_for_status()
                payload = await response.json()
            if not isinstance(payload, dict) or payload.get("success") is not True or not isinstance(payload.get("result"), list):
                raise ValueError("ДомКлик: неожиданный формат списка вакансий")
            items = payload["result"]
            for item in items:
                if item.get("id") is None or not item.get("slug") or not item.get("title"):
                    raise ValueError("ДомКлик: отсутствуют обязательные поля вакансии")
                vacancy_id = str(item["id"])
                if vacancy_id in seen_ids:
                    raise ValueError("ДомКлик: повторяющиеся id в пагинации")
                seen_ids.add(vacancy_id)
                self._slugs[vacancy_id] = item["slug"]
                work_formats = (item.get("vacancycontent") or {}).get("work_format") or []
                vacancies.append({
                    "id": vacancy_id,
                    "company": "ДомКлик",
                    "title": item["title"].strip(),
                    "grade": None,
                    "city": (item.get("area") or {}).get("name") or "Не указан",
                    "work_format": ", ".join(self.WORK_FORMAT_MAP.get(value, value) for value in work_formats)
                        or (item.get("schedule") or {}).get("name") or "Не указан",
                    "url": f"https://career.domclick.ru/vacancy/{quote(item['slug'], safe='')}",
                    "description": None,
                    "experience": (item.get("experience") or {}).get("name") or "не указан",
                    "published_at": None,
                    "source_json": item,
                })
            pagination = payload.get("pagination") or {}
            total = pagination.get("total")
            page_limit = pagination.get("limit") or limit
            if not isinstance(page_limit, int) or page_limit <= 0:
                raise ValueError("ДомКлик: неверный limit в пагинации")
            if total is not None and len(vacancies) >= total:
                if len(vacancies) != total:
                    raise ValueError("ДомКлик: число вакансий не совпадает с total")
                break
            if len(items) < page_limit:
                if total is not None and len(vacancies) != total:
                    raise ValueError("ДомКлик: неполная пагинация")
                break
            offset += len(items)

        return vacancies

    async def enrich(self, session, vacancy):
        slug = self._slugs.get(vacancy.get("id")) or urlsplit(vacancy.get("url") or "").path.rstrip('/').rsplit('/', 1)[-1]
        if not slug:
            return vacancy
        url = self.DETAIL_URL.format(slug=quote(slug, safe=''))

        try:
            async with session.get(url, headers=self._headers()) as response:
                response.raise_for_status()
                payload = await response.json()

            if payload.get("success") is not True or not isinstance(payload.get("result"), dict):
                raise ValueError("ДомКлик: неожиданный формат detail")
            description_html = (((payload["result"].get("vacancycontent") or {}).get("description")) or "").strip()
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
