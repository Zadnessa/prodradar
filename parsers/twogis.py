"""Парсер 2ГИС: актуальный JSON API списка и полного описания."""

from bs4 import BeautifulSoup

import config
from parsers.base import BaseParser


class TwoGisParser(BaseParser):
    LIST_URL = "https://job.2gis.ru/api/v1/vacancies"
    DETAIL_URL_TEMPLATE = "https://job.2gis.ru/api/v1/vacancies/{raw_id}"

    async def parse(self, session, existing_ids, city_mappings):
        del existing_ids, city_mappings
        vacancies = []
        seen_ids = set()
        page = 1
        while True:
            async with session.get(self.LIST_URL, params={"page": page}, headers=config.REQUEST_HEADERS) as response:
                response.raise_for_status()
                payload = await response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
                raise ValueError("2ГИС: изменился контракт списка вакансий")
            for item in payload["items"]:
                raw_id = item.get("id")
                direction_slug = (item.get("direction") or {}).get("slug")
                if raw_id is None or not direction_slug or not item.get("title"):
                    raise ValueError("2ГИС: в карточке отсутствуют id, направление или заголовок")
                if raw_id in seen_ids:
                    raise ValueError("2ГИС: повтор вакансии при пагинации")
                seen_ids.add(raw_id)
                vacancies.append({
                    "id": f"2gis_{raw_id}", "company": "2ГИС", "title": item["title"].strip(),
                    "grade": None, "city": (item.get("city") or {}).get("name"),
                    "work_format": "Удалёнка" if item.get("isRemote") else "Офис",
                    "url": f"https://job.2gis.ru/vacancies/{direction_slug}/{raw_id}",
                    "description": None, "experience": None, "published_at": None,
                })
            total_pages = int(payload.get("totalPages") or 0)
            if total_pages < page and payload["items"]:
                raise ValueError("2ГИС: отсутствует корректное число страниц")
            if page >= total_pages:
                if payload.get("totalItems") is not None and len(vacancies) != int(payload["totalItems"]):
                    raise ValueError("2ГИС: получен неполный список вакансий")
                break
            page += 1
        return vacancies

    async def enrich(self, session, vacancy):
        raw_id = str(vacancy.get("id") or "").removeprefix("2gis_")
        if not raw_id:
            return vacancy
        async with session.get(self.DETAIL_URL_TEMPLATE.format(raw_id=raw_id), headers=config.REQUEST_HEADERS) as response:
            response.raise_for_status()
            payload = await response.json()
        if not isinstance(payload, dict) or "description" not in payload:
            raise ValueError("2ГИС: изменился контракт полного описания")
        description = BeautifulSoup(payload.get("description") or "", "html.parser").get_text("\n", strip=True)
        if len(description) > len(vacancy.get("description") or ""):
            vacancy["description"] = description
        if not vacancy.get("city"):
            vacancy["city"] = (payload.get("city") or {}).get("name")
        return vacancy
