"""Парсер вакансий T-Bank."""

from bs4 import BeautifulSoup
from enrichment.grade_guesser import guess_grade_from_title
from parsers.base import BaseParser
import config


class TBankParser(BaseParser):
    async def parse(self, session, existing_ids, city_mappings):
        url = "https://www.tbank.ru/pfpjobs/papi/getVacancies"
        payload = {
            "filters": {"tag": ["product-manager"]},
            "pagination": {"it": {"limit": 100, "offset": 0}},
        }

        async with session.post(url, headers=config.REQUEST_HEADERS, json=payload) as response:
            response.raise_for_status()
            result = await response.json()

        vacancies = []
        for item in result.get("payload", {}).get("vacancies", []):
            title = item.get("title", "")
            tags = item.get("tags") or []
            grade = tags[0] if tags else guess_grade_from_title(title)
            city = ", ".join(item.get("cities", [])) or "Не указан"
            short_html = item.get("shortDescription") or ""
            short_description = BeautifulSoup(short_html, "html.parser").get_text(" ", strip=True) or None

            vacancies.append(
                {
                    "id": f"tbank_{item.get('urlSlug')}",
                    "company": "T-Bank",
                    "title": title,
                    "grade": grade,
                    "city": city,
                    "work_format": "Не указан",
                    "experience": "Не указан",
                    "url": f"https://www.tbank.ru/career/{item.get('source')}/{item.get('specialty')}/{item.get('urlSlug')}/",
                    "short_description": short_description,
                    "source_json": item,
                }
            )
        return vacancies
