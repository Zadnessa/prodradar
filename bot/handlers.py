"""Обработка команд Telegram-бота."""

from bot.onboarding import (
    advance_step,
    get_fallback_message,
    get_empty_filter_for_step,
    get_step_message,
    get_welcome_message,
    parse_selections_from_markup,
    toggle_selection,
)
from bot.telegram_api import edit_message, send_message
from database.supabase_client import SupabaseService


FINAL_TEXT = (
    "Настройки сохранены! Буду присылать подходящие вакансии дважды в день.\n\n"
    "Изменить фильтры: /settings"
)
QUICK_START_TEXT = (
    "Отлично! Буду присылать все вакансии для продактов дважды в день.\n\n"
    "Настроить фильтры можно в любой момент через /settings."
)


def _edit_fallback(chat_id, message_id):
    text, _ = get_fallback_message()
    edit_message(chat_id, message_id, text, reply_markup=None)


def _handle_step_transition(chat_id, message_id, reply_markup, db, skip=False):
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
    step_filter_fragment = (
        get_empty_filter_for_step(current_step)
        if skip
        else parse_selections_from_markup(current_step, reply_markup)
    )
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
        edit_message(chat_id, message_id, "⏳ Настраиваю рассылку...", reply_markup=None)
        db.update_user_filters(chat_id, {})
        db.update_onboarding_step(chat_id, None)
        edit_message(chat_id, message_id, QUICK_START_TEXT, reply_markup=None)
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
        next_markup = toggle_selection("grade", reply_markup, callback_value)
        text, _ = get_step_message("grade", {})
        edit_message(chat_id, message_id, text, reply_markup=next_markup)
        return

    if data.startswith("ob:c:"):
        if not reply_markup:
            _edit_fallback(chat_id, message_id)
            return

        callback_value = data.split(":", 2)[2]
        next_markup = toggle_selection("city", reply_markup, callback_value)
        text, _ = get_step_message("city", {})
        edit_message(chat_id, message_id, text, reply_markup=next_markup)
        return

    if data.startswith("ob:wf:"):
        if not reply_markup:
            _edit_fallback(chat_id, message_id)
            return

        callback_value = data.split(":", 2)[2]
        next_markup = toggle_selection("work_format", reply_markup, callback_value)
        text, _ = get_step_message("work_format", {})
        edit_message(chat_id, message_id, text, reply_markup=next_markup)
        return

    if data.startswith("ob:co:"):
        if not reply_markup:
            _edit_fallback(chat_id, message_id)
            return

        callback_value = data.split(":", 2)[2]
        companies_list = db.get_enabled_companies()
        all_company_names = [company.get("parser_name") for company in companies_list]
        next_markup = toggle_selection("company", reply_markup, callback_value, all_company_names=all_company_names)
        text, _ = get_step_message("company", {}, companies_list=companies_list)
        edit_message(chat_id, message_id, text, reply_markup=next_markup)
        return

    if data == "ob:next":
        _handle_step_transition(chat_id, message_id, reply_markup, db, skip=False)
        return

    if data == "ob:skip":
        _handle_step_transition(chat_id, message_id, reply_markup, db, skip=True)
        return

    if data == "ob:done":
        edit_message(chat_id, message_id, "⏳ Сохраняю настройки...", reply_markup=None)
        db.update_onboarding_step(chat_id, None)
        edit_message(chat_id, message_id, FINAL_TEXT, reply_markup=None)
        return

    if data == "ob:restart":
        db.update_user_filters(chat_id, {})
        db.update_onboarding_step(chat_id, "grade")
        text, step_markup = get_step_message("grade", {})
        edit_message(chat_id, message_id, text, reply_markup=step_markup)
        return

    if data.startswith("ob:"):
        _edit_fallback(chat_id, message_id)


def handle_stop(chat_id, db=None):
    db = db or SupabaseService()
    db.deactivate_user(chat_id)
    send_message(chat_id, "Ты отписался от рассылки. Чтобы подписаться снова — отправь /start")


def handle_unknown(chat_id):
    send_message(chat_id, "Доступные команды: /start, /stop, /settings\n\nНовые вакансии приходят автоматически.")
