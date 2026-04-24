"""Точка входа для запуска сбора вакансий через GitHub Actions."""

import asyncio
import json
import logging
import random
import re
from datetime import datetime, timedelta, timezone

import aiohttp

import config
from config import GRADE_OVERRIDE_PATTERNS, HH_ACCESS_TOKEN, TITLE_BLACKLIST_PATTERNS, TITLE_PREFILTER_REJECT
from bot.telegram_api import send_message
from database.supabase_client import SupabaseService, compute_content_hash
from delivery.filters import filter_vacancies_for_user
from delivery.ranking import classify_title, rank_vacancies
from delivery.telegram import format_vacancy_message, send_admin_report
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


HH_PARSER_NAMES = {"hh", "hh_cian", "hh_kaspersky", "hh_zvuk"}


def _build_grade_distribution(vacancies):
    distribution = {}
    for vacancy in vacancies:
        grade = vacancy.get("grade") or "null"
        distribution[grade] = distribution.get(grade, 0) + 1
    return distribution


def _has_active_core_filters(filters):
    filters = filters or {}
    return any(bool(filters.get(key)) for key in ("grades", "cities", "work_formats"))


def _classify_parser_error(parser_name: str, exc: Exception) -> str:
    tag = "[ERROR]"

    if isinstance(exc, aiohttp.ClientResponseError):
        if exc.status in (403, 429):
            tag = "[BLOCKED]"
        else:
            tag = f"[HTTP_{exc.status}]"
    elif isinstance(exc, (asyncio.TimeoutError, aiohttp.ServerTimeoutError)):
        tag = "[TIMEOUT]"
    elif isinstance(exc, json.JSONDecodeError):
        tag = "[NOT_JSON]"
    elif isinstance(exc, ValueError):
        tag = "[VALUE_ERROR]"

    short_error = str(exc).strip()
    if len(short_error) > 120:
        short_error = f"{short_error[:117]}..."
    if not short_error:
        short_error = "без деталей"

    return f"{parser_name} {tag}: {short_error}"


def _diagnose_blacklist(title: str) -> str | None:
    t = title.strip().lower()
    for pattern in TITLE_BLACKLIST_PATTERNS:
        if pattern in t:
            return pattern
    return None


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
    title_lower = vacancy.get("title", "").strip().lower()
    for pattern, override_grade in GRADE_OVERRIDE_PATTERNS:
        if re.search(pattern, title_lower):
            vacancy["grade"] = override_grade
            break
    if vacancy.get("city") == "Не указан" and "Удалёнка" in vacancy.get("work_format", ""):
        vacancy["city"] = "Удалёнка"
    return vacancy


