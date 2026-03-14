"""Парсер вакансий T-Bank."""

import asyncio
import logging

from bs4 import BeautifulSoup
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
            title = (item.get("title", "") or "").strip()
            tags = item.get("tags") or []
            grade_priority = {
                "Junior": 1,
                "Middle": 2,
                "Senior": 3,
                "Lead": 4,
            }
            grade_tags = sorted({tag for tag in tags if tag in grade_priority}, key=lambda x: grade_priority[x])
            if len(grade_tags) == 1:
                grade = grade_tags[0]
            elif len(grade_tags) > 1:
                grade = f"{grade_tags[0]}–{grade_tags[-1]}"
            else:
                grade = None
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

    async def enrich(self, session, vacancy):
        should_sleep = False
        try:
            slug = (vacancy.get("id") or "").replace("tbank_", "", 1)
            if not slug:
                return vacancy

            details_url = (
                "https://hrsites-api-vacancies.tbank.ru/vacancies/public/api/platform/v2/getVacancy"
                f"?urlSlug={slug}"
            )
            should_sleep = True
            async with session.get(details_url, headers=config.REQUEST_HEADERS) as response:
                response.raise_for_status()
                payload = await response.json()

            data = payload.get("payload") or payload

            if not vacancy.get("grade"):
                experiences = data.get("experiences") or []
                first_exp = experiences[0] if experiences else {}
                if first_exp.get("name"):
                    vacancy["grade"] = first_exp.get("name")

            if not vacancy.get("short_description"):
                parts = [data.get("tasks"), data.get("requirements")]
                description = "\n\n".join(
                    BeautifulSoup(part, "html.parser").get_text(" ", strip=True)
                    for part in parts
                    if part
                )
                if description:
                    vacancy["short_description"] = description[:500]
        except Exception as exc:
            logging.warning("T-Bank enrich ошибка для %s: %s", vacancy.get("id"), exc)
        finally:
            if should_sleep:
                await asyncio.sleep(0.3)

        return vacancy
