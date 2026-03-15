"""Бизнес-логика меню настроек без зависимостей от API и БД."""

from copy import deepcopy

from bot.onboarding import get_step_message


PREFIX = "st"
_STEP_TITLES = {
    "grade": "Грейд",
    "city": "Город",
    "work_format": "Формат работы",
    "company": "Компании",
}


def get_settings_menu(user, show_deliver=False):
    user = user or {}
    paused = bool(user.get("paused"))
    filters = user.get("filters") or {}

    grades = filters.get("grades") or []
    cities = filters.get("cities") or []
    work_formats = filters.get("work_formats") or []
    companies = filters.get("companies") or []

    grades_text = ", ".join(grades) if grades else "Все"
    cities_text = ", ".join(cities) if cities else "Все"
    work_formats_text = ", ".join(work_formats) if work_formats else "Все"
    companies_text = ", ".join(companies) if companies else "Все"

    text = (
        "⚙️ Настройки\n\n"
        f"Грейд: {grades_text}\n"
        f"Город: {cities_text}\n"
        f"Формат: {work_formats_text}\n"
        f"Компании: {companies_text}\n\n"
        "Что хочешь изменить?"
    )

    if show_deliver:
        text += (
            "\n\n📬 Фильтры обновлены. Новые вакансии придут в ближайшей рассылке, "
            "или можешь получить подборку прямо сейчас:"
        )

    keyboard = []

    if show_deliver:
        keyboard.append([{"text": "📬 Получить вакансии", "callback_data": "st:deliver"}])

    keyboard.extend(
        [
            [
                {"text": "Грейд", "callback_data": "st:edit:grade"},
                {"text": "Город", "callback_data": "st:edit:city"},
            ],
            [
                {"text": "Формат", "callback_data": "st:edit:wf"},
                {"text": "Компании", "callback_data": "st:edit:company"},
            ],
            [
                {
                    "text": "▶️ Возобновить" if paused else "⏸ Пауза",
                    "callback_data": "st:resume" if paused else "st:pause",
                },
                {"text": "🚫 Отписаться", "callback_data": "st:stop"},
            ],
            [{"text": "◀️ Назад", "callback_data": "st:close"}],
        ]
    )

    return text, {"inline_keyboard": keyboard}


def get_settings_step(step, current_filters, companies_list=None):
    text, reply_markup = get_step_message(
        step,
        current_filters,
        companies_list=companies_list,
        prefix=PREFIX,
    )

    markup = deepcopy(reply_markup or {"inline_keyboard": []})
    rows = markup.get("inline_keyboard", [])
    if rows:
        rows = rows[:-1]

    rows.append(
        [
            {"text": "💾 Сохранить", "callback_data": "st:save"},
            {"text": "◀️ Назад", "callback_data": "st:back"},
        ]
    )
    markup["inline_keyboard"] = rows

    title = _STEP_TITLES.get(step, step)
    settings_text = text
    if "—" in text:
        settings_text = f"⚙️ Настройка: {title}\n\n" + text.split("\n\n", 1)[1]

    return settings_text, markup


def get_pause_message():
    return (
        "Рассылка приостановлена. Настройки сохранены — когда будешь готов,\n"
        "возобнови через /settings.",
        {"inline_keyboard": [[{"text": "◀️ К настройкам", "callback_data": "st:menu"}]]},
    )


def get_resume_message():
    return (
        "Рассылка возобновлена! Новые вакансии придут в ближайшую рассылку.",
        {"inline_keyboard": [[{"text": "◀️ К настройкам", "callback_data": "st:menu"}]]},
    )


def get_stop_confirm():
    return (
        "Ты уверен? Фильтры будут сброшены.",
        {
            "inline_keyboard": [
                [
                    {"text": "Да, отписаться", "callback_data": "st:stop:yes"},
                    {"text": "Отмена", "callback_data": "st:menu"},
                ]
            ]
        },
    )