async def run():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    db = SupabaseService()
    companies = db.get_enabled_companies()
    city_mappings = db.get_city_mappings()

    try:
        browser_secrets = await fetch_browser_secrets()
    except Exception as exc:
        logging.warning("Браузерный этап не удался: %s", exc)
        browser_secrets = {}
    expected_browser_secrets_keys = ("sberhealth_build_id",)
    browser_secrets_parts = []
    for key in expected_browser_secrets_keys:
        value = browser_secrets.get(key)
        if isinstance(value, list):
            browser_secrets_parts.append(f"{key}={len(value)} шт")
        elif value is None:
            browser_secrets_parts.append(f"{key}=None")
        else:
            browser_secrets_parts.append(f"{key}={value}")
    logging.info("browser_secrets: %s", ", ".join(browser_secrets_parts) if browser_secrets_parts else "None")

    all_collected = []
    all_collected_ids = set()
    parser_errors = []
    successful_companies = set()
    parsers_by_company = {}
    empty_existing_ids = set()
    unique_parser_names = []
    seen_parser_names = set()
    parser_stats = {}

    for company in companies:
        parser_name = company.get("parser_name")
        if not parser_name or parser_name in seen_parser_names:
            continue
        seen_parser_names.add(parser_name)
        unique_parser_names.append(parser_name)

    if any(name in HH_PARSER_NAMES for name in unique_parser_names) and not HH_ACCESS_TOKEN:
        logging.warning("HH_ACCESS_TOKEN не задан — HH-парсеры могут вернуть 403")

    hh_names = [name for name in unique_parser_names if name in HH_PARSER_NAMES]
    other_names = [name for name in unique_parser_names if name not in HH_PARSER_NAMES]
    random.shuffle(hh_names)
    ordered_parser_names = other_names + hh_names

    async with aiohttp.ClientSession() as session:
        hh_captcha_detected = False

        for index, parser_name in enumerate(ordered_parser_names):
            if hh_captcha_detected and parser_name in HH_PARSER_NAMES:
                skipped_message = f"{parser_name} [SKIPPED]: captcha на предыдущем HH-парсере"
                parser_errors.append(skipped_message[:150])
                parser_stats[parser_name] = skipped_message.replace(f"{parser_name} ", "", 1)
                continue

            parser = None
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
                parser_stats[parser_name] = len(vacancies)
                if not vacancies and parser_name in HH_PARSER_NAMES:
                    error_msg = f"{parser_name}: 0 вакансий (возможно 403)"
                    parser_errors.append(error_msg[:150])
                    parser_stats[parser_name] = "0 вакансий (возможно 403)"
                parser_companies = {vacancy.get("company") for vacancy in vacancies if vacancy.get("company")}
                for vacancy_company in parser_companies:
                    parsers_by_company[vacancy_company] = parser
                successful_companies.update(parser_companies)
                logging.info("%s: собрано %s", parser_name, len(vacancies))

                if parser_name in HH_PARSER_NAMES and getattr(parser, "captcha_hit", False):
                    hh_captcha_detected = True
                    logging.warning("HH captcha detected, пропускаем оставшиеся HH-парсеры")
            except Exception as exc:
                classified_error = _classify_parser_error(parser_name, exc)
                parser_errors.append(classified_error[:150])
                parser_stats[parser_name] = classified_error.replace(f"{parser_name} ", "", 1)
                logging.error("Ошибка парсера %s: %s", parser_name, str(exc)[:500])

            next_parser_name = ordered_parser_names[index + 1] if index + 1 < len(ordered_parser_names) else None
            if (
                parser_name in HH_PARSER_NAMES
                and next_parser_name in HH_PARSER_NAMES
                and not hh_captcha_detected
            ):
                await asyncio.sleep(random.uniform(2.0, 4.0))

        before_filter = len(all_collected)
        filtered = []
        blacklist_hits = 0
        prefilter_rejected = 0
        exact_hits = 0
        regex_hits = 0
        grey_hits = 0
        regex_blacklist_rejected = 0
        grey_blacklist_rejected = 0
        for vacancy in all_collected:
            zone = classify_title(vacancy["title"])
            if zone is None:
                title_normalized = vacancy["title"].strip().lower()
                if any(pattern in title_normalized for pattern in TITLE_PREFILTER_REJECT):
                    prefilter_rejected += 1
                    logging.debug("Отфильтровано (pre-filter): %s", vacancy["title"])
                    continue

                blacklist_pattern = _diagnose_blacklist(vacancy["title"])
                if blacklist_pattern:
                    blacklist_hits += 1
                    logging.debug("Отфильтровано (blacklist '%s'): %s", blacklist_pattern, vacancy["title"])
                else:
                    logging.debug("Отфильтровано (не прошло whitelist): %s", vacancy["title"])
                continue

            if zone == "exact":
                exact_hits += 1
                filtered.append(vacancy)
                continue

            blacklist_pattern = _diagnose_blacklist(vacancy["title"])
            if blacklist_pattern:
                blacklist_hits += 1
                if zone == "regex":
                    regex_blacklist_rejected += 1
                elif zone == "grey":
                    grey_blacklist_rejected += 1
                logging.debug("Отфильтровано (blacklist '%s'): %s", blacklist_pattern, vacancy["title"])
            else:
                if zone == "regex":
                    regex_hits += 1
                elif zone == "grey":
                    grey_hits += 1
                filtered.append(vacancy)
        all_collected = filtered
        logging.info(
            "Фильтрация заголовков: %s -> %s (отсеяно %s, из них blacklist: %s)",
            before_filter,
            len(all_collected),
            before_filter - len(all_collected),
            blacklist_hits,
        )
        logging.info(
            "Зоны: exact=%s, regex=%s, grey=%s, отсеяно regex+blacklist=%s, отсеяно grey+blacklist=%s",
            exact_hits,
            regex_hits,
            grey_hits,
            regex_blacklist_rejected,
            grey_blacklist_rejected,
        )

        logging.info("Pre-filter отсёк: %s", prefilter_rejected)

        existing_hashes = db.get_existing_vacancy_hashes()
        new_vacancies = []
        changed_vacancies = []
        touch_ids = []
        skipped_count = 0

        for vacancy in all_collected:
            try:
                content_hash = compute_content_hash(vacancy)
                existing_hash = existing_hashes.get(vacancy["id"])

                if vacancy["id"] in existing_hashes and existing_hash == content_hash:
                    touch_ids.append(vacancy["id"])
                    continue

                parser = parsers_by_company.get(vacancy.get("company"))
                if parser:
                    vacancy = await parser.enrich(session, vacancy)

                _prepare_vacancy(vacancy, city_mappings)
                vacancy["content_hash"] = content_hash

                if vacancy["id"] in existing_hashes:
                    changed_vacancies.append(vacancy)
                else:
                    new_vacancies.append(vacancy)
            except Exception as exc:
                skipped_count += 1
                logging.warning("Пропущена битая вакансия %s: %s", vacancy.get("id"), exc)
                continue

    unchanged_count = 0
    deactivated_count = 0
    users = []
    sent_count = 0
    failed_users = []
    paused_users = 0
    skipped_onboarding = 0

    try:
        try:
            db.insert_vacancies(new_vacancies)
        except Exception as exc:
            logging.exception("Ошибка DB insert_vacancies")
            parser_errors.append(f"DB insert_vacancies: {exc}")

        try:
            db.touch_vacancies(touch_ids)
        except Exception as exc:
            logging.exception("Ошибка DB touch_vacancies")
            parser_errors.append(f"DB touch_vacancies: {exc}")

        try:
            db.update_vacancies(changed_vacancies)
        except Exception as exc:
            logging.exception("Ошибка DB update_vacancies")
            parser_errors.append(f"DB update_vacancies: {exc}")

        try:
            deactivated_count = db.deactivate_missing_vacancies(
                all_collected_ids,
                companies=sorted(successful_companies),
            )
        except Exception as exc:
            logging.exception("Ошибка DB deactivate_missing_vacancies")
            parser_errors.append(f"DB deactivate_missing_vacancies: {exc}")

        unchanged_count = len(touch_ids)
        logging.info(
            "Новых: %s, изменённых: %s, без изменений: %s, деактивировано: %s, пропущено битых: %s",
            len(new_vacancies),
            len(changed_vacancies),
            unchanged_count,
            deactivated_count,
            skipped_count,
        )

        users = db.get_active_users(bot_id="main")
        companies_map = {c.get("name"): c for c in companies}

        for user in users:
            if user.get("paused"):
                paused_users += 1
                continue

            chat_id = user.get("chat_id")
            bot_id = user.get("bot_id") or "main"

            user_detail = db.get_user(chat_id)
            if (user_detail or {}).get("onboarding_step") is not None:
                skipped_onboarding += 1
                continue

            try:
                undelivered = db.get_undelivered_vacancies(chat_id, limit=200)
                user_filters = user.get("filters") or {}
                user_grades = user_filters.get("grades") or []
                filtered_vacancies = filter_vacancies_for_user(undelivered, user_filters)
                filtered_vacancies = rank_vacancies(filtered_vacancies, user_grades)
                db.log_event(
                    chat_id,
                    "vacancy_summary_shown",
                    {
                        "total": len(filtered_vacancies),
                        "companies_count": len(
                            {vacancy.get("company") for vacancy in filtered_vacancies if vacancy.get("company")}
                        ),
                        "source": "scheduled",
                        "scarcity": len(filtered_vacancies) <= 5,
                        "grade_distribution": _build_grade_distribution(filtered_vacancies),
                    },
                )
                announced_ids = db.get_announced_vacancy_ids(chat_id)
                announced_count = sum(1 for vacancy in filtered_vacancies if vacancy["id"] in announced_ids)
                new_count = len(filtered_vacancies) - announced_count
                batch = filtered_vacancies[:10]

                if not batch:
                    db.log_event(chat_id, "scheduled_delivery_empty", {"announced_available": announced_count > 0})
                    continue

                if new_count > 0 and announced_count > 0:
                    intro_text = f"{new_count} новых вакансий. Ещё {announced_count} из прошлого выпуска."
                elif new_count > 0:
                    if _has_active_core_filters(user.get("filters")):
                        intro_text = f"{new_count} новых вакансий по твоим фильтрам."
                    else:
                        intro_text = f"{new_count} новых вакансий."
                else:
                    intro_text = f"Новых вакансий пока нет. {announced_count} из прошлого выпуска всё ещё доступны."
                    send_message(chat_id, intro_text, bot_id=bot_id)
                    continue

                send_message(chat_id, intro_text, bot_id=bot_id)

                delivered_ids = []
                for vacancy in batch:
                    message = format_vacancy_message(
                        vacancy,
                        companies_map.get(vacancy.get("company"), {}),
                        chat_id=chat_id,
                        source="scheduled",
                    )
                    result = send_message(chat_id, message, bot_id=bot_id)
                    if result:
                        delivered_ids.append(vacancy["id"])
                        sent_count += 1

                moscow_now = datetime.now(timezone.utc) + timedelta(hours=3)
                next_check_text = "Следующая проверка вечером." if moscow_now.hour < 15 else "Следующая проверка утром."
                remaining = len(filtered_vacancies) - len(delivered_ids)
                reply_markup = None
                if remaining > 0:
                    reply_markup = {
                        "inline_keyboard": [
                            [
                                {"text": "📬 Ещё 10", "callback_data": f"more:{len(delivered_ids)}"},
                                {"text": "✕ Хватит", "callback_data": "more:stop"},
                            ]
                        ]
                    }
                db.mark_delivered(chat_id, delivered_ids, source="scheduled")
                db.log_event(
                    chat_id,
                    "scheduled_delivery_sent",
                    {
                        "new_count": new_count,
                        "announced_count": announced_count,
                        "delivered_count": len(delivered_ids),
                        "remaining": remaining,
                        "has_more_button": remaining > 0,
                    },
                )
                send_message(
                    chat_id,
                    f"Показано {len(delivered_ids)} вакансий. {next_check_text}\n\nФильтры — /settings",
                    bot_id=bot_id,
                    reply_markup=reply_markup,
                )
            except Exception as exc:
                failed_users.append(f"{chat_id}: {str(exc)[:200]}")
                logging.error("Ошибка отправки пользователю %s: %s", chat_id, str(exc)[:500])
    finally:
        parser_stats["skipped_onboarding"] = skipped_onboarding
        send_admin_report(
            total=len(all_collected),
            new_count=len(new_vacancies),
            changed_count=len(changed_vacancies),
            unchanged_count=unchanged_count,
            deactivated_count=deactivated_count,
            skipped_count=skipped_count,
            sent_count=sent_count,
            users_count=len(users),
            paused_count=paused_users,
            parser_stats=parser_stats,
            parser_errors=[error[:150] for error in parser_errors + failed_users],
        )

    logging.info(
        "Итог: собрано=%s, новые=%s, изменённые=%s, без изменений=%s, деактивировано=%s, пропущено битых=%s, разослано=%s, подписчики=%s, пауза=%s, пропущено онбординг=%s, ошибок=%s",
        len(all_collected),
        len(new_vacancies),
        len(changed_vacancies),
        unchanged_count,
        deactivated_count,
        skipped_count,
        sent_count,
        len(users),
        paused_users,
        skipped_onboarding,
        len(parser_errors) + len(failed_users),
    )


if __name__ == "__main__":
    asyncio.run(run())
