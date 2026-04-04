"""Парсер вакансий экосистемы МТС."""

import re
from datetime import date, timedelta

import config
from parsers.base import BaseParser


class MtsParser(BaseParser):
    """Парсер вакансий МТС/МТС Банк/MWS.AI/KION/Юрент."""

    CAREER_URL = "https://job.mts.ru/"
    LIST_URL = "https://api.job.mts.ru/v1/vacancies/filtered/career"
    DETAIL_URL_TEMPLATE = "https://api.job.mts.ru/v1/vacancy/{raw_id}"
    API_KEY_PATTERN = re.compile(
        r"""apiKey\s*[:=]\s*["'](eyJhbG[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)["']"""
    )
    PM_CATEGORY = "Управление продуктами/проектами/процессами"
    STRICT_WHITELIST = (
        "product manager",
        "product owner",
        "продакт",
        "продукт менеджер",
        "менеджер продукта",
        "менеджер по продукту",
        "менеджер продуктов",
        "владелец продукта",
        "cpo",
    )
    BRAND_MAP = {
        "ПАО МТС-Банк": "МТС Банк",
        "ООО МТС Веб Сервисы": "MWS.AI",
        "АО МТС Веб Сервисы": "MWS.AI",
        'ООО "КИОН"': "KION",
        "ООО ШЕРИНГОВЫЕ ТЕХНОЛОГИИ": "Юрент",
    }
    RUS_MONTHS = {
        "января": 1,
        "февраля": 2,
        "марта": 3,
        "апреля": 4,
        "мая": 5,
        "июня": 6,
        "июля": 7,
        "августа": 8,
        "сентября": 9,
        "октября": 10,
        "ноября": 11,
        "декабря": 12,
    }

    def __init__(self):
        self.api_key = None

    async def _fetch_api_key(self, session):
        async with session.get(self.CAREER_URL, headers=config.REQUEST_HEADERS) as response:
            response.raise_for_status()
            html = await response.text()

        match = self.API_KEY_PATTERN.search(html)
        if not match:
            raise RuntimeError("MTS: не удалось получить x-api-key из HTML job.mts.ru")
        return match.group(1)

    @classmethod
    def _parse_russian_date(cls, raw_date):
        if not raw_date:
            return None

        try:
            cleaned = re.sub(r"\s+", " ", str(raw_date).strip().lower())
            parts = cleaned.split(" ")
            if len(parts) not in {2, 3}:
                return None

            day = int(parts[0])
            month = cls.RUS_MONTHS.get(parts[1])
            if not month:
                return None

            today = date.today()
            year = int(parts[2]) if len(parts) == 3 else today.year
            parsed_date = date(year, month, day)

            if len(parts) == 2 and parsed_date > today + timedelta(days=7):
                parsed_date = date(year - 1, month, day)

            return parsed_date.isoformat()
        except Exception:
            return None

    @classmethod
    def _resolve_company(cls, brand):
        return cls.BRAND_MAP.get((brand or "").strip(), "МТС")

    @classmethod
    def _is_relevant_vacancy(cls, item):
        info = item.get("info") or {}
        category = (info.get("category") or "").strip()
        if category == cls.PM_CATEGORY:
            return True

        title_lower = (item.get("name") or "").strip().lower()
        return any(pattern in title_lower for pattern in cls.STRICT_WHITELIST)

    async def parse(self, session, existing_ids, city_mappings):
        del existing_ids, city_mappings
        self.api_key = await self._fetch_api_key(session)

        headers = {
            **config.REQUEST_HEADERS,
            "x-api-key": self.api_key,
        }
        limit = 200
        offset = 0
        total = None
        vacancies = []

        while total is None or offset < total:
            payload = {
                "filters": {},
                "offset": offset,
                "limit": limit,
            }
            async with session.post(self.LIST_URL, headers=headers, json=payload) as response:
                response.raise_for_status()
                data = await response.json()

            data_payload = data.get("data") or {}
            page_info = data_payload.get("pageInfo") or {}
            page_total = page_info.get("total")
            if isinstance(page_total, int):
                total = page_total
            elif total is None:
                total = 0

            page_items = data_payload.get("vacancies") or []
            for item in page_items:
                if not self._is_relevant_vacancy(item):
                    continue

                info = item.get("info") or {}
                raw_id = item.get("id")
                if raw_id is None:
                    continue
                raw_id_str = str(raw_id)

                vacancies.append(
                    {
                        "id": f"mts_{raw_id_str}",
                        "company": self._resolve_company(info.get("brand")),
                        "title": (item.get("name") or "").strip(),
                        "grade": None,
                        "city": (info.get("city") or "").strip() or "Не указан",
                        "work_format": info.get("worktype"),
                        "experience": info.get("experience"),
                        "published_at": self._parse_russian_date(info.get("date")),
                        "description": None,
                        "url": f"https://job.mts.ru/vacancy/{raw_id_str}",
                    }
                )

            offset += limit
            if offset >= total:
                break

        return vacancies

    async def enrich(self, session, vacancy):
        if not self.api_key:
            self.api_key = await self._fetch_api_key(session)

        raw_id = str(vacancy.get("id", "")).removeprefix("mts_")
        if not raw_id:
            return vacancy

        headers = {
            **config.REQUEST_HEADERS,
            "x-api-key": self.api_key,
        }
        detail_url = self.DETAIL_URL_TEMPLATE.format(raw_id=raw_id)

        async with session.get(detail_url, headers=headers) as response:
            response.raise_for_status()
            payload = await response.json()

        detail_text = (((payload.get("data") or {}).get("vacancy") or {}).get("detailText") or {})
        blocks = []
        for key in ("descriptionOfProject", "description", "requirements", "conditions"):
            value = (detail_text.get(key) or "").strip()
            if value:
                blocks.append(value)

        if blocks:
            vacancy["description"] = "\n\n".join(blocks)

        return vacancy
