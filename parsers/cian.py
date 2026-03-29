"""Парсер вакансий Циан."""

import asyncio
import html
import json
import logging
import re

import requests

from parsers.base import BaseParser
from parsers.utils import normalize_city


logger = logging.getLogger(__name__)


class CianParser(BaseParser):
    """Парсер Циан: список через API, описание через SSR initialState."""

    API_URL = "https://api.cian.ru/job-vacancies-backend/v2/get-vacancies/"
    ROOT_URL = "https://www.cian.ru/"
    WARMUP_URL = "https://www.cian.ru/vacancies/"

    def __init__(self):
        self._session = None
        self._warmed_up = False

    @staticmethod
    def _is_salary_label(label):
        value = label.strip()
        return bool(re.search(r"₽|\bот\b.+\bдо\b", value, flags=re.IGNORECASE))

    @staticmethod
    def _clean_html_text(text):
        if not text:
            return ""

        prepared = re.sub(r"<\s*br\s*/?\s*>", "\n", text, flags=re.IGNORECASE)
        prepared = re.sub(r"<\s*/\s*(p|li)\s*>", "\n", prepared, flags=re.IGNORECASE)
        prepared = re.sub(r"<\s*(p|li)[^>]*>", "", prepared, flags=re.IGNORECASE)
        prepared = re.sub(r"<[^>]+>", "", prepared)
        prepared = html.unescape(prepared)

        lines = [line.strip() for line in prepared.splitlines()]
        compact = "\n".join(line for line in lines if line)
        return compact.strip()

    @staticmethod
    def _extract_initial_state(html_text):
        marker_index = html_text.find("initialState")
        if marker_index == -1:
            raise ValueError("В HTML не найден initialState")

        value_index = html_text.find('"value":{', marker_index)
        if value_index == -1:
            raise ValueError("В initialState не найден ключ value")

        start = html_text.find("{", value_index)
        if start == -1:
            raise ValueError("Не найдено начало JSON после value")

        depth = 0
        in_string = False
        escaped = False
        for i in range(start, len(html_text)):
            ch = html_text[i]

            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue

            if ch == '"':
                in_string = True
                continue

            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    raw_json = html_text[start : i + 1]
                    return json.loads(raw_json)

        raise ValueError("Не удалось сбалансировать скобки JSON initialState")

    async def _sync_get(self, url, **kwargs):
        return await asyncio.to_thread(self._session.get, url, **kwargs)

    async def _sync_post(self, url, **kwargs):
        return await asyncio.to_thread(self._session.post, url, **kwargs)

    async def parse(self, session, existing_ids, city_mappings):
        del session
        del existing_ids

        self._session = requests.Session()
        self._warmed_up = False

        root_response = await asyncio.to_thread(self._session.get, self.ROOT_URL, timeout=30)
        root_response.raise_for_status()

        headers = {
            "Accept": "*/*",
            "Content-Type": "application/json",
            "Origin": "https://www.cian.ru",
            "Referer": "https://www.cian.ru/",
            "sec-ch-ua": '"Chromium";v="123", "Google Chrome";v="123", "Not:A-Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
        }
        payload = {"filters": {"specializations": ["58"]}}

        response = await self._sync_post(self.API_URL, json=payload, headers=headers, timeout=30)
        response.raise_for_status()

        content_type = (response.headers.get("Content-Type") or "").lower()
        if "json" not in content_type:
            raise RuntimeError(
                "Циан API вернул не JSON: возможна проблема с cookie или captcha "
                f"(Content-Type={response.headers.get('Content-Type')})"
            )

        data = response.json()
        vacancies = []

        for group in data.get("groups") or []:
            group_vacancies = group.get("vacancies") or []
            group_count = group.get("count")
            if isinstance(group_count, int) and group_count != len(group_vacancies):
                logger.warning(
                    "Cian parse: возможная обрезка группы (count=%s, vacancies=%s)",
                    group_count,
                    len(group_vacancies),
                )

            for item in group_vacancies:
                raw_id = item.get("id")
                if raw_id is None:
                    continue

                labels = item.get("labels") or []
                if not isinstance(labels, list):
                    labels = [labels]

                is_remote = False
                city_chunks = []
                for label in labels:
                    label_str = str(label).strip()
                    if not label_str:
                        continue
                    if self._is_salary_label(label_str):
                        continue
                    if re.search(r"удал[её]нно", label_str, flags=re.IGNORECASE):
                        is_remote = True
                        continue
                    city_chunks.append(label_str)

                city_raw = ", ".join(city_chunks)
                vacancies.append(
                    {
                        "id": f"cian_{raw_id}",
                        "company": "Циан",
                        "title": (item.get("name") or "").strip(),
                        "grade": None,
                        "city": normalize_city(city_mappings, city_raw),
                        "work_format": "Удалёнка" if is_remote else "Офис",
                        "url": f"https://www.cian.ru/vacancies/{raw_id}/",
                        "description": None,
                        "experience": None,
                        "published_at": None,
                    }
                )

        return vacancies

    async def enrich(self, session, vacancy):
        del session

        if self._session is None:
            return vacancy

        raw_id = str(vacancy.get("id") or "").removeprefix("cian_")
        if not raw_id:
            return vacancy

        try:
            if not self._warmed_up:
                warmup_response = await self._sync_get(self.WARMUP_URL, timeout=30)
                warmup_response.raise_for_status()
                self._warmed_up = True

            url = f"https://www.cian.ru/vacancies/{raw_id}/"
            response = await self._sync_get(url, timeout=30)
            response.raise_for_status()
            html_text = response.text

            if "captcha" in html_text.lower():
                raise RuntimeError("Cian enrich: получена captcha-страница")

            state = self._extract_initial_state(html_text)
            contents = (
                state.get("vacancies", {})
                .get("vacancy", {})
                .get("contents", [])
            )

            parts = []
            for section in contents:
                title = self._clean_html_text((section or {}).get("title") or "")
                body = self._clean_html_text((section or {}).get("body") or "")
                section_text = "\n".join(chunk for chunk in [title, body] if chunk).strip()
                if section_text:
                    parts.append(section_text)

            new_description = "\n\n".join(parts).strip()
            current_description = vacancy.get("description") or ""
            if new_description and (not current_description or len(new_description) > len(current_description)):
                vacancy["description"] = new_description
        except Exception as exc:
            logger.warning("Cian enrich: не удалось обработать вакансию %s: %s", vacancy.get("id"), exc)
        finally:
            await asyncio.sleep(0.3)

        return vacancy
