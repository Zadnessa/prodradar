"""State machine онбординга: формирование сообщений и разбор выбора из кнопок."""

from copy import deepcopy

GRADE_OPTIONS = ["Junior", "Middle", "Senior"]
CITY_OPTIONS = [
    {"label": "Москва", "callback_value": "Москва", "filter_value": "Москва"},
    {"label": "Санкт-Петербург", "callback_value": "СПб", "filter_value": "Санкт-Петербург"},
    {"label": "Другой", "callback_value": "Другой", "filter_value": "Другой"},
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
        "👋 Добро пожаловать в Vacancy Radar!\n\n"
        "Помогу настроить рассылку вакансий Product Manager под твои предпочтения."
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


def get_step_message(step, current_filters, companies_list=None):
    current_filters = current_filters or {}

    if step == "grade":
        text = "Шаг 1/5. Выбери грейд(ы):"
        selected = set(current_filters.get("grades") or [])
        buttons = [
            {
                "text": f"{'✅' if grade in selected else '⬜'} {grade}",
                "callback_data": f"ob:g:{grade}",
            }
            for grade in GRADE_OPTIONS
        ]
        keyboard = [buttons, [{"text": "Далее →", "callback_data": "ob:next"}]]
        return text, {"inline_keyboard": keyboard}

    if step == "city":
        text = "Шаг 2/5. Выбери город(а):"
        selected = set(current_filters.get("cities") or [])
        buttons = [
            {
                "text": f"{'✅' if option['filter_value'] in selected else '⬜'} {option['label']}",
                "callback_data": f"ob:c:{option['callback_value']}",
            }
            for option in CITY_OPTIONS
        ]
        keyboard = [buttons, [{"text": "Далее →", "callback_data": "ob:next"}]]
        return text, {"inline_keyboard": keyboard}

    if step == "work_format":
        text = "Шаг 3/5. Выбери формат работы:"
        selected = set(current_filters.get("work_formats") or [])
        buttons = [
            {
                "text": f"{'✅' if option['filter_value'] in selected else '⬜'} {option['label']}",
                "callback_data": f"ob:wf:{option['callback_value']}",
            }
            for option in WORK_FORMAT_OPTIONS
        ]
        keyboard = [buttons, [{"text": "Далее →", "callback_data": "ob:next"}]]
        return text, {"inline_keyboard": keyboard}

    if step == "company":
        text = "Шаг 4/5. Выбери компании:"
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
                    "callback_data": f"ob:co:{parser_name}",
                }
            )
            if len(row) == 2:
                rows.append(row)
                row = []

        if row:
            rows.append(row)

        rows.append([{"text": "Далее →", "callback_data": "ob:next"}])
        return text, {"inline_keyboard": rows}

    if step == "confirm":
        companies_list = companies_list or []
        company_name_map = {item.get("parser_name"): item.get("name") for item in companies_list}

        grades = current_filters.get("grades") or []
        cities = current_filters.get("cities") or []
        work_formats = current_filters.get("work_formats") or []
        companies = current_filters.get("companies") or []

        grades_text = ", ".join(grades) if grades else "Все"
        cities_text = ", ".join(cities) if cities else "Все"
        work_formats_text = ", ".join(work_formats) if work_formats else "Все"
        if companies:
            company_names = [company_name_map.get(parser_name, parser_name) for parser_name in companies]
            companies_text = ", ".join(company_names)
        else:
            companies_text = "Все"

        text = (
            "Шаг 5/5. Проверь настройки:\n\n"
            f"• Грейды: {grades_text}\n"
            f"• Города: {cities_text}\n"
            f"• Формат: {work_formats_text}\n"
            f"• Компании: {companies_text}"
        )
        reply_markup = {
            "inline_keyboard": [
                [
                    {"text": "👍 Отлично", "callback_data": "ob:done"},
                    {"text": "🔄 Заново", "callback_data": "ob:restart"},
                ]
            ]
        }
        return text, reply_markup

    return get_fallback_message()


def toggle_selection(step, reply_markup, callback_value, all_company_names=None):
    markup = deepcopy(reply_markup or {"inline_keyboard": []})
    for row in markup.get("inline_keyboard", []):
        for button in row:
            callback_data = button.get("callback_data", "")
            if step == "grade" and callback_data == f"ob:g:{callback_value}":
                button["text"] = button["text"].replace("✅", "⬜", 1) if button["text"].startswith("✅") else button["text"].replace("⬜", "✅", 1)
            elif step == "city" and callback_data == f"ob:c:{callback_value}":
                button["text"] = button["text"].replace("✅", "⬜", 1) if button["text"].startswith("✅") else button["text"].replace("⬜", "✅", 1)
            elif step == "work_format" and callback_data == f"ob:wf:{callback_value}":
                button["text"] = button["text"].replace("✅", "⬜", 1) if button["text"].startswith("✅") else button["text"].replace("⬜", "✅", 1)
            elif step == "company" and callback_data == f"ob:co:{callback_value}":
                button["text"] = button["text"].replace("🟢", "🔴", 1) if button["text"].startswith("🟢") else button["text"].replace("🔴", "🟢", 1)

    if step == "company" and all_company_names:
        # Параметр оставлен для совместимости и явного контекста шага компаний.
        _ = all_company_names

    return markup


def parse_selections_from_markup(step, reply_markup):
    markup = reply_markup or {}
    rows = markup.get("inline_keyboard", [])

    if step == "grade":
        selected = []
        for row in rows:
            for button in row:
                callback_data = button.get("callback_data", "")
                if callback_data.startswith("ob:g:") and button.get("text", "").startswith("✅"):
                    selected.append(callback_data.split(":", 2)[2])
        return {"grades": selected}

    if step == "city":
        selected = []
        for row in rows:
            for button in row:
                callback_data = button.get("callback_data", "")
                if callback_data.startswith("ob:c:") and button.get("text", "").startswith("✅"):
                    callback_value = callback_data.split(":", 2)[2]
                    selected.append(CITY_CALLBACK_TO_FILTER.get(callback_value, callback_value))
        return {"cities": selected}

    if step == "work_format":
        selected = []
        for row in rows:
            for button in row:
                callback_data = button.get("callback_data", "")
                if callback_data.startswith("ob:wf:") and button.get("text", "").startswith("✅"):
                    callback_value = callback_data.split(":", 2)[2]
                    selected.append(WORK_FORMAT_CALLBACK_TO_FILTER.get(callback_value, callback_value))
        return {"work_formats": selected}

    if step == "company":
        enabled = []
        all_names = []
        for row in rows:
            for button in row:
                callback_data = button.get("callback_data", "")
                if callback_data.startswith("ob:co:"):
                    parser_name = callback_data.split(":", 2)[2]
                    all_names.append(parser_name)
                    if button.get("text", "").startswith("🟢"):
                        enabled.append(parser_name)

        if all_names and len(enabled) == len(all_names):
            return {"companies": []}
        return {"companies": enabled}

    return {}


def advance_step(current_step):
    order = ["grade", "city", "work_format", "company", "confirm"]
    if current_step not in order:
        return None

    index = order.index(current_step)
    return order[index + 1] if index + 1 < len(order) else None


def get_fallback_message():
    return "Сессия настройки устарела. Нажми /start, чтобы начать заново.", None
