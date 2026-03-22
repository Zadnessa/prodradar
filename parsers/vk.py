"""Парсер вакансий VK."""

import asyncio
import re
from bs4 import NavigableString, Tag
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup
from parsers.base import BaseParser
from parsers.utils import normalize_city
import config


class VKParser(BaseParser):
    @staticmethod
    def _extract_section_text_from_h3(soup, section_name):
        header = soup.find("h3", string=lambda value: isinstance(value, str) and value.strip() == section_name)
        if not header or not getattr(header, "parent", None):
            return None

        parts = []
        for sibling in header.parent.next_siblings:
            if isinstance(sibling, NavigableString):
                text = str(sibling).strip()
                if text:
                    parts.append(text)
                continue

            if not isinstance(sibling, Tag):
                continue

            if sibling.find(["h2", "h3"]):
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
        base_url = "https://team.vk.company/career/api/v2/vacancies/"
        limit = 50
        offset = 0
        vacancies = []

        while True:
            params = {"limit": limit, "offset": offset, "tags": 2259}
            async with session.get(base_url, headers=config.REQUEST_HEADERS, params=params) as response:
                response.raise_for_status()
                payload = await response.json()

            for item in payload.get("results", []):
                raw_work_format = (item.get("work_format") or "").strip().lower()
                work_map = {
                    "комбинированный": "Гибрид",
                    "удалённый": "Удаленка",
                    "удаленный": "Удаленка",
                    "офисный": "Офис",
                }
                work_format = work_map.get(raw_work_format, item.get("work_format") or "Не указан")
                title = (item.get("title", "") or "").strip()
                vacancy_id = f"vk_{item.get('id')}"
                grade = None
                short_description = None

                if vacancy_id not in existing_ids:
                    try:
                        html_url = f"https://team.vk.company/vacancy/{item.get('id')}/"
                        async with session.get(html_url, headers=config.REQUEST_HEADERS) as html_response:
                            html_response.raise_for_status()
                            html = await html_response.text()
                        soup = BeautifulSoup(html, "html.parser")

                        grade = self._normalize_grade_text(self._extract_grade_from_level_block(soup))
                        if not grade:
                            meta = soup.find("meta", attrs={"name": "description"})
                            content = meta.get("content", "") if meta else ""
                            match = re.search(r"уровня\s+([\w,\s]+?)(?:\s+в\s+проект|\s+с\s+графиком)", content, flags=re.IGNORECASE)
                            if match:
                                grade = self._normalize_grade_text(match.group(1).strip())

                        description_parts = [
                            self._extract_section_text_from_h3(soup, "Задачи"),
                            self._extract_section_text_from_h3(soup, "Требования"),
                        ]
                        description = "\n\n".join(part for part in description_parts if part).strip()
                        if description:
                            short_description = description[:500]
                    except Exception:
                        grade = None
                    await asyncio.sleep(0.5)

                vacancies.append(
                    {
                        "id": vacancy_id,
                        "company": "VK",
                        "title": title,
                        "grade": grade,
                        "city": normalize_city(city_mappings, (item.get("town") or {}).get("name")),
                        "work_format": work_format,
                        "experience": "Не указан",
                        "url": f"https://team.vk.company/vacancy/{item.get('id')}/",
                        "short_description": short_description,
                        "source_json": {**item, "group_name": (item.get("group") or {}).get("name")},
                    }
                )

            next_url = payload.get("next")
            if not next_url:
                break
            next_offset = parse_qs(urlparse(next_url).query).get("offset", [None])[0]
            if next_offset is None:
                break
            offset = int(next_offset)

        return vacancies
