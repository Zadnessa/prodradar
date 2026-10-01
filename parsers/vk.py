"""Парсер вакансий VK."""

import asyncio
import re
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup, NavigableString, Tag

import config
from parsers.base import BaseParser
from parsers.utils import normalize_city


class VKParser(BaseParser):
    @staticmethod
    def _extract_section_text_from_h3(soup, section_name):
        article_root = None
        article_header = None

        headers = soup.find_all("h3", string=lambda value: isinstance(value, str) and value.strip() == section_name)
        for header in headers:
            if getattr(header, "parent", None) and getattr(header.parent, "parent", None):
                candidate_article = header.parent.parent.find("div", class_="article")
                if candidate_article:
                    article_root = candidate_article
                    article_header = article_root.find(
                        "h3",
                        string=lambda value: isinstance(value, str) and value.strip() == section_name,
                    )
                    if article_header:
                        break

            candidate_article = header.find_parent("div", class_="article")
            if candidate_article:
                article_root = candidate_article
                article_header = header
                break

        if not article_root or not article_header:
            return None

        parts = []
        for sibling in article_header.next_siblings:
            if isinstance(sibling, NavigableString):
                text = str(sibling).strip()
                if text:
                    parts.append(text)
                continue

            if not isinstance(sibling, Tag):
                continue

            if sibling.name == "h3":
                break

            text = sibling.get_text("\n", strip=True)
            if text:
                parts.append(text)

        section_text = "\n".join(parts).strip()
        return section_text or None

    @staticmethod
    def _extract_grade_from_level_block(soup):
        level_header = soup.find("h4", string=lambda value: isinstance(value, str) and value.strip().lower() == "уровень")
        if not level_header or not getattr(level_header, "parent", None) or not getattr(level_header.parent, "parent", None):
            return None

        grandparent = level_header.parent.parent
        element_children = [child for child in grandparent.children if not isinstance(child, NavigableString)]
        if len(element_children) < 2:
            return None

        grade_text = element_children[1].get_text(" ", strip=True)
        return grade_text or None

    @staticmethod
    def _normalize_grade_text(raw_grade):
        if not raw_grade:
            return None

        compact_grade = re.sub(r"[^a-z]", "", raw_grade.lower())
        known_levels = ("intern", "junior", "middle", "senior")
        found_levels = [level for level in known_levels if level in compact_grade]
        if len(found_levels) > 1:
            return ", ".join(found_levels)
        if len(found_levels) == 1:
            return found_levels[0]

        cleaned_grade = raw_grade.strip()
        return cleaned_grade or None

    async def parse(self, session, existing_ids, city_mappings):
        del existing_ids
        base_url = "https://team.vk.company/career/api/v2/vacancies/"
        limit = 50
        offset = 0
        vacancies = []
        seen_ids = set()

        while True:
            params = {"limit": limit, "offset": offset, "tags": 2259}
            async with session.get(base_url, headers=config.REQUEST_HEADERS, params=params) as response:
                response.raise_for_status()
                payload = await response.json()

            items = payload.get("results")
            if not isinstance(items, list):
                raise ValueError("VK: API не подтвердил список")
            for item in items:
                raw_id = item.get("id")
                if raw_id is None or raw_id in seen_ids:
                    raise ValueError("VK: отсутствующий или повторяющийся id страницы")
                seen_ids.add(raw_id)
                raw_work_format = (item.get("work_format") or "").strip().lower()
                work_map = {
                    "комбинированный": "Гибрид",
                    "гибкий": "Гибрид",
                    "удалённый": "Удаленка",
                    "удаленный": "Удаленка",
                    "офисный": "Офис",
                }
                title = (item.get("title", "") or "").strip()

                vacancies.append(
                    {
                        "id": f"vk_{item.get('id')}",
                        "company": "VK",
                        "title": title,
                        "grade": None,
                        "city": normalize_city(city_mappings, (item.get("town") or {}).get("name")),
                        "work_format": work_map.get(raw_work_format, item.get("work_format") or "Не указан"),
                        "experience": "Не указан",
                        "url": f"https://team.vk.company/vacancy/{item.get('id')}/",
                        "description": None,
                        "source_json": {**item, "group_name": (item.get("group") or {}).get("name")},
                    }
                )

            next_url = payload.get("next")
            if not next_url:
                total = payload.get("count")
                if isinstance(total, int) and len(seen_ids) != total:
                    raise ValueError("VK: неполный список относительно count")
                break
            next_offset = parse_qs(urlparse(next_url).query).get("offset", [None])[0]
            if next_offset is None or not items or int(next_offset) <= offset:
                raise ValueError("VK: пагинация не продвигается")
            offset = int(next_offset)

        return vacancies

    async def enrich(self, session, vacancy):
        try:
            async with session.get(vacancy["url"], headers=config.REQUEST_HEADERS) as html_response:
                html_response.raise_for_status()
                html = await html_response.text()
        except Exception:
            await asyncio.sleep(0.5)
            return vacancy

        try:
            soup = BeautifulSoup(html, "html.parser")
            grade = self._normalize_grade_text(self._extract_grade_from_level_block(soup))
            if grade and vacancy.get("grade") in (None, "", "Не указан"):
                vacancy["grade"] = grade

            description_parts = [
                self._extract_section_text_from_h3(soup, "Задачи"),
                self._extract_section_text_from_h3(soup, "Требования"),
            ]
            description = "\n\n".join(part for part in description_parts if part).strip()
            if len(description) > len(vacancy.get("description") or ""):
                vacancy["description"] = description
        finally:
            await asyncio.sleep(0.5)

        return vacancy
