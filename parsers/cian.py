"""Парсер вакансий Циан."""

import asyncio
import html
import json
import logging
import re

from curl_cffi import requests as curl_requests

import config
from parsers.base import BaseParser
from parsers.utils import normalize_city


logger = logging.getLogger(__name__)


class CianParser(BaseParser):
    """Парсер Циан: список через API, описание через initialState."""

    API_URL = "https://api.cian.ru/job-vacancies-backend/v2/get-vacancies/"

    def __init__(self):
        self._cookie_string = None

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

    async def parse(self, session, existing_ids, city_mappings, browser_secrets=None):
        del existing_ids

        cookies = (browser_secrets or {}).get("cian_cookies") or []
        cian_cookie_pairs = []
        for cookie in cookies:
            if not isinstance(cookie, dict):
                continue
            domain = str(cookie.get("domain") or "")
            if "cian.ru" not in domain:
                continue
            name = str(cookie.get("name") or "").strip()
            value = str(cookie.get("value") or "").strip()
            if not name or not value:
                continue
            cian_cookie_pairs.append(f"{name}={value}")

        if not cian_cookie_pairs:
            raise RuntimeError(
                "Cian parse: отсутствуют cookies из browser_secrets['cian_cookies']; "
                "нужен браузерный этап parsers/browser.py"
            )

        cookie_string = "; ".join(cian_cookie_pairs)
        self._cookie_string = cookie_string
        has_yasc_cookie = any(pair.startswith("_yasc=") for pair in cian_cookie_pairs)
        logger.info("Cian parse: cookies=%s, _yasc=%s", len(cian_cookie_pairs), "да" if has_yasc_cookie else "нет")
        logger.info("Cian parse: cookie names=[%s]", ", ".join(pair.split("=", 1)[0] for pair in cian_cookie_pairs))

        headers = {
            "accept": "*/*",
            "accept-language": "ru-RU,ru;q=0.9",
            "content-type": "application/json",
            "origin": "https://www.cian.ru",
            "referer": "https://www.cian.ru/",
            "cookie": cookie_string,
            "sec-ch-ua": '"Chromium";v="146", "Not_A Brand";v="24", "Google Chrome";v="146"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": config.REQUEST_HEADERS["User-Agent"],
        }
        payload = {"filters": {"specializations": ["58"]}}

        async with session.post(self.API_URL, headers=headers, json=payload, timeout=30) as response:
            response.raise_for_status()

            logger.info(
                "Cian parse: API ответ status=%s, Content-Type=%s",
                response.status,
                response.headers.get("Content-Type"),
            )
            content_type = (response.headers.get("Content-Type") or "").lower()
            if "json" not in content_type:
                raise RuntimeError(
                    "Циан API вернул не JSON: возможна captcha или блокировка "
                    f"(Content-Type={response.headers.get('Content-Type')})"
                )

            data = await response.json()
        vacancies = []
        groups = data.get("groups") or []
        total_vacancies = sum(len((group or {}).get("vacancies") or []) for group in groups)
        logger.info("Cian parse: групп=%s, вакансий=%s", len(groups), total_vacancies)

        for group in groups:
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

        raw_id = str(vacancy.get("id") or "").removeprefix("cian_")
        if not raw_id:
            return vacancy

        try:
            response = await asyncio.to_thread(
                curl_requests.get,
                f"https://www.cian.ru/vacancies/{raw_id}/",
                headers={"user-agent": config.REQUEST_HEADERS["User-Agent"]},
                impersonate="chrome131",
                timeout=30,
            )
            response.raise_for_status()
            html_text = response.text

            if "captcha" in html_text.lower():
                logger.warning("Cian enrich: получена captcha для %s", vacancy.get("id"))
                return vacancy

            state = self._extract_initial_state(html_text)
            contents = state.get("vacancies", {}).get("vacancy", {}).get("contents", [])

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
