"""Точка входа для запуска сбора вакансий через GitHub Actions."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import aiohttp

import config
from config import DOMCLICK_TITLE_WHITELIST, HH_TITLE_WHITELIST
from bot.telegram_api import send_message
from database.supabase_client import SupabaseService, compute_content_hash
from delivery.filters import filter_vacancies_for_user
from delivery.telegram import format_vacancy_message, send_admin_report
from enrichment.ai_summary import generate_summary
from enrichment.normalizer import (
    experience_from_grade,
    grade_from_experience,
    normalize_experience,
    normalize_grade,
    normalize_work_format,
)
from parsers import PARSER_REGISTRY
from parsers.browser import fetch_browser_secrets
from parsers.utils import normalize_city


def _prepare_vacancy(vacancy, city_mappings):
    vacancy["city"] = normalize_city(city_mappings, vacancy.get("city"))
    vacancy["experience"] = normalize_experience(vacancy.get("experience"))
    vacancy["work_format"] = normalize_work_format(vacancy.get("work_format"))
    if vacancy.get("grade") is not None:
        vacancy["grade"] = normalize_grade(vacancy.get("grade"))
    if not vacancy.get("grade"):
        vacancy["grade"] = grade_from_experience(vacancy.get("experience", ""))
    elif vacancy.get("experience") == "не указан":
        inferred_experience = experience_from_grade(vacancy.get("grade"))
        if inferred_experience is not None:
            vacancy["experience"] = inferred_experience
    if vacancy.get("city") == "Не указан" and "Удалёнка" in vacancy.get("work_format", ""):
        vacancy["city"] = "Удалёнка"
    if not vacancy.get("description"):
        vacancy["description"] = generate_summary(vacancy)
    return vacancy


async def run():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    db = SupabaseService()
    companies = db.get_enabled_companies()
    city_mappings = db.get_city_mappings()

    try:
        browser_secrets = await fetch_browser_secrets()
    except Exception as exc:
        logging.warning("Браузерный этап не удался: %s", exc)
        browser_secrets = {}

    all_collected = []
    all_collected_ids = set()
    parser_errors = []
    successful_companies = set()
    parsers_by_company = {}
    empty_existing_ids = set()
    unique_parser_names = []
    seen_parser_names = set()

    for company in companies:
        parser_name = company.get("parser_name")
        if not parser_name or parser_name in seen_parser_names:
            continue
        seen_parser_names.add(parser_name)
        unique_parser_names.append(parser_name)

    async with aiohttp.ClientSession() as session:
        for parser_name in unique_parser_names:
            try:
                parser_cls = PARSER_REGISTRY.get(parser_name)
                if not parser_cls:
                    raise ValueError(f"Парсер {parser_name} не найден в PARSER_REGISTRY")
                parser = parser_cls()
                vacancies = await parser.parse(session, empty_existing_ids, city_mappings, browser_secrets=browser_secrets)
                if config.TEST_MODE:
                    vacancies = vacancies[: config.TEST_LIMIT]
                all_collected.extend(vacancies)
                all_collected_ids.update(vacancy["id"] for vacancy in vacancies)
                parser_companies = {vacancy.get("company") for vacancy in vacancies if vacancy.get("company")}
                for vacancy_company in parser_companies:
                    parsers_by_company[vacancy_company] = parser
                successful_companies.update(parser_companies)
                logging.info("%s: собрано %s", parser_name, len(vacancies))
            except Exception as exc:
                parser_errors.append(f"{parser_name}: {exc}")
                logging.exception("Ошибка парсера %s", parser_name)

        before_filter = len(all_collected)
        all_collected = [
            vacancy
            for vacancy in all_collected
            if not any(pattern in vacancy.get("title", "").lower() for pattern in config.TITLE_STOP_PATTERNS)
        ]
        filtered_out = before_filter - len(all_collected)
        if filtered_out:
            logging.info("Отфильтровано по стоп-словам: %s", filtered_out)

        before_sber_whitelist = len(all_collected)
        all_collected = [
            vacancy
            for vacancy in all_collected
            if vacancy.get("company") != "Сбер"
            or any(
                pattern in vacancy.get("title", "").lower()
                for pattern in config.SBER_TITLE_WHITELIST
            )
        ]
        sber_filtered_out = before_sber_whitelist - len(all_collected)
        if sber_filtered_out:
            logging.info("Отфильтровано по Сбер whitelist: %s", sber_filtered_out)

        before_domclick_whitelist = len(all_collected)
        all_collected = [
            vacancy
            for vacancy in all_collected
            if vacancy.get("company") != "ДомКлик"
            or any(
                pattern in vacancy.get("title", "").lower()
                for pattern in DOMCLICK_TITLE_WHITELIST
            )
        ]
        domclick_filtered_out = before_domclick_whitelist - len(all_collected)
        if domclick_filtered_out:
            logging.info("Отфильтровано по ДомКлик whitelist: %s", domclick_filtered_out)

        before_hh_whitelist = len(all_collected)
        all_collected = [
            vacancy
            for vacancy in all_collected
            if vacancy.get("company") != "HeadHunter"
            or vacancy.get("is_product_role") is True
            or any(
                pattern in vacancy.get("title", "").lower()
                for pattern in HH_TITLE_WHITELIST
            )
        ]
        hh_filtered_out = before_hh_whitelist - len(all_collected)
        if hh_filtered_out:
            logging.info("Отфильтровано по HeadHunter двухуровневому фильтру: %s", hh_filtered_out)

        existing_hashes = db.get_existing_vacancy_hashes()
        new_vacancies = []
        changed_vacancies = []
        touch_ids = []

        for vacancy in all_collected:
            vacancy.pop("is_product_role", None)
            vacancy.pop("_source", None)
            content_hash = compute_content_hash(vacancy)
            existing_hash = existing_hashes.get(vacancy["id"])

            if vacancy["id"] in existing_hashes and existing_hash == content_hash:
                touch_ids.append(vacancy["id"])
                continue

            parser = parsers_by_company.get(vacancy.get("company"))
            if parser:
                try:
                    vacancy = await parser.enrich(session, vacancy)
                except Exception as exc:
                    logging.warning("Ошибка enrichment для %s: %s", vacancy.get("id"), exc)

            _prepare_vacancy(vacancy, city_mappings)
            vacancy["content_hash"] = content_hash

            if vacancy["id"] in existing_hashes:
                changed_vacancies.append(vacancy)
            else:
                new_vacancies.append(vacancy)

    db.insert_vacancies(new_vacancies)
    db.touch_vacancies(touch_ids)
    db.update_vacancies(changed_vacancies)

    deactivated_count = db.deactivate_missing_vacancies(
        all_collected_ids,
        companies=sorted(successful_companies),
    )

    unchanged_count = len(touch_ids)
    logging.info(
        "Новых: %s, изменённых: %s, без изменений: %s, деактивировано: %s",
        len(new_vacancies),
        len(changed_vacancies),
        unchanged_count,
        deactivated_count,
    )

    users = db.get_active_users(bot_id="main")
    companies_map = {c.get("name"): c for c in companies}

    sent_count = 0
    failed_users = []
    paused_users = 0

    for user in users:
        if user.get("paused"):
            paused_users += 1
            continue

        chat_id = user.get("chat_id")
        bot_id = user.get("bot_id") or "main"
        try:
            undelivered = db.get_undelivered_vacancies(chat_id, limit=200)
            filtered_vacancies = filter_vacancies_for_user(undelivered, user.get("filters") or {})
            batch = filtered_vacancies[:10]

            if not batch:
                continue

            send_message(chat_id, "Новые вакансии по твоим фильтрам:", bot_id=bot_id)

            delivered_ids = []
            for vacancy in batch:
                message = format_vacancy_message(vacancy, companies_map.get(vacancy.get("company"), {}))
                result = send_message(chat_id, message, bot_id=bot_id)
                if result:
                    delivered_ids.append(vacancy["id"])
                    sent_count += 1

            moscow_now = datetime.now(timezone.utc) + timedelta(hours=3)
            next_check_text = "Следующая проверка вечером." if moscow_now.hour < 15 else "Следующая проверка утром."
            send_message(
                chat_id,
                f"Показано {len(delivered_ids)} вакансий. {next_check_text}\n\nФильтры — /settings",
                bot_id=bot_id,
            )

            db.mark_delivered(chat_id, delivered_ids, source="scheduled")
        except Exception as exc:
            failed_users.append(f"{chat_id}: {exc}")
            logging.exception("Ошибка отправки пользователю %s", chat_id)

    send_admin_report(
        total=len(all_collected),
        new_count=len(new_vacancies),
        changed_count=len(changed_vacancies),
        unchanged_count=unchanged_count,
        deactivated_count=deactivated_count,
        sent_count=sent_count,
        users_count=len(users),
        paused_count=paused_users,
        parser_errors=parser_errors + failed_users,
    )

    logging.info(
        "Итог: собрано=%s, новые=%s, изменённые=%s, без изменений=%s, деактивировано=%s, разослано=%s, подписчики=%s, пауза=%s, ошибок=%s",
        len(all_collected),
        len(new_vacancies),
        len(changed_vacancies),
        unchanged_count,
        deactivated_count,
        sent_count,
        len(users),
        paused_users,
        len(parser_errors) + len(failed_users),
    )


if __name__ == "__main__":
    asyncio.run(run())
