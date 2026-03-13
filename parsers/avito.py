"""Парсер вакансий Avito."""

from bs4 import BeautifulSoup

from enrichment.grade_guesser import guess_grade_from_title
from parsers.base import BaseParser
from parsers.utils import normalize_city
import config


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
            link = card.find("a")
            title = link.get_text(strip=True) if link else ""
            href = link.get("href") if link else ""
            data_attrs = {k: v for k, v in card.attrs.items() if k.startswith("data-")}
            vacancies.append(
                {
                    "id": f"avito_{card.get('data-vacancy-id')}",
                    "company": "Avito",
                    "title": title,
                    "grade": guess_grade_from_title(title),
                    "city": normalize_city(city_mappings, card.get("data-vacancy-geo")),
                    "work_format": "Удаленка" if card.get("data-vacancy-remote") == "Да" else "Офис",
                    "experience": "Не указан",
                    "url": f"https://career.avito.com{href}",
                    "short_description": None,
                    "source_json": {"data_attrs": data_attrs, "title": title, "href": href},
                }
            )
        return vacancies
