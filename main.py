"""Точка входа для запуска сбора вакансий через GitHub Actions."""

import asyncio
import logging

import aiohttp

import config
from database.supabase_client import SupabaseService
from delivery.telegram import deliver_vacancies, send_admin_report
from enrichment.ai_summary import generate_summary
from enrichment.grade_guesser import guess_grade_from_title
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

    async with aiohttp.ClientSession() as session:
        for company in companies:
            parser_name = company.get("parser_name")
            try:
                parser_cls = PARSER_REGISTRY.get(parser_name)
                if not parser_cls:
                    raise ValueError(f"Парсер '{parser_name}' не зарегистрирован")
                parser = parser_cls()
                vacancies = await parser.parse(session, existing_ids, city_mappings)
                if config.TEST_MODE:
                    vacancies = vacancies[: config.TEST_LIMIT]
                all_collected.extend(vacancies)
                logging.info("%s: собрано %s", parser_name, len(vacancies))
            except Exception as exc:
                parser_errors.append(f"{company.get('name')}: {exc}")
                logging.exception("Ошибка парсера %s", parser_name)

    new_vacancies = [v for v in all_collected if v["id"] not in existing_ids]

    for vacancy in new_vacancies:
        vacancy["short_description"] = generate_summary(vacancy)
        vacancy["city"] = _normalize_general_city(city_mappings, vacancy.get("city"))
        if not vacancy.get("grade"):
            vacancy["grade"] = guess_grade_from_title(vacancy.get("title", ""))

    db.save_vacancies(new_vacancies)

    unnotified = db.get_unnotified_vacancies()
    users = db.get_active_users(bot_id="main")
    companies_map = {c.get("name"): c for c in companies}

    sent_count, failed_users = await deliver_vacancies(unnotified, users, companies_map, bot_id="main")
    db.mark_vacancies_notified([v["id"] for v in unnotified])

    send_admin_report(
        total=len(all_collected),
        new_count=len(new_vacancies),
        sent_count=sent_count,
        users_count=len(users),
        parser_errors=parser_errors + failed_users,
    )

    logging.info(
        "Итог: собрано=%s, новые=%s, разослано=%s, подписчики=%s, ошибок=%s",
        len(all_collected),
        len(new_vacancies),
        sent_count,
        len(users),
        len(parser_errors) + len(failed_users),
    )


if __name__ == "__main__":
    asyncio.run(run())
