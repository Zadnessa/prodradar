"""Отправка и форматирование сообщений в Telegram."""

import asyncio
from datetime import datetime, timezone

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


def _is_empty_field(value):
    return not value or str(value).strip().lower() == "не указан"


def _parse_vacancy_datetime(value):
    if not value:
        return None

    value_str = str(value).strip()
    if not value_str:
        return None

    normalized_value = value_str.replace("Z", "+00:00")

    try:
        parsed = datetime.fromisoformat(normalized_value)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def _format_published_at_label(vacancy):
    published_at = vacancy.get("published_at") or vacancy.get("created_at")
    published_datetime = _parse_vacancy_datetime(published_at)
    if not published_datetime:
        return None

    today_utc = datetime.now(timezone.utc).date()
    published_date = published_datetime.date()
    days_ago = max((today_utc - published_date).days, 0)

    if days_ago == 0:
        return "сегодня"
    if days_ago == 1:
        return "вчера"
    if days_ago > 30:
        return "больше месяца назад"

    last_two_digits = days_ago % 100
    last_digit = days_ago % 10
    if 11 <= last_two_digits <= 14:
        suffix = "дней"
    elif last_digit == 1:
        suffix = "день"
    elif 2 <= last_digit <= 4:
        suffix = "дня"
    else:
        suffix = "дней"

    return f"{days_ago} {suffix} назад"


def format_vacancy_message(vacancy, company_meta):
    emoji = company_meta.get("emoji", "") if company_meta else ""
    lines = [
        f"{emoji} {vacancy.get('company', 'Компания')}",
        f"<b>{_escape_html(vacancy.get('title', ''))}</b>",
        "",
    ]

    grade = vacancy.get("grade")
    if _is_empty_field(grade):
        lines.append("<b>грейд:</b> <i>не указан компанией</i>")
    else:
        lines.append(f"<b>грейд:</b> {_escape_html(grade)}")

    experience = vacancy.get("experience")
    if not _is_empty_field(experience):
        lines.append(f"<b>опыт:</b> {_escape_html(experience)}")

    city = vacancy.get("city")
    if not _is_empty_field(city):
        lines.append(f"<b>город:</b> {_escape_html(city)}")

    work_format = vacancy.get("work_format")
    if _is_empty_field(work_format):
        lines.append("<b>формат:</b> <i>не указан компанией</i>")
    else:
        lines.append(f"<b>формат:</b> {_escape_html(work_format)}")

    published_at_label = _format_published_at_label(vacancy)
    if published_at_label:
        lines.append(f"<b>опубликовано:</b> {published_at_label}")

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
