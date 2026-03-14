"""Отправка и форматирование сообщений в Telegram."""

import asyncio

import config
from bot.telegram_api import send_message
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
            lines.append(f"<b>{label}:</b> {_escape_html(value)}")

    description = vacancy.get("short_description")
    if config.SHOW_DESCRIPTION and description and str(description).strip().lower() != "не указан":
        lines.append(f"описание: {_escape_html(description)}")

    lines.append("")
    url = vacancy.get("url", "")
    lines.append(f'<a href="{url}">Открыть вакансию</a>')
    return "\n".join(lines)


def send_telegram_message(token, chat_id, text):
    del token
    return send_message(chat_id, text)


async def deliver_vacancies(vacancies, users, companies_map, bot_id="main"):
    del bot_id
    sent_count = 0
    failed_users = []

    for user in users:
        try:
            filtered = filter_vacancies_for_user(vacancies, user.get("filters") or {})
            for vacancy in filtered:
                message = format_vacancy_message(vacancy, companies_map.get(vacancy.get("company"), {}))
                result = send_message(user["chat_id"], message, bot_id=user.get("bot_id") or "main")
                if result:
                    sent_count += 1
                await asyncio.sleep(0.05)
        except Exception as exc:
            failed_users.append(f"{user.get('chat_id')}: {exc}")

    return sent_count, failed_users


def send_admin_report(total, new_count, sent_count, users_count, parser_errors, paused_count=0):
    admin_chat_id = config.ADMIN_CHAT_ID
    if not admin_chat_id:
        return

    errors_text = ", ".join(parser_errors) if parser_errors else "нет"

    message = (
        "📊 Vacancy Radar — отчёт\n\n"
        f"Собрано: {total} вакансий\n"
        f"Новых: {new_count}\n"
        f"Отправлено: {sent_count} сообщений на {users_count} подписчиков\n"
        f"На паузе: {paused_count}\n"
        f"Ошибки: {errors_text}"
    )
    send_message(admin_chat_id, message)
