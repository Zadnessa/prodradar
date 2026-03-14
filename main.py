"""Точка входа для запуска сбора вакансий через GitHub Actions."""

import asyncio
import logging

import aiohttp

import config
from bot.telegram_api import send_message
from database.supabase_client import SupabaseService
from delivery.filters import filter_vacancies_for_user
from delivery.telegram import format_vacancy_message, send_admin_report
from enrichment.ai_summary import generate_summary
from enrichment.normalizer import grade_from_experience, normalize_experience
from parsers import PARSER_REGISTRY


def _normalize_general_city(city_mappings, city):
    if not city:
        return "Не указан"
    value = str(city).strip()
    if not value:
        return "Не указан"
    return city_mappings.get(("general", value), value)


async def run():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    db = SupabaseService()
    companies = db.get_enabled_companies()
    existing_ids = db.get_existing_vacancy_ids()
    city_mappings = db.get_city_mappings()

    all_collected = []
    parser_errors = []
    parsers_by_company = {}

    async with aiohttp.ClientSession() as session:
        for company in companies:
            parser_name = company.get("parser_name")
            try:
                parser_cls = PARSER_REGISTRY.get(parser_name)
                if not parser_cls:
                    raise ValueError(f"Парсер {parser_name} не найден в PARSER_REGISTRY")
                parser = parser_cls()
                parsers_by_company[company.get("name")] = parser
                vacancies = await parser.parse(session, existing_ids, city_mappings)
                if config.TEST_MODE:
                    vacancies = vacancies[: config.TEST_LIMIT]
                all_collected.extend(vacancies)
                logging.info("%s: собрано %s", parser_name, len(vacancies))
            except Exception as exc:
                parser_errors.append(f"{company.get('name')}: {exc}")
                logging.exception("Ошибка парсера %s", parser_name)

        before_filter = len(all_collected)
        all_collected = [
            v for v in all_collected
            if not any(pattern in v.get("title", "").lower() for pattern in config.TITLE_STOP_PATTERNS)
        ]
        filtered_out = before_filter - len(all_collected)
        if filtered_out:
            logging.info("Отфильтровано по стоп-словам: %s", filtered_out)

        new_vacancies = [v for v in all_collected if v["id"] not in existing_ids]

        for vacancy in new_vacancies:
            parser = parsers_by_company.get(vacancy.get("company"))
            if parser:
                try:
                    vacancy = await parser.enrich(session, vacancy)
                except Exception as exc:
                    logging.warning("Ошибка enrichment для %s: %s", vacancy.get("id"), exc)

            vacancy["city"] = _normalize_general_city(city_mappings, vacancy.get("city"))
            vacancy["experience"] = normalize_experience(vacancy.get("experience"))
            if not vacancy.get("grade"):
                vacancy["grade"] = grade_from_experience(vacancy.get("experience", ""))
            if not vacancy.get("short_description"):
                vacancy["short_description"] = generate_summary(vacancy)

    db.save_vacancies(new_vacancies)

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
        try:
            undelivered = db.get_undelivered_vacancies(chat_id)
            filtered_vacancies = filter_vacancies_for_user(undelivered, user.get("filters") or {})

            delivered_ids = []
            for vacancy in filtered_vacancies:
                message = format_vacancy_message(vacancy, companies_map.get(vacancy.get("company"), {}))
                result = send_message(chat_id, message, bot_id=user.get("bot_id") or "main")
                if result:
                    delivered_ids.append(vacancy["id"])
                    sent_count += 1
                await asyncio.sleep(0.05)

            db.mark_delivered(chat_id, delivered_ids, source="scheduled")
        except Exception as exc:
            failed_users.append(f"{chat_id}: {exc}")
            logging.exception("Ошибка отправки пользователю %s", chat_id)

    send_admin_report(
        total=len(all_collected),
        new_count=len(new_vacancies),
        sent_count=sent_count,
        users_count=len(users),
        paused_count=paused_users,
        parser_errors=parser_errors + failed_users,
    )

    logging.info(
        "Итог: собрано=%s, новые=%s, разослано=%s, подписчики=%s, пауза=%s, ошибок=%s",
        len(all_collected),
        len(new_vacancies),
        sent_count,
        len(users),
        paused_users,
        len(parser_errors) + len(failed_users),
    )


if __name__ == "__main__":
    asyncio.run(run())
