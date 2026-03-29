"""Парсер вакансий Контур."""

import html
import json
import logging
import re

from bs4 import BeautifulSoup

import config
from parsers.base import BaseParser


logger = logging.getLogger(__name__)


class KonturParser(BaseParser):
    """Парсер Контур: список вакансий через SSR HTML, enrichment через JSON-LD."""

    LIST_URL = "https://kontur.ru/career/vacancies?direction=product-management"
    DETAIL_URL_TEMPLATE = "https://kontur.ru/career/vacancies/{vacancy_id}"

    VALID_GRADE_TOKENS = {
        "junior",
        "middle",
        "middle+",
        "senior",
        "lead",
        "middle/middle+",
        "middle+/senior",
        "junior/middle",
        "senior/lead",
    }

    @staticmethod
    def _clean_text(value):
        if value is None:
            return ""
        text = html.unescape(str(value)).replace("\u00a0", " ")
        return text.strip()

    @classmethod
    def _extract_title_and_grade(cls, raw_title):
        title = cls._clean_text(raw_title)
        if not title or "," not in title:
            return title, None

        head, tail = title.rsplit(",", 1)
        grade_candidate = cls._clean_text(tail).lower()
        if grade_candidate not in cls.VALID_GRADE_TOKENS:
            return title, None

        grade = grade_candidate.replace("/", "-")
        return cls._clean_text(head), grade

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
            if isinstance(address, dict):
                locality = address.get("addressLocality")
            else:
                locality = None

            locality_text = html.unescape(str(locality)).strip() if locality else ""
            if locality_text:
                localities.append(locality_text)

        return localities

    @staticmethod
    def _extract_experience_from_html(page_text):
        match = re.search(r"Опыт\s+от\s+\d+\s*(?:лет|года|год)", page_text, flags=re.IGNORECASE)
        if not match:
            return None
        return match.group(0).strip()

    @staticmethod
    def _extract_description_fallback(soup):
        blocks = soup.select("div.vacancy-rubric__body")
        parts = []

        for block in blocks:
            text = block.get_text("\n", strip=True)
            if text:
                parts.append(text)

        return "\n".join(parts).strip() or None

    async def parse(self, session, existing_ids, city_mappings):
        del existing_ids
        del city_mappings

        async with session.get(self.LIST_URL, headers=config.REQUEST_HEADERS) as response:
            response.raise_for_status()
            html_text = await response.text()

        soup = BeautifulSoup(html_text, "html.parser")
        links = soup.find_all("a", href=re.compile(r"^/career/vacancies/(\d+)/?$"))

        vacancies = []
        seen_ids = set()

        for link in links:
            href = (link.get("href") or "").strip()
            match = re.search(r"/career/vacancies/(\d+)/?$", href)
            if not match:
                continue

            raw_id = match.group(1)
            vacancy_id = f"kontur_{raw_id}"
            if vacancy_id in seen_ids:
                continue
            seen_ids.add(vacancy_id)

            title, grade = self._extract_title_and_grade(link.get_text(" ", strip=True))

            card = link.find_parent(attrs={"data-vacancy-id": True}) or link.find_parent("li") or link.parent
            city_el = card.select_one("[class*='city']") if card else None
            format_el = card.select_one("[class*='format']") if card else None

            city = self._clean_text(city_el.get_text(" ", strip=True) if city_el else "") or "Не указан"
            work_format = self._clean_text(format_el.get_text(" ", strip=True) if format_el else "") or "Не указан"

            vacancies.append(
                {
                    "id": vacancy_id,
                    "company": "Контур",
                    "title": title,
                    "grade": grade,
                    "city": city,
                    "work_format": work_format,
                    "url": self.DETAIL_URL_TEMPLATE.format(vacancy_id=raw_id),
                    "description": None,
                    "experience": None,
                    "published_at": None,
                }
            )

        return vacancies

    async def enrich(self, session, vacancy):
        raw_id = str(vacancy.get("id") or "").removeprefix("kontur_")
        if not raw_id:
            return vacancy

        url = self.DETAIL_URL_TEMPLATE.format(vacancy_id=raw_id)

        try:
            async with session.get(url, headers=config.REQUEST_HEADERS) as response:
                response.raise_for_status()
                html_text = await response.text()

            soup = BeautifulSoup(html_text, "html.parser")
            json_ld = self._extract_job_posting_json_ld(soup)

            json_ld_description = None
            if json_ld:
                description_raw = json_ld.get("description")
                if description_raw:
                    description_text = BeautifulSoup(html.unescape(str(description_raw)), "html.parser").get_text("\n", strip=True)
                    if description_text:
                        json_ld_description = description_text.strip()

                published_at = self._clean_text(json_ld.get("datePosted"))
                if published_at and not vacancy.get("published_at"):
                    vacancy["published_at"] = published_at

                localities = self._extract_localities(json_ld.get("jobLocation"))
                if localities:
                    new_city = ", ".join(localities)
                    current_city = str(vacancy.get("city") or "").strip()
                    should_replace_city = (
                        "и ещё" in current_city.lower()
                        or current_city.count(",") < new_city.count(",")
                    )
                    if should_replace_city or not current_city:
                        vacancy["city"] = new_city

            if not json_ld_description:
                json_ld_description = self._extract_description_fallback(soup)

            current_description = vacancy.get("description") or ""
            if json_ld_description and len(json_ld_description) > len(current_description):
                vacancy["description"] = json_ld_description

            if not vacancy.get("experience"):
                experience = self._extract_experience_from_html(soup.get_text(" ", strip=True))
                if experience:
                    vacancy["experience"] = experience
        except Exception as exc:
            logger.warning("Kontur enrich: не удалось обработать вакансию %s: %s", vacancy.get("id"), exc)

        return vacancy
