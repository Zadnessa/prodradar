"""Парсер вакансий Avito."""

import asyncio
import json
import logging

from bs4 import BeautifulSoup

from parsers.base import BaseParser
from parsers.utils import normalize_city
import config


logger = logging.getLogger(__name__)


def _resolve_grade(title):
    title_lower = title.lower()
    if title_lower.startswith("ведущий") or title_lower.startswith("ведущая"):
        return "Senior"
    if "руководитель" in title_lower:
        return "Lead+"
    if "cpo" in title_lower:
        return "Lead+"
    if "head of" in title_lower:
        return "Lead+"
    return None


class AvitoParser(BaseParser):
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
    def _extract_description_from_sections(soup):
        target_sections = {"Вам предстоит:", "Мы ждём, что вы:"}
        sections = []
        for section in soup.find_all("section", class_="vacancies-detail__description"):
            header = section.find("h2")
            section_name = header.get_text(" ", strip=True) if header else ""
            if section_name not in target_sections:
                continue

            text = section.get_text("\n", strip=True)
            if text:
                lines = [line.strip() for line in text.splitlines() if line.strip()]
                if lines and lines[0] == section_name:
                    lines = lines[1:]
                section_text = "\n".join(lines).strip()
                if section_text:
                    sections.append(section_text)

        description = "\n\n".join(sections).strip()
        return description or None

    async def parse(self, session, existing_ids, city_mappings):
        del existing_ids
        headers = dict(config.REQUEST_HEADERS)
        headers["X-Requested-With"] = "XMLHttpRequest"
        url = "https://career.avito.com/vacancies/?action=filter&direction=upravlenie-produktom"

        async with session.get(url, headers=headers) as response:
            response.raise_for_status()
            payload = await response.json()

        soup = BeautifulSoup(payload.get("html", ""), "html.parser")
        cards = soup.find_all("div", class_="vacancies-section__item")

        vacancies = []
        for card in cards:
            link = card.find("a", class_="vacancies-section__item-name")
            title = (link.get_text(strip=True) if link else "").strip()
            href = link.get("href") if link else ""
            work_format_el = card.select_one("span.vacancies-section__item-format")
            work_format = (work_format_el.get_text(strip=True) if work_format_el else "").strip() or "Не указан"
            data_attrs = {k: v for k, v in card.attrs.items() if k.startswith("data-")}
            vacancies.append(
                {
                    "id": f"avito_{card.get('data-vacancy-id')}",
                    "company": "Avito",
                    "title": title,
                    "grade": _resolve_grade(title),
                    "city": normalize_city(city_mappings, card.get("data-vacancy-geo")),
                    "work_format": work_format,
                    "experience": "Не указан",
                    "url": f"https://career.avito.com{href}",
                    "short_description": None,
                    "source_json": {
                        "data_attrs": data_attrs,
                        "title": title,
                        "href": href,
                        "team": card.get("data-vacancy-team"),
                    },
                }
            )
        return vacancies

    async def enrich(self, session, vacancy):
        try:
            async with session.get(vacancy["url"], headers=config.REQUEST_HEADERS) as response:
                response.raise_for_status()
                html = await response.text()
        except Exception as exc:
            logger.warning("Avito enrich: не удалось загрузить HTML для %s: %s", vacancy.get("url"), exc)
            return vacancy
        finally:
            await asyncio.sleep(0.3)

        try:
            soup = BeautifulSoup(html, "html.parser")
            vacancy.setdefault("source_json", {})

            json_ld = self._extract_job_posting_json_ld(soup)
            if json_ld:
                vacancy["source_json"]["json_ld"] = json_ld

                if not vacancy.get("short_description"):
                    description = BeautifulSoup(json_ld.get("description", ""), "html.parser").get_text("\n", strip=True).strip()
                    if description:
                        vacancy["short_description"] = description[:500]

                if not vacancy.get("published_at"):
                    published_at = json_ld.get("datePosted")
                    if published_at:
                        vacancy["published_at"] = published_at
                return vacancy

            description = self._extract_description_from_sections(soup)
            if description and not vacancy.get("short_description"):
                vacancy["short_description"] = description[:500]
        except Exception as exc:
            logger.warning("Avito enrich: ошибка парсинга HTML для %s: %s", vacancy.get("url"), exc)

        return vacancy
