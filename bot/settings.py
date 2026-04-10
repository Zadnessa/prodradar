"""Бизнес-логика меню настроек без зависимостей от API и БД."""

from copy import deepcopy

from bot.onboarding import get_company_page, get_step_message


PREFIX = "st"
_STEP_TITLES = {
    "grade": "Грейд",
    "city": "Город",
    "work_format": "Формат работы",
    "company": "Компании",
}


def get_settings_menu(user):
    user = user or {}
    paused = bool(user.get("paused"))
    filters = user.get("filters") or {}

    grades = filters.get("grades") or []
    cities = filters.get("cities") or []
    work_formats = filters.get("work_formats") or []
    excluded_companies = [str(v).strip() for v in (filters.get("excluded_companies") or []) if str(v).strip()]

    grades_text = ", ".join(grades) if grades else "Все"
    cities_text = ", ".join(cities) if cities else "Любой"
    work_formats_text = ", ".join(work_formats) if work_formats else "Все"
    blocked_summary = ""
    if excluded_companies:
        if len(excluded_companies) <= 3:
            blocked_list = ", ".join(excluded_companies)
        else:
            blocked_list = f"{', '.join(excluded_companies[:3])} и ещё {len(excluded_companies) - 3}"
        blocked_summary = f"Заблокировано: {blocked_list}\n"

    text = (
        "⚙️ Настройки\n\n"
        f"Грейд: {grades_text}\n"
        f"Город: {cities_text}\n"
        f"Формат: {work_formats_text}\n"
        f"{blocked_summary}\n"
        "Что хочешь изменить?"
        "\n\n<i>Не все компании указывают грейд и город — такие вакансии тоже попадают в выдачу.</i>"
    )

    keyboard = [[{"text": "📬 Получить вакансии", "callback_data": "st:deliver"}]]

    keyboard.extend([
        [
            {"text": "Грейд", "callback_data": "st:edit:grade"},
            {"text": "Город", "callback_data": "st:edit:city"},
        ],
        [
            {"text": "Формат", "callback_data": "st:edit:wf"},
            {"text": "Компании", "callback_data": "st:edit:company"},
        ],
    ])

    if excluded_companies:
        keyboard.append([{"text": f"Заблокированные ({len(excluded_companies)})", "callback_data": "st:blocked"}])

    keyboard.extend([
        [
            {
                "text": "▶️ Возобновить" if paused else "⏸ Пауза",
                "callback_data": "st:resume" if paused else "st:pause",
            },
            {"text": "🚫 Отписаться", "callback_data": "st:stop"},
        ],
        [{"text": "◀️ Назад", "callback_data": "st:close"}],
    ])

    return text, {"inline_keyboard": keyboard}


def get_settings_step(step, current_filters, companies_list=None):
    if step == "company":
        return get_company_page(companies_list, current_filters, page=0, prefix=PREFIX)

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
        "Рассылка приостановлена. Настройки сохранены — когда будешь готов, возобнови одной кнопкой.",
        {
            "inline_keyboard": [[
                {"text": "▶️ Возобновить", "callback_data": "st:resume"},
                {"text": "◀️ К настройкам", "callback_data": "st:menu"},
            ]]
        },
    )


def get_resume_message():
    return (
        "Рассылка возобновлена! Новые вакансии придут в ближайшую рассылку.",
        {"inline_keyboard": [[{"text": "◀️ К настройкам", "callback_data": "st:menu"}]]},
    )


def get_stop_prompt():
    return (
        "Полностью отписываться необязательно — можно поставить рассылку на паузу и возобновить, когда придёт время.",
        {
            "inline_keyboard": [
                [{"text": "⏸ Поставить на паузу", "callback_data": "st:pause"}],
                [
                    {"text": "🚫 Всё равно отписаться", "callback_data": "st:stop:yes"},
                    {"text": "Отмена", "callback_data": "st:menu"},
                ],
            ]
        },
    )
