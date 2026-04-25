"""Отправка и форматирование сообщений в Telegram."""
from datetime import datetime, timezone
import logging
import os
import re
import urllib.parse

import config
from bot.telegram_api import send_message


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


def format_company_emoji(company_meta):
    if company_meta is None:
        return ""

    fallback_emoji = company_meta.get("emoji") or "🏢"
    custom_emoji_id = company_meta.get("custom_emoji_id")

    if isinstance(custom_emoji_id, str):
        custom_emoji_id = custom_emoji_id.strip()

    if custom_emoji_id:
        return f'<tg-emoji emoji-id="{custom_emoji_id}">{fallback_emoji}</tg-emoji>'

    return fallback_emoji


def build_redirect_url(vacancy, company_meta, chat_id, source):
    _ = company_meta
    try:
        vercel_url = (os.getenv("REDIRECT_BASE_URL") or "").strip()
        original_url = vacancy.get("url", "")        
        logging.info("REDIRECT_BASE_URL=%s, original_url=%s, chat_id=%s", vercel_url, original_url, chat_id)
        if not vercel_url:
            return original_url

        base_url = f"https://{vercel_url}/api/go"
        params = {
            "url": original_url,
            "vacancy_id": vacancy.get("id", ""),
            "chat_id": str(chat_id),
            "source": source,
            "company": vacancy.get("company", ""),
            "grade": vacancy.get("grade", ""),
            "title_confidence": vacancy.get("title_confidence", ""),
            "city": vacancy.get("city", ""),
            "work_format": vacancy.get("work_format", ""),
        }
        return f"{base_url}?{urllib.parse.urlencode(params)}"
    except Exception:
        logging.warning("Не удалось собрать redirect URL для вакансии", exc_info=True)
        return vacancy.get("url", "")


def _format_published_at_label(vacancy):
    published_at = vacancy.get("published_at")
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


def format_vacancy_message(vacancy, company_meta, chat_id=None, source="on_demand"):
    emoji = format_company_emoji(company_meta)
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

    description = vacancy.get("description")
    if config.SHOW_DESCRIPTION and description and str(description).strip().lower() != "не указан":
        lines.append(f"описание: {_escape_html(description)}")

    lines.append("")
    url = vacancy.get("url", "")
    if chat_id is not None:
        url = build_redirect_url(vacancy, company_meta, chat_id, source)
    lines.append(f'<a href="{url}">Открыть вакансию</a>')
    slug = (company_meta or {}).get("slug")
    if slug:
        company_name = vacancy.get("company", "компании")
        lines.append("")
        lines.append(f"/mute_{slug} — не получать вакансии от {company_name}")
    return "\n".join(lines)


_ERROR_TAG_MAP = {
    "[BLOCKED]": "заблокирован источником",
    "[TIMEOUT]": "таймаут соединения",
    "[NOT_JSON]": "битый ответ (не JSON)",
    "[HTTP_401]": "401 ошибка авторизации",
    "[HTTP_403]": "403 доступ запрещён",
    "[HTTP_404]": "404 эндпоинт не найден",
    "[HTTP_429]": "429 слишком много запросов",
    "[HTTP_500]": "500 ошибка сервера",
    "[HTTP_502]": "502 bad gateway",
    "[HTTP_503]": "503 сервис недоступен",
    "[VALUE_ERROR]": "ошибка данных",
    "[ERROR]": "неизвестная ошибка",
}


def _format_parser_error(error):
    parts = error.split(" ", 1)
    parser_name = parts[0].rstrip(":")
    description = parts[1] if len(parts) > 1 else error

    for tag, readable in _ERROR_TAG_MAP.items():
        if tag in description:
            description = description.replace(tag, readable, 1)
            break
    else:
        http_match = re.search(r'\[HTTP_(\d+)\]', description)
        if http_match:
            code = http_match.group(1)
            description = description.replace(f"[HTTP_{code}]", f"HTTP {code}", 1)

    if len(description) > 100:
        description = description[:97] + "..."

    return f"<b>{_escape_html(parser_name)}:</b> {_escape_html(description)}"


def send_admin_report(
    new_count,
    deactivated_count,
    sent_count,
    users_count,
    parser_errors,
    paused_count=0,
    total_active=0,
    blocked_users=0,
    rate_limited_users=0,
    skipped_onboarding=0,
):
    admin_chat_id = config.ADMIN_CHAT_ID
    if not admin_chat_id:
        return

    total_eligible = users_count - skipped_onboarding
    delivery_target = total_eligible - paused_count

    lines = [
        "📊 <b>Vacancy Radar</b>",
        "",
        f"<b>Вакансий:</b> {total_active} активных, +{new_count} новых, -{deactivated_count} снято",
        f"<b>Подписчиков:</b> {total_eligible} <i>({delivery_target} получают, {paused_count} на паузе)</i>",
    ]

    delivery_line = f"<b>Доставка:</b> {sent_count} сообщений"
    if blocked_users == 0 and rate_limited_users == 0:
        delivery_line += " ✓"
    lines.append(delivery_line)

    if blocked_users > 0:
        lines.append(f"🚫 {blocked_users} заблокировали бота (деактивированы)")
    if rate_limited_users > 0:
        lines.append(f"⏳ {rate_limited_users} пропущены (rate limit)")

    lines.append("")

    clean_errors = [str(e) for e in (parser_errors or []) if e]
    if clean_errors:
        lines.append("<b>Проблемы сбора:</b>")
        for error in clean_errors:
            lines.append(_format_parser_error(error))

    message = "\n".join(lines)

    if len(message) > 4000:
        message = message[:4000]

    send_message(admin_chat_id, message)
