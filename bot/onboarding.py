"""State machine онбординга: формирование сообщений и разбор выбора из кнопок."""

from copy import deepcopy

GRADE_OPTIONS = ["Junior", "Middle", "Senior", "Lead+"]
CITY_OPTIONS = [
    {"label": "Москва", "callback_value": "Москва", "filter_value": "Москва"},
    {"label": "Санкт-Петербург", "callback_value": "СПб", "filter_value": "Санкт-Петербург"},
    {"label": "Другой / зарубежные", "callback_value": "Другой", "filter_value": "Другой"},
]
WORK_FORMAT_OPTIONS = [
    {"label": "Офис", "callback_value": "office", "filter_value": "Офис"},
    {"label": "Удалёнка", "callback_value": "remote", "filter_value": "Удалёнка"},
    {"label": "Гибрид", "callback_value": "hybrid", "filter_value": "Гибрид"},
]

CITY_CALLBACK_TO_FILTER = {item["callback_value"]: item["filter_value"] for item in CITY_OPTIONS}
WORK_FORMAT_CALLBACK_TO_FILTER = {item["callback_value"]: item["filter_value"] for item in WORK_FORMAT_OPTIONS}


def get_welcome_message():
    text = (
        "Привет! Я — <b>ProductRadar</b>.\n\n"
        "Слежу за вакансиями для продакт-менеджеров напрямую на сайтах Яндекса, Озона, Т-Банка и ещё 5 компаний. "
        "Никаких агрегаторов — только первоисточники.\n\n"
        "Присылаю новые позиции дважды в день.\n\n"
        "Можешь настроить фильтры под себя или начать сразу — потом всё легко поменять через /settings."
    )
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "⚡ Быстрый старт", "callback_data": "ob:quick"},
                {"text": "⚙️ Настроить", "callback_data": "ob:setup"},
            ]
        ]
    }
    return text, reply_markup


def _get_adaptive_next_button(step, current_filters, prefix):
    selected_map = {
        "grade": current_filters.get("grades") or [],
        "city": current_filters.get("cities") or [],
        "work_format": current_filters.get("work_formats") or [],
    }

    is_selected = True if step == "company" else bool(selected_map.get(step, []))
    button_text = "Далее ➡️" if is_selected else "Пропустить ⏭"
    return {"text": button_text, "callback_data": f"{prefix}:next"}


def _build_step_navigation(step, current_filters, prefix):
    next_button = _get_adaptive_next_button(step, current_filters, prefix)
    if step == "grade":
        return [next_button]
    return [
        {"text": "◀️ Назад", "callback_data": f"{prefix}:back"},
        next_button,
    ]


def get_step_message(step, current_filters, companies_list=None, prefix="ob"):
    current_filters = current_filters or {}

    if step == "grade":
        text = (
            "<b>Шаг 1 из 5 — Грейд</b>\n\n"
            "Какой уровень позиций тебе интересен? Можно выбрать несколько — покажу вакансии по всем отмеченным."
        )
        selected = set(current_filters.get("grades") or [])
        buttons = [
            {
                "text": f"{'✅' if grade in selected else '⬜'} {grade}",
                "callback_data": f"{prefix}:g:{grade}",
            }
            for grade in GRADE_OPTIONS
        ]
        keyboard = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
        keyboard.append(_build_step_navigation("grade", current_filters, prefix))
        return text, {"inline_keyboard": keyboard}

    if step == "city":
        text = (
            "<b>Шаг 2 из 5 — Город</b>\n\n"
            "В каком городе ищешь? «Другой / зарубежные» — это все остальные города и  другие страны, где нанимают компании из списка.\n\n"
            "Формат работы (удалёнка, офис) будет на следующем шаге."
        )
        selected = set(current_filters.get("cities") or [])
        buttons = [
            {
                "text": f"{'✅' if option['filter_value'] in selected else '⬜'} {option['label']}",
                "callback_data": f"{prefix}:c:{option['callback_value']}",
            }
            for option in CITY_OPTIONS
        ]
        keyboard = [buttons]
        keyboard.append(_build_step_navigation("city", current_filters, prefix))
        return text, {"inline_keyboard": keyboard}

    if step == "work_format":
        text = (
            "<b>Шаг 3 из 5 — Формат работы</b>\n\n"
            "Какой формат подходит? Если у вакансии формат не указан — я всё равно её покажу, чтобы ты ничего не пропустил."
        )
        selected = set(current_filters.get("work_formats") or [])
        buttons = [
            {
                "text": f"{'✅' if option['filter_value'] in selected else '⬜'} {option['label']}",
                "callback_data": f"{prefix}:wf:{option['callback_value']}",
            }
            for option in WORK_FORMAT_OPTIONS
        ]
        keyboard = [buttons]
        keyboard.append(_build_step_navigation("work_format", current_filters, prefix))
        return text, {"inline_keyboard": keyboard}

    if step == "company":
        text = (
            "<b>Шаг 4 из 5 — Компании</b>\n\n"
            "Все компании включены по-умолчанию. Нажми на компанию, чтобы убрать её из рассылки."
        )
        companies_list = companies_list or []
        enabled_companies = current_filters.get("companies") or []
        all_enabled = len(enabled_companies) == 0

        rows = []
        row = []
        for company in companies_list:
            parser_name = company.get("parser_name")
            label = company.get("name") or parser_name
            is_enabled = all_enabled or parser_name in enabled_companies
            marker = "🟢" if is_enabled else "🔴"
            row.append(
                {
                    "text": f"{marker} {label}",
                    "callback_data": f"{prefix}:co:{parser_name}",
                }
            )
            if len(row) == 2:
                rows.append(row)
                row = []

        if row:
            rows.append(row)

        rows.append(_build_step_navigation("company", current_filters, prefix))
        return text, {"inline_keyboard": rows}

    if step == "confirm":
        companies_list = companies_list or []

        grades = current_filters.get("grades") or []
        cities = current_filters.get("cities") or []
        work_formats = current_filters.get("work_formats") or []
        companies = current_filters.get("companies") or []

        grades_text = ", ".join(grades) if grades else "Все"
        cities_text = ", ".join(cities) if cities else "Все"
        work_formats_text = ", ".join(work_formats) if work_formats else "Все"
        companies_text = ", ".join(companies) if companies else "Все"

        text = (
            "<b>Шаг 5 из 5 — Проверь настройки</b>\n\n"
            f"• Грейды: {grades_text}\n"
            f"• Города: {cities_text}\n"
            f"• Формат: {work_formats_text}\n"
            f"• Компании: {companies_text}\n\n"
            "Изменить фильтры можно в любой момент через /settings."
        )
        reply_markup = {
            "inline_keyboard": [
                [
                    {"text": "◀️ Назад", "callback_data": "ob:back"},
                    {"text": "👍 Отлично", "callback_data": "ob:done"},
                    {"text": "🔄 Заново", "callback_data": "ob:restart"},
                ]
            ]
        }
        return text, reply_markup

    return get_fallback_message()


