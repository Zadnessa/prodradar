"""Парсер вакансий T-Bank."""

from bs4 import BeautifulSoup
from parsers.base import BaseParser
import config


class TBankParser(BaseParser):
    @staticmethod
    def _build_grade(tags):
        grade_priority = {
            "Junior": 1,
            "Middle": 2,
            "Senior": 3,
            "Lead": 4,
            "Head": 5,
            "CPO": 5,
        }
        grade_tags = sorted({tag for tag in (tags or []) if tag in grade_priority}, key=lambda x: grade_priority[x])
        if len(grade_tags) == 1:
            grade = grade_tags[0]
        elif len(grade_tags) > 1:
            grade = f"{grade_tags[0]}-{grade_tags[-1]}"
        else:
            grade = None

        if grade:
            grade = grade.replace("Head", "Lead+").replace("CPO", "Lead+")
        return grade

    @staticmethod
    def _resolve_city(city_mappings, region_id):
        if region_id is None:
            return "Удалёнка"
        return city_mappings.get(("tbank_region", str(region_id)), str(region_id))

    @staticmethod
    def _resolve_city_slug(city_mappings, region_id):
        if region_id is None:
            return "remote"
        return city_mappings.get(("tbank_city_slug", str(region_id)), str(region_id))

    @staticmethod
    def _merge_cities(primary_city, duplicate_city):
        cities = []
        for city_value in (primary_city, duplicate_city):
            for city in (city_value or '').split(','):
                normalized = city.strip()
                if normalized and normalized not in cities:
                    cities.append(normalized)
        return ', '.join(cities) or 'Не указан'

    async def parse(self, session, existing_ids, city_mappings):
        url = "https://www.tbank.ru/pfpjobs/papi/getVacancies"
        pagination = {"it": {"limit": 100, "offset": 0}}
        collected = []

        while True:
            payload = {
                "filters": {"tcareer_it_profession": ["product-management"]},
                "pagination": pagination,
            }

            async with session.post(url, headers=config.REQUEST_HEADERS, json=payload) as response:
                response.raise_for_status()
                result = await response.json()

            body = result.get("payload", {})
            collected.extend(body.get("vacancies", []))

            next_pagination = ((body.get("nextPagination") or {}).get("it") or {})
            if next_pagination.get("isFinished", True):
                break
            pagination = {
                "it": {
                    "limit": pagination["it"]["limit"],
                    "offset": next_pagination.get("offset", pagination["it"]["offset"]),
                }
            }

        vacancies_by_key = {}
        ordered_keys = []
        for item in collected:
            title = (item.get("title", "") or "").strip()
            region_id = item.get("regionId")
            seo_slug = item.get("seoSlug")
            url_slug = item.get("urlSlug")
            city_slug = self._resolve_city_slug(city_mappings, region_id)
            city = self._resolve_city(city_mappings, region_id)
            short_html = item.get("shortDescription") or ""
            short_description = BeautifulSoup(short_html, "html.parser").get_text(" ", strip=True) or None
            if seo_slug:
                vacancy_url = f"https://www.tbank.ru/career/it/vacancy/{city_slug}/{seo_slug}/{url_slug}/"
            else:
                vacancy_url = f"https://www.tbank.ru/career/it/{url_slug}/"

            vacancy = {
                "id": f"tbank_{url_slug}",
                "company": "Т-Банк",
                "title": title,
                "grade": self._build_grade(item.get("tags")),
                "city": city,
                "work_format": "Не указан",
                "experience": "Не указан",
                "url": vacancy_url,
                "short_description": short_description,
                "source_json": item,
            }

            dedupe_key = (seo_slug or "", title)
            if dedupe_key in vacancies_by_key:
                vacancies_by_key[dedupe_key]["city"] = self._merge_cities(vacancies_by_key[dedupe_key].get("city"), city)
                continue

            vacancies_by_key[dedupe_key] = vacancy
            ordered_keys.append(dedupe_key)

        return [vacancies_by_key[key] for key in ordered_keys]

    async def enrich(self, session, vacancy):
        # enrichment отключён: getVacancy возвращает пустышку для source=publisher (проверено 2026-03-22), в будущем заменить на HTML-парсинг
        return vacancy
