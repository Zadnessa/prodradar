"""Отправка и форматирование сообщений в Telegram."""

import asyncio
import html
import logging
import os

import requests

import config
from delivery.filters import filter_vacancies_for_user


def _escape_html(text):
    if text is None:
        return ""
    return html.escape(str(text), quote=True)


def _is_present(value):
    return value not in (None, "", "Не указан")


def format_vacancy_message(vacancy, company_meta):
    emoji = company_meta.get("emoji", "") if company_meta else ""
    company = _escape_html(vacancy.get("company", "Компания"))

    lines = [
        f"{emoji} Новая вакансия в {company}",
        "",
    ]

    if _is_present(vacancy.get("title")):
        lines.append(f"<b>Позиция:</b> {_escape_html(vacancy.get('title'))}")
    if _is_present(vacancy.get("city")):
        lines.append(f"<b>Город:</b> {_escape_html(vacancy.get('city'))}")
    if _is_present(vacancy.get("experience")):
        lines.append(f"<b>Опыт:</b> {_escape_html(vacancy.get('experience'))}")
    if _is_present(vacancy.get("grade")):
        lines.append(f"<b>Грейд:</b> {_escape_html(vacancy.get('grade'))}")
    if _is_present(vacancy.get("work_format")):
        lines.append(f"<b>Формат:</b> {_escape_html(vacancy.get('work_format'))}")

    description = vacancy.get("short_description")
    if config.SHOW_DESCRIPTION and _is_present(description):
        lines.append(f"<b>Описание:</b> {_escape_html(description)}")

    url = _escape_html(vacancy.get("url", ""))
    lines.append("")
    lines.append(f'<a href="{url}">Посмотреть вакансию</a>')
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
    send_telegram_message(token, admin_chat_id, _escape_html(message))
