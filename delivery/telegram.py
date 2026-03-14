"""Отправка и форматирование сообщений в Telegram."""

import asyncio
import logging
import os

import requests

import config
from delivery.filters import filter_vacancies_for_user


def _escape_html(text):
    if text is None:
        return ""
    escaped = str(text)
    escaped = escaped.replace("&", "&amp;")
    escaped = escaped.replace("<", "&lt;")
    escaped = escaped.replace(">", "&gt;")
    return escaped


def format_vacancy_message(vacancy, company_meta):
    emoji = company_meta.get("emoji", "") if company_meta else ""
    lines = [
        f"{emoji} {vacancy.get('company', 'Компания')}",
        f"<b>{_escape_html(vacancy.get('title', ''))}</b>",
        "",
    ]

    fields = [
        ("грейд", vacancy.get("grade")),
        ("опыт", vacancy.get("experience")),
        ("город", vacancy.get("city")),
        ("формат", vacancy.get("work_format")),
    ]
    for label, value in fields:
        if value and str(value).strip().lower() != "не указан":
            lines.append(f"{label}: {_escape_html(value)}")

    description = vacancy.get("short_description")
    if config.SHOW_DESCRIPTION and description and str(description).strip().lower() != "не указан":
        lines.append(f"описание: {_escape_html(description)}")

    lines.append("")
    url = vacancy.get("url", "")
    lines.append(f'<a href="{url}">Открыть вакансию</a>')
    return "\n".join(lines)


def send_telegram_message(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    response = requests.post(url, json=payload, timeout=20)
    response.raise_for_status()


async def deliver_vacancies(vacancies, users, companies_map, bot_id="main"):
    token = os.getenv(config.BOTS[bot_id]["token_env"], "")
    sent_count = 0
    failed_users = []

    for user in users:
        try:
            filtered = filter_vacancies_for_user(vacancies, user.get("filters") or {})
            for vacancy in filtered:
                message = format_vacancy_message(vacancy, companies_map.get(vacancy.get("company"), {}))
                send_telegram_message(token, user["chat_id"], message)
                sent_count += 1
                await asyncio.sleep(0.05)
        except Exception as exc:
            failed_users.append(f"{user.get('chat_id')}: {exc}")
            logging.exception("Ошибка отправки пользователю %s", user.get("chat_id"))

    return sent_count, failed_users


def send_admin_report(total, new_count, sent_count, users_count, parser_errors):
    admin_chat_id = config.ADMIN_CHAT_ID
    if not admin_chat_id:
        return
    token = os.getenv(config.BOTS["main"]["token_env"], "")
    errors_text = ", ".join(parser_errors) if parser_errors else "нет"

    message = (
        "📊 Vacancy Radar — отчёт\n\n"
        f"Собрано: {total} вакансий\n"
        f"Новых: {new_count}\n"
        f"Отправлено: {sent_count} сообщений на {users_count} подписчиков\n"
        f"Ошибки: {errors_text}"
    )
    send_telegram_message(token, admin_chat_id, message)
