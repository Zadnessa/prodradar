"""Парсер вакансий T-Bank."""

import asyncio
import logging

from bs4 import BeautifulSoup, NavigableString, Tag
from parsers.base import BaseParser
import config


logger = logging.getLogger(__name__)


class TBankParser(BaseParser):
    SECTION_NAMES = ("Описание", "Обязанности", "Требования", "Мы предлагаем")
    WORK_FORMAT_TAGS = {
        "Удаленный": "Удалёнка",
        "Гибрид": "Гибрид",
        "Офис": "Офис",
    }

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
    def _merge_cities(primary_city, duplicate_city):
        cities = []
        for city_value in (primary_city, duplicate_city):
            for city in (city_value or '').split(','):
                normalized = city.strip()
                if normalized and normalized not in cities:
                    cities.append(normalized)
        return ', '.join(cities) or 'Не указан'

    @staticmethod
    def _extract_work_format(tags):
        for tag in tags or []:
            if tag in TBankParser.WORK_FORMAT_TAGS:
                return TBankParser.WORK_FORMAT_TAGS[tag]
        return "Не указан"

    @staticmethod
    def _collect_section_text(header):
        parts = []
        for sibling in header.next_siblings:
            if isinstance(sibling, NavigableString):
                text = str(sibling).strip()
                if text:
                    parts.append(text)
                continue

            if not isinstance(sibling, Tag):
                continue

            if sibling.name in {"h1", "h2"}:
                break

            text = sibling.get_text("\n", strip=True)
            if text:
                parts.append(text)

        return "\n".join(parts).strip()

    @staticmethod
    def _extract_html_sections(soup):
        sections = {}
        for header in soup.find_all("h2"):
            section_name = header.get_text(" ", strip=True)
            if section_name not in TBankParser.SECTION_NAMES:
                continue

            section_text = TBankParser._collect_section_text(header)
            if section_text:
                sections[section_name] = section_text
        return sections

    async def parse(self, session, existing_ids, city_mappings):
        del existing_ids
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
            city = self._resolve_city(city_mappings, region_id)
            short_html = item.get("shortDescription") or ""
            description = BeautifulSoup(short_html, "html.parser").get_text(" ", strip=True) or None
            if seo_slug:
                vacancy_url = f"https://www.tbank.ru/career/it/vacancy/moscow/{seo_slug}/{url_slug}/"
            else:
                vacancy_url = f"https://www.tbank.ru/career/it/{url_slug}/"

            vacancy = {
                "id": f"tbank_{url_slug}",
                "company": "Т-Банк",
                "title": title,
                "grade": self._build_grade(item.get("tags")),
                "city": city,
                "work_format": self._extract_work_format(item.get("tags")),
                "experience": "Не указан",
                "url": vacancy_url,
                "description": description,
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
        try:
            async with session.get(vacancy["url"], headers=config.REQUEST_HEADERS) as response:
                response.raise_for_status()
                html = await response.text(encoding="utf-8")
        except Exception as exc:
            logger.warning("T-Bank enrich: не удалось загрузить HTML для %s: %s", vacancy.get("url"), exc)
            return vacancy
        finally:
            await asyncio.sleep(0.3)

        try:
            soup = BeautifulSoup(html, "html.parser")
            sections = self._extract_html_sections(soup)
            if not sections:
                logger.warning("T-Bank enrich: не найдены HTML-секции для %s", vacancy.get("url"))
                return vacancy

            vacancy.setdefault("source_json", {})
            vacancy["source_json"]["html_sections"] = sections

            summary_parts = [
                sections.get("Описание"),
                sections.get("Обязанности"),
                sections.get("Требования"),
            ]
            summary = "\n\n".join(part for part in summary_parts if part).strip()
            current_description = vacancy.get("description") or ""
            if summary and len(summary) > len(current_description):
                vacancy["description"] = summary

            if vacancy.get("work_format") in (None, "", "Не указан"):
                vacancy["work_format"] = self._extract_work_format((vacancy.get("source_json") or {}).get("tags"))
        except Exception as exc:
            logger.warning("T-Bank enrich: ошибка парсинга HTML для %s: %s", vacancy.get("url"), exc)

        return vacancy
