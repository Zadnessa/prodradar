"""Парсер вакансий Alfa-Bank."""

from parsers.base import BaseParser
import config


class AlfaParser(BaseParser):
    @staticmethod
    def _fallback_city_from_slug(city_mappings, slug):
        parts = [part for part in (slug or "").split("/") if part]
        raw_city = parts[0] if parts else ""
        if not raw_city:
            return "Не указан"
        return city_mappings.get(("alfa_slug", raw_city), raw_city.replace("-", " ").title())

    @staticmethod
    def _extract_option_list(payload, target_id):
        if isinstance(payload, dict):
            if str(payload.get("id")) == str(target_id) or payload.get("code") == target_id or payload.get("listId") == target_id:
                items = payload.get("items") or payload.get("options") or payload.get("values") or payload.get("data") or []
                if isinstance(items, list):
                    return items
            for value in payload.values():
                result = AlfaParser._extract_option_list(value, target_id)
                if result is not None:
                    return result
        elif isinstance(payload, list):
            for value in payload:
                result = AlfaParser._extract_option_list(value, target_id)
                if result is not None:
                    return result
        return None

    @staticmethod
    def _build_option_map(payload, target_id):
        items = AlfaParser._extract_option_list(payload, target_id) or []
        result = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            item_id = item.get("id")
            name = item.get("name") or item.get("title")
            if item_id is not None and name:
                result[str(item_id)] = name
        return result

    async def parse(self, session, existing_ids, city_mappings):
        options_url = "https://job.alfabank.ru/api/optionLists"
        options_params = [("listIds", "archetypes"), ("listIds", "cities")]
        async with session.get(options_url, headers=config.REQUEST_HEADERS, params=options_params) as response:
            response.raise_for_status()
            option_lists = await response.json()

        archetype_map = self._build_option_map(option_lists, "archetypes")
        city_map = self._build_option_map(option_lists, "cities")

        url = "https://job.alfabank.ru/api/vacancies?businessLine=1020&take=100&search=продукт"
        async with session.get(url, headers=config.REQUEST_HEADERS) as response:
            response.raise_for_status()
            payload = await response.json()

        vacancies = []
        for item in payload.get("items", []):
            slug = item.get("slug") or ""
            city = city_map.get(str(item.get("cityId"))) or self._fallback_city_from_slug(city_mappings, slug)
            title = (item.get("name", "") or "").strip()
            description = (item.get("descriptionText") or "").strip()
            canonical_url = f"https://job.alfabank.ru/vacancies{slug}" if slug else f"https://job.alfabank.ru/vacancies/{item.get('id')}"
            vacancies.append(
                {
                    "id": f"alfa_{item.get('id')}",
                    "company": "Альфа-Банк",
                    "title": title,
                    "grade": None,
                    "city": city,
                    "work_format": archetype_map.get(str(item.get("archetypeId")), "Не указан"),
                    "experience": config.ALFA_EXPERIENCE_MAP.get(item.get("experienceId"), "Не указан"),
                    "url": canonical_url,
                    "published_at": item.get("createdAt"),
                    "short_description": description[:500] if description else None,
                    "source_json": item,
                }
            )
        return vacancies