def toggle_selection(step, reply_markup, callback_value, all_company_names=None, prefix="ob"):
    markup = deepcopy(reply_markup or {"inline_keyboard": []})
    for row in markup.get("inline_keyboard", []):
        for button in row:
            callback_data = button.get("callback_data", "")
            if step == "grade" and callback_data == f"{prefix}:g:{callback_value}":
                button["text"] = button["text"].replace("✅", "⬜", 1) if button["text"].startswith("✅") else button["text"].replace("⬜", "✅", 1)
            elif step == "city" and callback_data == f"{prefix}:c:{callback_value}":
                button["text"] = button["text"].replace("✅", "⬜", 1) if button["text"].startswith("✅") else button["text"].replace("⬜", "✅", 1)
            elif step == "work_format" and callback_data == f"{prefix}:wf:{callback_value}":
                button["text"] = button["text"].replace("✅", "⬜", 1) if button["text"].startswith("✅") else button["text"].replace("⬜", "✅", 1)
            elif step == "company" and callback_data == f"{prefix}:co:{callback_value}":
                button["text"] = button["text"].replace("🟢", "🔴", 1) if button["text"].startswith("🟢") else button["text"].replace("🔴", "🟢", 1)

    if step == "company" and all_company_names:
        # Параметр оставлен для совместимости и явного контекста шага компаний.
        _ = all_company_names

    return markup


def parse_selections_from_markup(step, reply_markup, companies_list=None, prefix="ob"):
    markup = reply_markup or {}
    rows = markup.get("inline_keyboard", [])

    if step == "grade":
        selected = []
        for row in rows:
            for button in row:
                callback_data = button.get("callback_data", "")
                if callback_data.startswith(f"{prefix}:g:") and button.get("text", "").startswith("✅"):
                    selected.append(callback_data.split(":", 2)[2])
        return {"grades": selected}

    if step == "city":
        selected = []
        for row in rows:
            for button in row:
                callback_data = button.get("callback_data", "")
                if callback_data.startswith(f"{prefix}:c:") and button.get("text", "").startswith("✅"):
                    callback_value = callback_data.split(":", 2)[2]
                    selected.append(CITY_CALLBACK_TO_FILTER.get(callback_value, callback_value))
        return {"cities": selected}

    if step == "work_format":
        selected = []
        for row in rows:
            for button in row:
                callback_data = button.get("callback_data", "")
                if callback_data.startswith(f"{prefix}:wf:") and button.get("text", "").startswith("✅"):
                    callback_value = callback_data.split(":", 2)[2]
                    selected.append(WORK_FORMAT_CALLBACK_TO_FILTER.get(callback_value, callback_value))
        return {"work_formats": selected}

    if step == "company":
        companies_list = companies_list or []
        company_name_map = {item.get("parser_name"): item.get("name") for item in companies_list}
        enabled = []
        all_names = []
        for row in rows:
            for button in row:
                callback_data = button.get("callback_data", "")
                if callback_data.startswith(f"{prefix}:co:"):
                    parser_name = callback_data.split(":", 2)[2]
                    company_name = company_name_map.get(parser_name, parser_name)
                    all_names.append(company_name)
                    if button.get("text", "").startswith("🟢"):
                        enabled.append(company_name)

        if all_names and len(enabled) == len(all_names):
            return {"companies": []}
        return {"companies": enabled}

    return {}



def reverse_step(current_step):
    order = ["grade", "city", "work_format", "company", "confirm"]
    if current_step not in order:
        return None

    index = order.index(current_step)
    return order[index - 1] if index > 0 else None


def advance_step(current_step):
    order = ["grade", "city", "work_format", "company", "confirm"]
    if current_step not in order:
        return None

    index = order.index(current_step)
    return order[index + 1] if index + 1 < len(order) else None


def get_fallback_message():
    return "Сессия настройки устарела. Нажми /start, чтобы начать заново.", None
