"""Базовый парсер вакансий HeadHunter API."""

import asyncio
import logging
import random

from bs4 import BeautifulSoup

from config import HH_ACCESS_TOKEN, HH_USER_AGENT
from parsers.base import BaseParser
from parsers.utils import normalize_city


logger = logging.getLogger(__name__)


class HHBaseParser(BaseParser):
    LIST_URL = "https://api.hh.ru/vacancies"
    DETAIL_URL = "https://api.hh.ru/vacancies/{raw_id}"
    EMPLOYER_ID = None
    COMPANY_NAME = None
    VACANCY_ID_PREFIX = None

    def __init__(self):
        self.captcha_hit = False

    def _build_headers(self):
        headers = {"HH-User-Agent": HH_USER_AGENT}
        if HH_ACCESS_TOKEN:
            headers["Authorization"] = f"Bearer {HH_ACCESS_TOKEN}"
        return headers

    async def _read_error_payload(self, response):
        error_type = "unknown"
        request_id = "unknown"
        captcha_url = None

        try:
            payload = await response.json(content_type=None)
            errors = payload.get("errors") or []
            if errors and isinstance(errors[0], dict):
                error_type = errors[0].get("type") or "unknown"
                captcha_url = errors[0].get("captcha_url")
            request_id = payload.get("request_id") or "unknown"
        except Exception:
            pass

        return error_type, request_id, captcha_url

    async def parse(self, session, existing_ids, city_mappings, browser_secrets=None):
        del existing_ids, browser_secrets

        vacancies = []
        page = 0

        while True:
            params = {
                "employer_id": self.EMPLOYER_ID,
                "page": page,
                "per_page": 100,
            }
            payload = None

            for attempt in (1, 2):
                async with session.get(self.LIST_URL, params=params, headers=self._build_headers()) as response:
                    if response.status in (403, 429):
                        error_type, request_id, captcha_url = await self._read_error_payload(response)
                        logger.warning(
                            "HH API %s: type=%s, request_id=%s, url=%s",
                            response.status,
                            error_type,
                            request_id,
                            str(response.url),
                        )
                        if any(kw in error_type for kw in ("oauth", "token", "unauthorized")):
                            logger.error("HH OAuth ошибка: %s — проверьте HH_ACCESS_TOKEN", error_type)
                            return vacancies
                        if error_type == "captcha_required":
                            if captcha_url:
                                logger.warning("HH captcha_url: %s", captcha_url)
                            self.captcha_hit = True
                            return vacancies
                        if attempt == 1:
                            await asyncio.sleep(30)
                            continue
                        return vacancies

                    response.raise_for_status()
                    payload = await response.json()
                    break

            if payload is None:
                return vacancies

            items = payload.get("items") or []
            for item in items:
                work_formats = item.get("work_format") or []
                work_format = ", ".join(
                    fmt.get("name", "").strip() for fmt in work_formats if (fmt.get("name") or "").strip()
                )

                vacancies.append(
                    {
                        "id": f"{self.VACANCY_ID_PREFIX}{item.get('id')}",
                        "company": self.COMPANY_NAME,
                        "title": (item.get("name") or "").strip(),
                        "grade": None,
                        "city": normalize_city(city_mappings, ((item.get("area") or {}).get("name"))),
                        "work_format": work_format or "Не указан",
                        "experience": ((item.get("experience") or {}).get("name")) or "не указан",
                        "published_at": item.get("published_at"),
                        "description": None,
                        "url": item.get("alternate_url"),
                    }
                )

            page += 1
            if page >= (payload.get("pages") or 0):
                break
            await asyncio.sleep(random.uniform(1.0, 2.0))

        return vacancies

    async def enrich(self, session, vacancy):
        should_sleep = False
        try:
            vacancy_id = vacancy.get("id") or ""
            raw_id = vacancy_id.removeprefix(self.VACANCY_ID_PREFIX)
            if not raw_id:
                return vacancy

            should_sleep = True
            async with session.get(self.DETAIL_URL.format(raw_id=raw_id), headers=self._build_headers()) as response:
                if response.status in (403, 429):
                    error_type, request_id, _ = await self._read_error_payload(response)
                    logger.warning(
                        "HH API %s: type=%s, request_id=%s, url=%s",
                        response.status,
                        error_type,
                        request_id,
                        str(response.url),
                    )
                    return vacancy

                response.raise_for_status()
                payload = await response.json()

            description_html = (payload.get("description") or "").strip()
            if not description_html:
                return vacancy

            description_text = BeautifulSoup(description_html, "html.parser").get_text("\n", strip=True)
            current_description = vacancy.get("description") or ""
            if description_text and len(description_text) > len(current_description):
                vacancy["description"] = description_text
        except Exception as exc:
            logger.warning("Ошибка enrichment %s для %s: %s", self.COMPANY_NAME, vacancy.get("id"), exc)
        finally:
            if should_sleep:
                await asyncio.sleep(random.uniform(0.3, 0.8))

        return vacancy
