"""Парсер вакансий Точка Банк."""

import logging

from bs4 import BeautifulSoup, NavigableString, Tag

from parsers.base import BaseParser


logger = logging.getLogger(__name__)


class TochkaParser(BaseParser):
    EXPERIENCE_MAP = {
        "up_to_three_years": "1-3 года",
        "up_to_five_years": "3-5 лет",
        "over_five_years": "5+ лет",
    }

    WORK_FORMAT_MAP = {
        "remotely": "Удалёнка",
        "hybrid": "Гибрид",
        "trips": "Офис",
    }

    TARGET_H2_PATTERNS = (
        "Что делать",
        "Ты подойдёшь",
        "Что ждёт тебя",
    )

    @staticmethod
    def _extract_section_text(header):
        parts = []
        parent = header.parent
        for sibling in header.next_siblings:
            if isinstance(sibling, NavigableString):
                text = str(sibling).strip()
                if text:
                    parts.append(text)
                continue

            if not isinstance(sibling, Tag):
                continue

            if sibling.name == "h2":
                break

            if sibling.parent is not parent:
                break

            text = sibling.get_text("\n", strip=True)
            if text:
                parts.append(text)

        section_text = "\n".join(parts).strip()
        return section_text or None

    async def parse(self, session, existing_ids, city_mappings):
        del existing_ids
        del city_mappings

        base_url = "https://hr.tochka.com/api/v2/hr/vacancies/"
        page = 1
        page_size = 20
        vacancies = []

        while True:
            params = {
                "category": "it",
                "specializations[]": "product-management",
                "page": page,
            }
            async with session.get(base_url, params=params) as response:
                response.raise_for_status()
                payload = await response.json()

            items = payload.get("items") or []
            meta = payload.get("meta") or {}
            total = meta.get("total") or 0

            if not items:
                break

            for item in items:
                slug = item.get("slug")
                title = (item.get("title") or "").strip()
                city_obj = item.get("city") or {}
                city_name = city_obj.get("name") if isinstance(city_obj, dict) else None

                vacancies.append(
                    {
                        "id": str(slug),
                        "title": title,
                        "company": "Точка",
                        "city": city_name or "Не указан",
                        "experience": self.EXPERIENCE_MAP.get(item.get("workExperience"), "не указан"),
                        "work_format": self.WORK_FORMAT_MAP.get(item.get("workFormat"), "Не указан"),
                        "grade": "Lead+" if item.get("type") == "lead" else None,
                        "url": f"https://hr.tochka.com/vacancies/catalog/{slug}/",
                        "published_at": None,
                        "description": None,
                    }
                )

            if page * page_size >= total:
                break
            page += 1

        return vacancies

    async def enrich(self, session, vacancy):
        slug = vacancy.get("id")
        url = f"https://hr.tochka.com/vacancies/catalog/{slug}/"

        try:
            async with session.get(url) as response:
                response.raise_for_status()
                html = await response.text()

            soup = BeautifulSoup(html, "html.parser")
            description_parts = []

            for header in soup.find_all("h2"):
                header_text = header.get_text(" ", strip=True)
                if not any(pattern in header_text for pattern in self.TARGET_H2_PATTERNS):
                    continue

                section_text = self._extract_section_text(header)
                if section_text:
                    description_parts.append(section_text)

            new_description = "\n\n".join(description_parts).strip()
            current_description = vacancy.get("description") or ""
            if new_description and len(new_description) >= len(current_description):
                vacancy["description"] = new_description
        except Exception as exc:
            logger.warning("Tochka enrich: не удалось обработать %s: %s", url, exc)

        return vacancy
