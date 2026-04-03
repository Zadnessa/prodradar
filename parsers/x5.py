"""Парсер вакансий X5 Group."""

import config
from parsers.base import BaseParser


class X5Parser(BaseParser):
    """Парсер вакансий X5 Group с маппингом нескольких брендов."""

    LIST_URL = "https://rabota.x5.ru/public/api/vacancies/vacancies/"
    VACANCY_URL_TEMPLATE = "https://rabota.x5.ru/vacancies/{raw_id}"
    BRAND_MAP = {
        "X5 Tech": "X5 Tech",
        "Пятерочка": "Пятёрочка",
        "Перекресток": "Перекрёсток",
        "Чижик": "Чижик",
        "X5 Media": "X5 Media",
        "X5 Import": "X5 Импорт",
        "Много лосося": "Много лосося",
        "X5 Digital": "X5 Tech",
        "X5 Digital - партнер": "X5 Tech",
        "5POST": "X5 Tech",
        "X5 Transport": "X5 Tech",
        "X5 Поддержка бизнеса": "X5 Tech",
    }
    DEFAULT_COMPANY = "X5 Tech"

    @classmethod
    def _resolve_company(cls, business_units):
        if not business_units:
            return cls.DEFAULT_COMPANY

        first_unit = business_units[0] or {}
        title = (first_unit.get("title") or "").strip()
        return cls.BRAND_MAP.get(title, cls.DEFAULT_COMPANY)

    @staticmethod
    def _build_description(data):
        if not data:
            return None

        parts = []
        for key in ("main_responsibilities", "professional_skills"):
            value = (data.get(key) or "").strip()
            if value:
                parts.append(value)

        if not parts:
            return None
        return "\n\n".join(parts)

    async def parse(self, session, existing_ids, city_mappings):
        del existing_ids, city_mappings
        vacancies = []
        page = 1

        while True:
            params = {
                "vacancy_categories": 18858,
                "page": page,
                "page_size": 50,
            }
            async with session.get(self.LIST_URL, headers=config.REQUEST_HEADERS, params=params) as response:
                response.raise_for_status()
                payload = await response.json()

            items = payload.get("items") or []
            for item in items:
                raw_id = item.get("id")
                if raw_id is None:
                    continue

                raw_id_str = str(raw_id)
                data = item.get("data") or {}

                vacancies.append(
                    {
                        "id": f"x5_{raw_id_str}",
                        "company": self._resolve_company(item.get("business_units") or []),
                        "title": (item.get("name") or "").strip(),
                        "grade": None,
                        "city": item.get("city") or None,
                        "work_format": item.get("work_format") or None,
                        "experience": data.get("experience") or None,
                        "published_at": None,
                        "description": self._build_description(data),
                        "url": self.VACANCY_URL_TEMPLATE.format(raw_id=raw_id_str),
                    }
                )

            if not items or payload.get("next_page") is None:
                break
            page += 1

        return vacancies

    async def enrich(self, session, vacancy):
        del session
        return vacancy
