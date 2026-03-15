"""Обработка команд Telegram-бота."""

import config
from bot.onboarding import (
    advance_step,
    get_fallback_message,
    get_step_message,
    reverse_step,
    get_welcome_message,
    parse_selections_from_markup,
    toggle_selection,
)
from bot.settings import (
    get_pause_message,
    get_resume_message,
    get_settings_menu,
    get_settings_step,
    get_stop_confirm,
)
from bot.telegram_api import edit_message, send_message
from database.supabase_client import SupabaseService
from delivery.filters import filter_vacancies_for_user
from delivery.telegram import format_vacancy_message


FINAL_TEXT = (
    "Настройки сохранены! Пока подходящих вакансий нет —\n"
    "пришлю, как только появятся.\n\n"
    "Изменить фильтры: /settings"
)


def _edit_fallback(chat_id, message_id):
    text, _ = get_fallback_message()
    edit_message(chat_id, message_id, text, reply_markup=None)


def _detect_step_by_markup(reply_markup):
    rows = (reply_markup or {}).get("inline_keyboard", [])
    for row in rows:
        for button in row:
            callback_data = button.get("callback_data", "")
            if callback_data.startswith("st:g:"):
                return "grade"
            if callback_data.startswith("st:c:"):
                return "city"
            if callback_data.startswith("st:wf:"):
                return "work_format"
            if callback_data.startswith("st:co:"):
                return "company"
    return None


def _send_onboarding_batch(chat_id, message_id, db, filters):
    edit_message(chat_id, message_id, "⏳ Подбираю вакансии...", reply_markup=None)
    user = db.get_user(chat_id)
    effective_filters = filters if filters is not None else (user or {}).get("filters") or {}

    companies_list = db.get_enabled_companies()
    companies_map = {company.get("name"): company for company in companies_list}

    undelivered = db.get_undelivered_vacancies(chat_id, limit=6)
    filtered = filter_vacancies_for_user(undelivered, effective_filters)
    batch = filtered[:5]

    if not batch:
        edit_message(chat_id, message_id, FINAL_TEXT, reply_markup=None)
        return

    edit_message(chat_id, message_id, "Настройки сохранены! Вот первые подходящие вакансии:", reply_markup=None)

    for vacancy in batch:
        message = format_vacancy_message(vacancy, companies_map.get(vacancy.get("company"), {}))
        send_message(chat_id, message)

    db.mark_delivered(chat_id, [vacancy["id"] for vacancy in batch], source="onboarding")

    if len(filtered) > 5 or len(undelivered) == 6:
        send_message(
            chat_id,
            "Остальные подходящие вакансии пришлю в ближайшей рассылке.\n\n"
            "Изменить фильтры: /settings",
        )
    else:
        send_message(
            chat_id,
            "Это все вакансии на данный момент. Новые пришлю, как только появятся.\n\n"
            "Изменить фильтры: /settings",
        )


def _handle_step_transition(chat_id, message_id, reply_markup, db):
    if not reply_markup:
        _edit_fallback(chat_id, message_id)
        return

    user = db.get_user(chat_id)
    if not user:
        _edit_fallback(chat_id, message_id)
        return

    current_step = user.get("onboarding_step")
    if current_step not in {"grade", "city", "work_format", "company"}:
        _edit_fallback(chat_id, message_id)
        return

    current_filters = user.get("filters") or {}
    step_filter_fragment = parse_selections_from_markup(current_step, reply_markup)
    next_filters = dict(current_filters)
    next_filters.update(step_filter_fragment)

    next_step = advance_step(current_step)
    if not next_step:
        _edit_fallback(chat_id, message_id)
        return

    companies_list = None
    if next_step == "company":
        edit_message(chat_id, message_id, "⏳ Загружаю список компаний...", reply_markup=None)
        companies_list = db.get_enabled_companies()
    elif next_step == "confirm":
        edit_message(chat_id, message_id, "⏳ Применяю настройки...", reply_markup=None)
        companies_list = db.get_enabled_companies()
        step_filter_fragment = parse_selections_from_markup(current_step, reply_markup, companies_list=companies_list)
        next_filters = dict(current_filters)
        next_filters.update(step_filter_fragment)

    db.update_user_filters(chat_id, next_filters)
    db.update_onboarding_step(chat_id, next_step)

    text, next_markup = get_step_message(next_step, next_filters, companies_list=companies_list)
    edit_message(chat_id, message_id, text, reply_markup=next_markup)


def handle_start(chat_id, username, db=None):
    db = db or SupabaseService()
    db.upsert_user(chat_id, username, bot_id="main")
    db.update_user_filters(chat_id, {})
    db.update_onboarding_step(chat_id, "welcome")

    text, reply_markup = get_welcome_message()
    send_message(chat_id, text, reply_markup=reply_markup)


