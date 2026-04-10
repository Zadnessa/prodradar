"""State machine онбординга: формирование сообщений и разбор выбора из кнопок."""

import math
from copy import deepcopy

GRADE_OPTIONS = ["Junior", "Middle", "Senior", "Lead+"]
CITY_OPTIONS = [
    {"label": "Москва", "callback_value": "Москва", "filter_value": "Москва"},
    {"label": "Санкт-Петербург", "callback_value": "СПб", "filter_value": "Санкт-Петербург"},
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
        "Привет!\n"
        "Я помогаю продакт-менеджерам найти релевантные вакансии и мониторю появление новых предложений дважды в день.\n"
        "⚡ <b>Быстрый старт</b> – сразу попробовать посмотреть, как тут все устроено.\n"
        "⚙️ <b>Настроить</b> – пройти онбординг, сделать пару полезных фильтров и увеличить релевантность выдачи.\n\n"
        "Удачи!"
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


def _format_filter_values(values, empty_text):
    return ", ".join(values) if values else empty_text


def get_hub_message(user):
    user = user or {}
    filters = user.get("filters") or {}

    grades_text = _format_filter_values(filters.get("grades") or [], "любой")
    cities_text = _format_filter_values(filters.get("cities") or [], "любой")
    work_formats_text = _format_filter_values(filters.get("work_formats") or [], "любой")
    companies_text = _format_filter_values(filters.get("companies") or [], "все")

    text = (
        "<b>С возвращением!</b>\n\n"
        f"Грейд: {grades_text}\n"
        f"Город: {cities_text}\n"
        f"Формат: {work_formats_text}\n"
        f"Компании: {companies_text}\n\n"
        "Что хочешь сделать?"
    )
    reply_markup = {
        "inline_keyboard": [
            [{"text": "📬 Получить вакансии", "callback_data": "hub:vacancies"}],
            [{"text": "⚙️ Изменить фильтры", "callback_data": "hub:settings"}],
            [{"text": "🔄 Начать заново", "callback_data": "hub:reset"}],
        ]
    }
    return text, reply_markup


def get_continue_message():
    text = "Ты не закончил настройку. Продолжить с того места или начать заново?"
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "▶️ Продолжить", "callback_data": "hub:continue"},
                {"text": "🔄 Заново", "callback_data": "hub:reset"},
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

    is_selected = bool(selected_map.get(step, []))
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
            "<b>Шаг 1 из 4</b> – Грейд\n\n"
            "Какой уровень позиций тебя интересует? Можно выбрать несколько – покажу вакансии по каждому."
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
            "<b>Шаг 2 из 4</b> – Город\n\n\n"
            "В каком городе ищешь? Можно выбрать несколько.\n"
            "«Любой город» означает буквально любой: может попасться Минск, Алматы и прочие интересные места.\n\n"
            "⚠ Формат работы (удалёнка, офис) будет на следующем шаге."
        )
        selected = set(current_filters.get("cities") or [])
        buttons = [
            {
                "text": f"{'✅' if option['filter_value'] in selected else '⬜'} {option['label']}",
                "callback_data": f"{prefix}:c:{option['callback_value']}",
            }
            for option in CITY_OPTIONS
        ]
        keyboard = [
            [{"text": "🌍 Любой город", "callback_data": f"{prefix}:c:any"}],
            buttons,
            _build_step_navigation("city", current_filters, prefix),
        ]
        return text, {"inline_keyboard": keyboard}

    if step == "work_format":
        text = (
            "<b>Шаг 3 из 4</b> – Формат работы\n\n"
            "Какой формат ищешь? Можно выбрать несколько."
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

    if step == "confirm":
        grades = current_filters.get("grades") or []
        cities = current_filters.get("cities") or []
        work_formats = current_filters.get("work_formats") or []

        grades_text = ", ".join(grades) if grades else "Все"
        cities_text = ", ".join(cities) if cities else "Любой"
        work_formats_text = ", ".join(work_formats) if work_formats else "Все"

        text = (
            "<b>Шаг 4 из 4</b> – Проверь настройки\n\n"
            f"• Грейды: {grades_text}\n"
            f"• Города: {cities_text}\n"
            f"• Формат: {work_formats_text}\n"
            "\n"
            "Изменить фильтры можно в любой момент через /settings."
        )
        reply_markup = {
            "inline_keyboard": [
                [
                    {"text": "◀️ Назад", "callback_data": f"{prefix}:back"},
                    {"text": "🔄 Заново", "callback_data": f"{prefix}:restart"},
                    {"text": "👍 Отлично", "callback_data": f"{prefix}:done"},
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
        company_name_map = {
            str(item.get("slug") or item.get("id") or item.get("parser_name")): item.get("name")
            for item in companies_list
        }
        enabled = []
        all_names = []
        for row in rows:
            for button in row:
                callback_data = button.get("callback_data", "")
                if callback_data.startswith(f"{prefix}:co:"):
                    company_slug = callback_data.split(":", 2)[2]
                    company_name = company_name_map.get(company_slug, company_slug)
                    all_names.append(company_name)
                    if button.get("text", "").startswith("🟢"):
                        enabled.append(company_name)

        if all_names and len(enabled) == len(all_names):
            return {"companies": []}
        return {"companies": enabled}

    return {}




def get_company_page(companies_list, current_filters, page=0, page_size=8, prefix="st"):
    companies_list = companies_list or []
    current_filters = current_filters or {}
    excluded_companies = set(current_filters.get("excluded_companies") or [])

    blocked_companies = []
    active_companies = []
    for company in companies_list:
        company_name = company.get("name", "")
        if company_name in excluded_companies:
            blocked_companies.append(company)
        else:
            active_companies.append(company)

    blocked_companies.sort(key=lambda company: company.get("sort_name", company.get("name", "")).lower())
    active_companies.sort(key=lambda company: company.get("sort_name", company.get("name", "")).lower())
    sorted_companies = blocked_companies + active_companies

    total_pages = max(1, math.ceil(len(sorted_companies) / page_size))
    safe_page = max(0, min(page, total_pages - 1))

    start = safe_page * page_size
    end = start + page_size
    page_companies = sorted_companies[start:end]

    rows = []
    row = []
    for company in page_companies:
        company_slug = company.get("slug") or company.get("id")
        company_name = company.get("name") or company.get("parser_name") or str(company_slug)
        marker = "🔴" if company_name in excluded_companies else "🟢"
        row.append({"text": f"{marker} {company_name}", "callback_data": f"{prefix}:co:{company_slug}"})
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    if total_pages > 1:
        nav_row = []
        if safe_page > 0:
            nav_row.append({"text": "⬅️", "callback_data": f"{prefix}:co:page:{safe_page - 1}"})
        if safe_page < total_pages - 1:
            nav_row.append({"text": "➡️", "callback_data": f"{prefix}:co:page:{safe_page + 1}"})
        if nav_row:
            rows.append(nav_row)

    rows.append([
        {"text": "💾 Сохранить", "callback_data": f"{prefix}:save"},
        {"text": "◀️ Назад", "callback_data": f"{prefix}:back"},
    ])

    text = f"⚙️ <b>Компании</b> ({safe_page + 1}/{total_pages})\n\n🔴 – заблокированные, 🟢 – активные"
    return text, {"inline_keyboard": rows}



def reverse_step(current_step):
    order = ["grade", "city", "work_format", "confirm"]
    if current_step not in order:
        return None

    index = order.index(current_step)
    return order[index - 1] if index > 0 else None


def advance_step(current_step):
    order = ["grade", "city", "work_format", "confirm"]
    if current_step not in order:
        return None

    index = order.index(current_step)
    return order[index + 1] if index + 1 < len(order) else None


def get_fallback_message():
    return "Сессия настройки устарела. Нажми /start, чтобы начать заново.", None


def get_disclaimer_message(hidden_count, show_count, strict_count):
    text = (
        "<b>Последний момент</b>\n\n"
        "⚠ Не все компании указывают грейд, город и формат работы. Из-за этого часть вакансий приходит с пустыми полями. "
        "Тут ничего не поделать, но я пытался.\n\n"
        f"В строгом режиме будет на {hidden_count} вакансий меньше. Что делать с такими?"
    )
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": f"Показать ({show_count})", "callback_data": "ob:strict:off"},
                {"text": f"Скрыть ({strict_count})", "callback_data": "ob:strict:on"},
            ]
        ]
    }
    return text, reply_markup
