"""Парсер вакансий Wildberries."""

import asyncio
import logging

from parsers.base import BaseParser
from parsers.utils import normalize_city
import config


class WildberriesParser(BaseParser):
    async def parse(self, session, existing_ids, city_mappings):
        del existing_ids
        headers = dict(config.REQUEST_HEADERS)
        headers["Referer"] = "https://career.rwb.ru/vacancies"
        url = "https://career.rwb.ru/crm-api/api/v1/pub/vacancies"
        items = []
        seen_ids = set()
        while True:
            params = {"limit": 200, "offset": len(items)}
            if not config.CAPTURE_ALL_ROLES:
                params["direction_ids[]"] = 9
            async with session.get(url, params=params, headers=headers) as response:
                response.raise_for_status()
                payload = await response.json()
            data = payload.get("data") or {}
            page_items = data.get("items")
            if not isinstance(page_items, list):
                raise ValueError("Wildberries: API не подтвердил список")
            for item in page_items:
                if item.get("id") is None or item["id"] in seen_ids:
                    raise ValueError("Wildberries: отсутствующий или повторяющийся id")
                seen_ids.add(item["id"])
            items.extend(page_items)
            if not config.CAPTURE_ALL_ROLES:
                break
            total = (data.get("range") or {}).get("count")
            if not isinstance(total, int) or (not page_items and len(items) < total):
                raise ValueError("Wildberries: неполный каталог")
            if len(items) >= total:
                if len(items) != total:
                    raise ValueError("Wildberries: число вакансий не совпадает с count")
                break

        vacancies = []
        for item in items:
            vacancy_id = f"wb_{item.get('id')}"
            employment_types = item.get("employment_types") or []
            work_format = ", ".join(t.get("title", "") for t in employment_types if t.get("title")) or "Не указан"
            title = (item.get("name", "") or "").strip()

            vacancies.append(
                {
                    "id": vacancy_id,
                    "company": "Wildberries",
                    "title": title,
                    "grade": None,
                    "city": normalize_city(city_mappings, item.get("city_title")),
                    "work_format": work_format,
                    "experience": item.get("experience_type_title") or "Не указан",
                    "url": f"https://career.rwb.ru/vacancies/{item.get('id')}",
                    "description": None,
                    "source_json": item,
                }
            )
        return vacancies

    async def enrich(self, session, vacancy):
        should_sleep = False
        try:
            raw_id = (vacancy.get("id") or "").replace("wb_", "", 1)
            if not raw_id.isdigit():
                return vacancy

            headers = dict(config.REQUEST_HEADERS)
            headers["Referer"] = "https://career.rwb.ru/vacancies"
            details_url = f"https://career.rwb.ru/crm-api/api/v1/pub/vacancies/{raw_id}"
            should_sleep = True
            async with session.get(details_url, headers=headers) as response:
                response.raise_for_status()
                payload = await response.json()

            data = payload.get("data") or {}

            if not vacancy.get("grade") and data.get("skill_level_id") is not None:
                vacancy["grade"] = str(data.get("skill_level_id"))

            if not vacancy.get("description"):
                duties_arr = data.get("duties_arr") or []
                requirements_arr = data.get("requirements_arr") or []
                conditions_arr = data.get("conditions_arr") or []
                parts = [data.get("description"), *duties_arr, *requirements_arr, *conditions_arr]
                description = "\n\n".join((part or "").strip() for part in parts if (part or "").strip())
                if description:
                    vacancy["description"] = description
        except Exception as exc:
            logging.warning("Wildberries enrich ошибка для %s: %s", vacancy.get("id"), exc)
        finally:
            if should_sleep:
                await asyncio.sleep(0.3)

        return vacancy