def handle_callback(data, chat_id, message_id, callback_message, db=None):
    db = db or SupabaseService()
    reply_markup = (callback_message or {}).get("reply_markup")

    if data == "ob:quick":
        db.update_user_filters(chat_id, {})
        db.update_onboarding_step(chat_id, None)
        _send_onboarding_batch(chat_id, message_id, db, filters={})
        return

    if data == "ob:setup":
        db.update_onboarding_step(chat_id, "grade")
        text, step_markup = get_step_message("grade", {})
        edit_message(chat_id, message_id, text, reply_markup=step_markup)
        return

    if data.startswith("ob:g:"):
        if not reply_markup:
            _edit_fallback(chat_id, message_id)
            return

        callback_value = data.split(":", 2)[2]
        toggled_markup = toggle_selection("grade", reply_markup, callback_value)
        current_filters = parse_selections_from_markup("grade", toggled_markup)
        text, next_markup = get_step_message("grade", current_filters)
        edit_message(chat_id, message_id, text, reply_markup=next_markup)
        return

    if data.startswith("ob:c:"):
        if not reply_markup:
            _edit_fallback(chat_id, message_id)
            return

        callback_value = data.split(":", 2)[2]
        toggled_markup = toggle_selection("city", reply_markup, callback_value)
        current_filters = parse_selections_from_markup("city", toggled_markup)
        text, next_markup = get_step_message("city", current_filters)
        edit_message(chat_id, message_id, text, reply_markup=next_markup)
        return

    if data.startswith("ob:wf:"):
        if not reply_markup:
            _edit_fallback(chat_id, message_id)
            return

        callback_value = data.split(":", 2)[2]
        toggled_markup = toggle_selection("work_format", reply_markup, callback_value)
        current_filters = parse_selections_from_markup("work_format", toggled_markup)
        text, next_markup = get_step_message("work_format", current_filters)
        edit_message(chat_id, message_id, text, reply_markup=next_markup)
        return

    if data.startswith("ob:co:"):
        if not reply_markup:
            _edit_fallback(chat_id, message_id)
            return

        callback_value = data.split(":", 2)[2]
        next_markup = toggle_selection("company", reply_markup, callback_value, all_company_names=None)
        text = (callback_message or {}).get("text") or "<b>Шаг 4 из 5 — Компании</b>"
        edit_message(chat_id, message_id, text, reply_markup=next_markup)
        return

    if data == "ob:next":
        _handle_step_transition(chat_id, message_id, reply_markup, db)
        return

    if data == "ob:back":
        user = db.get_user(chat_id)
        if not user:
            _edit_fallback(chat_id, message_id)
            return

        previous_step = reverse_step(user.get("onboarding_step"))
        if previous_step is None:
            _edit_fallback(chat_id, message_id)
            return

        current_filters = user.get("filters") or {}
        companies_list = None
        if previous_step == "company":
            edit_message(chat_id, message_id, "⏳ Загружаю список компаний...", reply_markup=None)
            companies_list = db.get_enabled_companies()

        db.update_onboarding_step(chat_id, previous_step)
        text, step_markup = get_step_message(previous_step, current_filters, companies_list=companies_list)
        edit_message(chat_id, message_id, text, reply_markup=step_markup)
        return

    if data == "ob:done":
        db.update_onboarding_step(chat_id, None)
        _send_onboarding_batch(chat_id, message_id, db, filters=None)
        return

    if data == "ob:restart":
        db.update_user_filters(chat_id, {})
        db.update_onboarding_step(chat_id, "grade")
        text, step_markup = get_step_message("grade", {})
        edit_message(chat_id, message_id, text, reply_markup=step_markup)
        return

    if data.startswith("ob:"):
        _edit_fallback(chat_id, message_id)


def handle_settings(chat_id, db=None):
    db = db or SupabaseService()
    user = db.get_user(chat_id)

    if not user:
        send_message(chat_id, "Сначала подпишись через /start")
        return

    if user.get("onboarding_step") is not None:
        send_message(chat_id, "Сначала заверши настройку фильтров или нажми /start, чтобы начать заново.")
        return

    text, reply_markup = get_settings_menu(user)
    send_message(chat_id, text, reply_markup=reply_markup)


