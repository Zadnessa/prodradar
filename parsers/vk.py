"""Парсер вакансий VK."""

import asyncio
import re

from bs4 import BeautifulSoup
from parsers.base import BaseParser
from parsers.utils import normalize_city
import config


class VKParser(BaseParser):
    async def parse(self, session, existing_ids, city_mappings):
        url = "https://team.vk.company/career/api/v2/vacancies/?limit=100&tags=2259"
        async with session.get(url, headers=config.REQUEST_HEADERS) as response:
            response.raise_for_status()
            payload = await response.json()

        vacancies = []
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

            if vacancy_id not in existing_ids:
                try:
                    html_url = f"https://team.vk.company/vacancy/{item.get('id')}/"
                    async with session.get(html_url, headers=config.REQUEST_HEADERS) as html_response:
                        html_response.raise_for_status()
                        html = await html_response.text()
                    soup = BeautifulSoup(html, "html.parser")
                    meta = soup.find("meta", attrs={"name": "description"})
                    content = meta.get("content", "") if meta else ""
                    match = re.search(r"уровня\s+([\w,\s]+?)(?:\s+в\s+проект|\s+с\s+графиком)", content, flags=re.IGNORECASE)
                    if match:
                        grade = match.group(1).strip()
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
                    "short_description": None,
                    "source_json": {**item, "group_name": (item.get("group") or {}).get("name")},
                }
            )
        return vacancies
