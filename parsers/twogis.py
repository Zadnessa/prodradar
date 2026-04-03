"""Парсер вакансий 2ГИС."""

import html
import json
import logging
import re

from bs4 import BeautifulSoup, NavigableString, Tag

import config
from parsers.base import BaseParser


logger = logging.getLogger(__name__)


class TwoGisParser(BaseParser):
    """Парсер 2ГИС: HTML SSR список и enrichment из HTML/JSON-LD."""

    LIST_URL = "https://job.2gis.ru/project/"
    DETAIL_URL_TEMPLATE = "https://job.2gis.ru/project/{raw_id}/"

    TARGET_H2_PATTERNS = (
        "что предстоит делать",
        "что будет входить в задачи",
        "вам точно предстоит",
        "ключевые задачи",
        "что мы ожидаем",
        "кого мы ищем",
        "что предлагаем",
        "что мы предлагаем",
    )

    @staticmethod
    def _clean_text(value):
        if value is None:
            return ""
        text = html.unescape(str(value)).replace("\u00a0", " ")
        return text.strip()

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

    @staticmethod
    def _extract_job_posting_json_ld(soup):
        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            raw_json = (script.string or script.get_text() or "").strip()
            if not raw_json:
                continue

            try:
                parsed = json.loads(raw_json)
            except json.JSONDecodeError:
                continue

            candidates = parsed if isinstance(parsed, list) else [parsed]
            for candidate in candidates:
                if isinstance(candidate, dict) and candidate.get("@type") == "JobPosting":
                    return candidate

        return None

    @staticmethod
    def _extract_localities(job_location):
        if not job_location:
            return []

        items = job_location if isinstance(job_location, list) else [job_location]
        localities = []

        for item in items:
            if not isinstance(item, dict):
                continue

            address = item.get("address")
            locality = address.get("addressLocality") if isinstance(address, dict) else None
            locality_text = html.unescape(str(locality)).strip() if locality else ""
            if locality_text:
                localities.append(locality_text)

        return localities

    async def parse(self, session, existing_ids, city_mappings):
        del existing_ids
        del city_mappings

        async with session.get(self.LIST_URL, headers=config.REQUEST_HEADERS) as response:
            response.raise_for_status()
            html_text = await response.text()

        soup = BeautifulSoup(html_text, "html.parser")
        links = soup.find_all("a", href=re.compile(r"/project/(\d+)/?$"))

        vacancies = []
        seen_ids = set()

        for link in links:
            href = (link.get("href") or "").strip()
            match = re.search(r"/project/(\d+)/?$", href)
            if not match:
                continue

            raw_id = match.group(1)
            if raw_id in seen_ids:
                continue
            seen_ids.add(raw_id)

            title = self._clean_text(link.get_text(" ", strip=True))
            card = link.find_parent("li") or link.find_parent("div") or link.parent
            card_text = self._clean_text(card.get_text(" ", strip=True) if card else "")
            card_text_lower = card_text.lower()
            work_format = "Удалённая работа" if "удалённая работа" in card_text_lower else "Не указан"

            vacancies.append(
                {
                    "id": f"2gis_{raw_id}",
                    "company": "2ГИС",
                    "title": title,
                    "grade": None,
                    "city": "Не указан",
                    "work_format": work_format,
                    "url": self.DETAIL_URL_TEMPLATE.format(raw_id=raw_id),
                    "description": None,
                    "experience": None,
                    "published_at": None,
                }
            )

        return vacancies

    async def enrich(self, session, vacancy):
        try:
            raw_id = str(vacancy.get("id") or "").removeprefix("2gis_")
            if not raw_id:
                return vacancy

            url = self.DETAIL_URL_TEMPLATE.format(raw_id=raw_id)
            async with session.get(url, headers=config.REQUEST_HEADERS) as response:
                response.raise_for_status()
                html_text = await response.text()

            soup = BeautifulSoup(html_text, "html.parser")

            description_parts = []
            for header in soup.find_all("h2"):
                header_text = header.get_text(" ", strip=True).lower()
                if not any(pattern in header_text for pattern in self.TARGET_H2_PATTERNS):
                    continue

                section_text = self._extract_section_text(header)
                if section_text:
                    description_parts.append(section_text)

            new_description = "\n\n".join(description_parts).strip()
            current_description = vacancy.get("description") or ""
            if new_description and len(new_description) > len(current_description):
                vacancy["description"] = new_description

            if not vacancy.get("experience"):
                page_text = soup.get_text(" ", strip=True)
                match = re.search(
                    r"[Оо]пыт\s+(?:работы?\s+)?(?:\S+\s+){0,3}от\s+(\d+)\s*(?:лет|года|год)",
                    page_text,
                )
                if match:
                    vacancy["experience"] = match.group(0).strip()

            job_posting = self._extract_job_posting_json_ld(soup)
            if job_posting:
                date_posted = self._clean_text(job_posting.get("datePosted"))
                if date_posted and not vacancy.get("published_at"):
                    vacancy["published_at"] = date_posted

                localities = self._extract_localities(job_posting.get("jobLocation"))
                if localities and vacancy.get("city") == "Не указан":
                    vacancy["city"] = ", ".join(localities)
        except Exception as exc:
            logger.warning("TwoGis enrich: не удалось обработать вакансию %s: %s", vacancy.get("id"), exc)

        return vacancy
