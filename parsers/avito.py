"""Парсер вакансий Avito."""

from bs4 import BeautifulSoup

from parsers.base import BaseParser
from parsers.utils import normalize_city
import config


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
    async def parse(self, session, existing_ids, city_mappings):
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