def handle_settings_callback(data, chat_id, message_id, callback_message, db=None):
    db = db or SupabaseService()
    reply_markup = (callback_message or {}).get("reply_markup")

    if data in {"st:edit:grade", "st:edit:city", "st:edit:wf", "st:edit:company"}:
        step_map = {
            "st:edit:grade": "grade",
            "st:edit:city": "city",
            "st:edit:wf": "work_format",
            "st:edit:company": "company",
        }
        step = step_map[data]

        user = db.get_user(chat_id)
        if not user:
            edit_message(chat_id, message_id, "Сначала подпишись через /start", reply_markup=None)
            return

        companies_list = None
        if step == "company":
            edit_message(chat_id, message_id, "⏳ Загружаю список компаний...", reply_markup=None)
            companies_list = db.get_enabled_companies()

        text, step_markup = get_settings_step(step, user.get("filters") or {}, companies_list=companies_list)
        edit_message(chat_id, message_id, text, reply_markup=step_markup)
        return

    if data.startswith("st:g:") or data.startswith("st:c:") or data.startswith("st:wf:") or data.startswith("st:co:"):
        if not reply_markup:
            _edit_fallback(chat_id, message_id)
            return

        if data.startswith("st:g:"):
            step = "grade"
        elif data.startswith("st:c:"):
            step = "city"
        elif data.startswith("st:wf:"):
            step = "work_format"
        else:
            step = "company"

        callback_value = data.split(":", 2)[2]
        toggled_markup = toggle_selection(
            step,
            reply_markup,
            callback_value,
            all_company_names=None,
            prefix="st",
        )

        companies_list = db.get_enabled_companies() if step == "company" else None
        current_filters = parse_selections_from_markup(
            step,
            toggled_markup,
            companies_list=companies_list,
            prefix="st",
        )
        text, next_markup = get_settings_step(step, current_filters, companies_list=companies_list)
        edit_message(chat_id, message_id, text, reply_markup=next_markup)
        return

    if data == "st:save":
        if not reply_markup:
            _edit_fallback(chat_id, message_id)
            return

        user = db.get_user(chat_id)
        if not user:
            edit_message(chat_id, message_id, "Сначала подпишись через /start", reply_markup=None)
            return

        step = _detect_step_by_markup(reply_markup)
        if not step:
            _edit_fallback(chat_id, message_id)
            return

        companies_list = db.get_enabled_companies() if step == "company" else None
        fragment = parse_selections_from_markup(step, reply_markup, companies_list=companies_list, prefix="st")

        merged = dict(user.get("filters") or {})
        merged.update(fragment)
        db.update_user_filters(chat_id, merged)

        refreshed_user = db.get_user(chat_id) or {}
        text, menu_markup = get_settings_menu(refreshed_user)
        edit_message(chat_id, message_id, text, reply_markup=menu_markup)
        return

    if data == "st:pause":
        db.set_user_paused(chat_id, True)
        text, reply = get_pause_message()
        edit_message(chat_id, message_id, text, reply_markup=reply)
        return

    if data == "st:resume":
        db.set_user_paused(chat_id, False)
        text, reply = get_resume_message()
        edit_message(chat_id, message_id, text, reply_markup=reply)
        return

    if data == "st:stop":
        text, reply = get_stop_confirm()
        edit_message(chat_id, message_id, text, reply_markup=reply)
        return

    if data == "st:stop:yes":
        db.deactivate_user(chat_id)
        edit_message(chat_id, message_id, "Ты отписался от рассылки. Чтобы вернуться — /start", reply_markup=None)
        return

    if data == "st:close":
        edit_message(chat_id, message_id, "Настройки сохранены.", reply_markup=None)
        return

    if data in {"st:menu", "st:back"}:
        user = db.get_user(chat_id)
        text, menu_markup = get_settings_menu(user or {})
        edit_message(chat_id, message_id, text, reply_markup=menu_markup)


def handle_stats(chat_id, db=None):
    db = db or SupabaseService()
    user = db.get_user(chat_id)

    if not user:
        send_message(chat_id, "Сначала подпишись через /start")
        return

    if user.get("onboarding_step") is not None:
        send_message(chat_id, "Сначала заверши настройку фильтров или нажми /start, чтобы начать заново.")
        return

    stats = db.get_vacancy_stats()
    total = stats.get("total", 0)
    by_company = stats.get("by_company") or {}

    companies = db.get_enabled_companies()
    companies_map = {company.get("name"): company for company in companies}

    all_vacancies = db.get_undelivered_vacancies(chat_id, limit=500)
    filtered_count = len(filter_vacancies_for_user(all_vacancies, user.get("filters") or {}))

    company_lines = []
    for company_name, count in sorted(by_company.items(), key=lambda item: item[1], reverse=True):
        company_meta = companies_map.get(company_name, {})
        emoji = company_meta.get("emoji") or "🏢"
        company_lines.append(f"{emoji} {company_name}: {count}")

    lines = "\n".join(company_lines) if company_lines else "Нет данных"
    text = (
        f"📊 Статистика вакансий (за {config.VACANCY_TTL_DAYS} дней)\n\n"
        f"Всего на рынке: {total}\n"
        f"Подходят под твои фильтры: {filtered_count}\n\n"
        f"По компаниям:\n{lines}"
    )
    send_message(chat_id, text)


def handle_stop(chat_id, db=None):
    db = db or SupabaseService()
    db.deactivate_user(chat_id)
    send_message(chat_id, "Ты отписался от рассылки. Чтобы подписаться снова — отправь /start")


def handle_unknown(chat_id):
    send_message(chat_id, "Доступные команды: /start, /stop, /settings, /stats\n\nНовые вакансии приходят автоматически.")
