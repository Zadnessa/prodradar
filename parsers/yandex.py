"""Парсер вакансий Yandex."""

from enrichment.grade_guesser import guess_grade_from_title
from parsers.base import BaseParser
import config


class YandexParser(BaseParser):
    BASE_URL = "https://yandex.ru/jobs/api/publications?public_professions=product-manager&page_size=100"
    PRO_LEVELS = {
        "intern": {"grade": "Junior", "experience": "Без опыта"},
        "junior": {"grade": "Junior", "experience": "1-3 лет"},
        "middle": {"grade": "Middle", "experience": "3-5 лет"},
        "senior": {"grade": "Senior", "experience": "5+ лет"},
    }
    GRADE_PRIORITY = {"Junior": 1, "Middle": 2, "Senior": 3}

    async def _fetch_results(self, session, url):
        async with session.get(url, headers=config.REQUEST_HEADERS) as response:
            response.raise_for_status()
            payload = await response.json()
        return payload.get("results", [])

    def _build_vacancy(self, item, grade, experience):
        vacancy = item.get("vacancy", {})
        cities = ", ".join(c.get("name", "") for c in vacancy.get("cities", []) if c.get("name")) or "Не указан"
        work_modes = ", ".join(m.get("name", "") for m in vacancy.get("work_modes", []) if m.get("name")) or "Не указан"
        title = (item.get("title", "") or "").strip()
        return {
            "id": f"ya_{item.get('id')}",
            "company": "Yandex",
            "title": title,
            "grade": grade,
            "city": cities,
            "work_format": work_modes,
            "experience": experience,
            "url": f"https://yandex.ru/jobs/vacancies/{item.get('publication_slug_url')}",
            "short_description": item.get("short_summary") or None,
            "source_json": {
                **item,
                "public_service_name": (item.get("public_service") or {}).get("name"),
            },
        }

    async def parse(self, session, existing_ids, city_mappings):
        vacancies_by_id = {}

        for pro_level, grade_data in self.PRO_LEVELS.items():
            url = f"{self.BASE_URL}&pro_levels={pro_level}"
            for item in await self._fetch_results(session, url):
                vacancy_data = self._build_vacancy(item, grade_data["grade"], grade_data["experience"])
                vacancy_id = vacancy_data["id"]
                current = vacancies_by_id.get(vacancy_id)
                if not current:
                    vacancies_by_id[vacancy_id] = vacancy_data
                    continue

                current_priority = self.GRADE_PRIORITY.get(current.get("grade"), 0)
                new_priority = self.GRADE_PRIORITY.get(vacancy_data.get("grade"), 0)
                if new_priority > current_priority:
                    vacancies_by_id[vacancy_id] = vacancy_data

        for item in await self._fetch_results(session, self.BASE_URL):
            vacancy_id = f"ya_{item.get('id')}"
            if vacancy_id in vacancies_by_id:
                continue
            title = (item.get("title", "") or "").strip()
            grade = guess_grade_from_title(title)
            vacancies_by_id[vacancy_id] = self._build_vacancy(item, grade, "Не указан")

        return list(vacancies_by_id.values())
