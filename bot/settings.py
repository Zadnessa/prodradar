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


def get_settings_menu(user):
    user = user or {}
    paused = bool(user.get("paused"))
    text = "⚙️ Настройки\n\nЧто хочешь изменить?"

    keyboard = [
        [{"text": "Грейд", "callback_data": "st:edit:grade"}],
        [{"text": "Город", "callback_data": "st:edit:city"}],
        [{"text": "Формат работы", "callback_data": "st:edit:wf"}],
        [{"text": "Компании", "callback_data": "st:edit:company"}],
    ]

    if paused:
        keyboard.append([{"text": "▶️ Возобновить рассылку", "callback_data": "st:resume"}])
    else:
        keyboard.append([{"text": "⏸ Поставить на паузу", "callback_data": "st:pause"}])

    keyboard.append([{"text": "🚫 Отписаться", "callback_data": "st:stop"}])

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
