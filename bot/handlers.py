"""Обработка команд Telegram-бота."""

import config
import logging
import re
from bot.onboarding import (
    advance_step,
    get_continue_message,
    get_company_page,
    get_disclaimer_message,
    get_fallback_message,
    get_hub_message,
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
from bot.telegram_api import delete_message, edit_message, send_message
from database.supabase_client import SupabaseService
from delivery.filters import filter_vacancies_for_user
from delivery.telegram import format_company_emoji, format_vacancy_message


def _pluralize(number, one, few, many):
    number = abs(number) % 100
    last_digit = number % 10
    if 10 < number < 20:
        return many
    if last_digit == 1:
        return one
    if 2 <= last_digit <= 4:
        return few
    return many


def _edit_fallback(chat_id, message_id):
    text, _ = get_fallback_message()
    edit_message(chat_id, message_id, text, reply_markup=None)


def _extract_current_company_page(reply_markup, message_text):
    rows = (reply_markup or {}).get("inline_keyboard", [])
    for row in rows:
        for button in row:
            callback_data = button.get("callback_data", "")
            if callback_data.startswith("st:co:page:"):
                try:
                    page_number = int(callback_data.split(":")[-1])
                except ValueError:
                    continue
                if button.get("text") == "⬅️":
                    return page_number + 1
                if button.get("text") == "➡️":
                    return page_number - 1

    match = re.search(r"\((\d+)/(\d+)\)", message_text or "")
    if match:
        return max(0, int(match.group(1)) - 1)
    return 0


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


def _build_more_keyboard(offset, remaining):
    more_text = f"📬 Показать оставшиеся {remaining}" if remaining <= 10 else "📬 Ещё 10"
    return {
        "inline_keyboard": [
            [
                {"text": more_text, "callback_data": f"more:{offset}"},
                {"text": f"📦 Все ({remaining})", "callback_data": f"more:all:{offset}"},
            ],
            [{"text": "✕ Хватит", "callback_data": "more:stop"}],
        ]
    }


def _get_zero_state_text(chat_id, db, effective_filters):
    _ = effective_filters

    total_active = db.count_active_vacancies()
    if total_active == 0:
        return (
            "Сейчас на рынке нет активных вакансий. Такое бывает редко — "
            "проверю снова утром и вечером и пришлю, как только появятся."
        )

    all_undelivered = db.get_undelivered_vacancies(chat_id, limit=1)
    if not all_undelivered:
        return (
            "Ты уже видел все подходящие вакансии — молодец! "
            "Новые проверяю утром и вечером, пришлю сразу."
        )

    return (
        f"По твоим фильтрам сейчас ничего нет, но на рынке есть {total_active} активных вакансий. "
        "Попробуй расширить фильтры в /settings — может, найдётся что-то интересное."
    )


def _send_vacancies_chunk(chat_id, loader_message_id, db, filters, offset=0, chunk_size=10):
    companies_list = db.get_enabled_companies()
    companies_map = {company.get("name"): company for company in companies_list}

    undelivered = db.get_undelivered_vacancies(chat_id, limit=500)
    filtered = filter_vacancies_for_user(undelivered, filters)
    batch = filtered if chunk_size is None else filtered[:chunk_size]

    if not batch:
        try:
            delete_message(chat_id, loader_message_id)
        except Exception:
            logging.exception("Не удалось удалить лоадер перед финальным сообщением")
        send_message(
            chat_id,
            "Это все подходящие вакансии. Проверяю новые утром и вечером — пришлю сразу.\n\n"
            "Фильтры — /settings",
            reply_markup=None,
        )
        return 0, 0

    sent_ids = []
    for vacancy in batch:
        try:
            message = format_vacancy_message(vacancy, companies_map.get(vacancy.get("company"), {}))
            result = send_message(chat_id, message)
            if result:
                sent_ids.append(vacancy["id"])
        except Exception:
            logging.exception("Не удалось отправить вакансию пользователю")

    if sent_ids:
        db.mark_delivered(chat_id, sent_ids, source="onboarding")

    total = offset + len(filtered)
    sent_count = len(sent_ids)
    shown_count = offset + sent_count
    remaining = len(filtered) - sent_count

    if total > shown_count and sent_count > 0:
        if offset == 0:
            navigation_text = (
                f"Показано {shown_count} из {total}\n\n"
                "Если пока не нашёл нужное — в следующих может быть «та самая» вакансия. "
                "Я мониторю эти компании каждый день и пришлю новые, как только появятся.\n\n"
                "Что дальше?"
            )
        else:
            navigation_text = f"Показано {shown_count} из {total}"
        try:
            delete_message(chat_id, loader_message_id)
        except Exception:
            logging.exception("Не удалось удалить лоадер перед сообщением с навигацией")
        send_message(
            chat_id,
            navigation_text,
            reply_markup=_build_more_keyboard(shown_count, remaining),
        )
    else:
        try:
            delete_message(chat_id, loader_message_id)
        except Exception:
            logging.exception("Не удалось удалить лоадер перед финальным сообщением")
        send_message(
            chat_id,
            "Это все подходящие вакансии. Проверяю новые утром и вечером — пришлю сразу.\n\n"
            "Фильтры — /settings",
            reply_markup=None,
        )

    return sent_count, total


def _send_onboarding_batch(chat_id, message_id, db, filters):
    try:
        edit_message(chat_id, message_id, "⏳ Подбираю вакансии...", reply_markup=None)
        user = db.get_user(chat_id)
        effective_filters = filters if filters is not None else (user or {}).get("filters") or {}

        undelivered = db.get_undelivered_vacancies(chat_id, limit=500)
        filtered = filter_vacancies_for_user(undelivered, effective_filters)
        total = len(filtered)
        companies_count = len({vacancy.get("company") for vacancy in filtered if vacancy.get("company")})
        vacancies_word = _pluralize(total, "вакансию", "вакансии", "вакансий")
        companies_word = _pluralize(companies_count, "компании", "компаниях", "компаниях")

        if total == 0:
            zero_state_text = _get_zero_state_text(chat_id, db, effective_filters)
            edit_message(chat_id, message_id, zero_state_text, reply_markup=None)
            return

        if total <= 5:
            prompt = (
                f"Нашёл {total} {vacancies_word}.\n\n"
                "Это узкий срез рынка — мониторю компании каждый день и пришлю новые, как только появятся.\n\n"
                "Ненужные компании можно отключить в /settings"
            )
            keyboard = {"inline_keyboard": [[{"text": "📬 Показать", "callback_data": "more:0"}]]}
        else:
            prompt = (
                f"Нашёл {total} {vacancies_word} в {companies_count} {companies_word}.\n\n"
                "Сейчас показываю по дате — от свежих к старым. Умная сортировка и фильтрация шума — очень скоро!\n\n"
                "Ненужные компании можно отключить в /settings"
            )
            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "📬 Показать первые 10", "callback_data": "more:0"},
                        {"text": "⚙️ Изменить фильтры", "callback_data": "st:menu"},
                    ]
                ]
            }

        edit_message(
            chat_id,
            message_id,
            prompt,
            reply_markup=keyboard,
        )
    except Exception:
        logging.exception("Ошибка при подготовке выдачи вакансий")
        edit_message(
            chat_id,
            message_id,
            "Произошла ошибка при загрузке вакансий. Попробуй позже или нажми /settings",
            reply_markup=None,
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
    if current_step not in {"grade", "city", "work_format"}:
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
    if next_step == "confirm":
        edit_message(chat_id, message_id, "⏳ Применяю настройки...", reply_markup=None)

    db.update_user_filters(chat_id, next_filters)
    db.update_onboarding_step(chat_id, next_step)

    text, next_markup = get_step_message(next_step, next_filters, companies_list=companies_list)
    edit_message(chat_id, message_id, text, reply_markup=next_markup)


def handle_start(chat_id, username, db=None):
    db = db or SupabaseService()
    user = db.get_user(chat_id)

    if user is None or user.get("is_active") is False:
        db.upsert_user(chat_id, username, bot_id="main")
        db.set_user_paused(chat_id, False)
        db.update_user_filters(chat_id, {})
        db.update_onboarding_step(chat_id, "welcome")

        text, reply_markup = get_welcome_message()
        send_message(chat_id, text, reply_markup=reply_markup)
        return

    was_paused = bool(user.get("paused"))

    db.upsert_user(chat_id, username, bot_id="main")
    db.set_user_paused(chat_id, False)

    if user.get("onboarding_step") is not None:
        text, reply_markup = get_continue_message()
        send_message(chat_id, text, reply_markup=reply_markup)
        if was_paused:
            send_message(chat_id, "Рассылка возобновлена — новые вакансии придут в ближайшую проверку.")
        return

    text, reply_markup = get_hub_message(user)
    send_message(chat_id, text, reply_markup=reply_markup)
    if was_paused:
        send_message(chat_id, "Рассылка возобновлена — новые вакансии придут в ближайшую проверку.")


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
        if callback_value == "any":
            user = db.get_user(chat_id)
            current_filters = dict((user.get("filters") or {})) if user else {}
            current_filters["cities"] = []
            db.update_user_filters(chat_id, current_filters)
            db.update_onboarding_step(chat_id, "work_format")
            text, step_markup = get_step_message("work_format", current_filters)
            edit_message(chat_id, message_id, text, reply_markup=step_markup)
            return

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
        db.update_onboarding_step(chat_id, previous_step)
        text, step_markup = get_step_message(previous_step, current_filters)
        edit_message(chat_id, message_id, text, reply_markup=step_markup)
        return

    if data == "ob:done":
        text, disclaimer_markup = get_disclaimer_message()
        edit_message(chat_id, message_id, text, reply_markup=disclaimer_markup)
        return

    if data == "ob:strict:off":
        user = db.get_user(chat_id) or {}
        filters = dict(user.get("filters") or {})
        filters["strict_mode"] = False
        db.update_user_filters(chat_id, filters)
        db.update_onboarding_step(chat_id, None)
        _send_onboarding_batch(chat_id, message_id, db, filters=filters)
        return

    if data == "ob:strict:on":
        user = db.get_user(chat_id) or {}
        filters = dict(user.get("filters") or {})
        filters["strict_mode"] = True
        db.update_user_filters(chat_id, filters)
        db.update_onboarding_step(chat_id, None)
        _send_onboarding_batch(chat_id, message_id, db, filters=filters)
        return

    if data == "ob:restart":
        db.update_user_filters(chat_id, {})
        db.update_onboarding_step(chat_id, "grade")
        text, step_markup = get_step_message("grade", {})
        edit_message(chat_id, message_id, text, reply_markup=step_markup)
        return

    if data.startswith("ob:"):
        _edit_fallback(chat_id, message_id)


def handle_hub_callback(data, chat_id, message_id, callback_message, db=None):
    db = db or SupabaseService()

    if data == "hub:vacancies":
        _send_onboarding_batch(chat_id, message_id, db, filters=None)
        return

    if data == "hub:settings":
        user = db.get_user(chat_id)
        if not user:
            edit_message(chat_id, message_id, "Сначала подпишись через /start", reply_markup=None)
            return

        text, reply_markup = get_settings_menu(user)
        edit_message(chat_id, message_id, text, reply_markup=reply_markup)
        return

    if data == "hub:continue":
        user = db.get_user(chat_id)
        if not user:
            edit_message(chat_id, message_id, "Сначала подпишись через /start", reply_markup=None)
            return

        step = user.get("onboarding_step")
        if step is None:
            text, reply_markup = get_hub_message(user)
            edit_message(chat_id, message_id, text, reply_markup=reply_markup)
            return

        if step == "welcome":
            text, reply_markup = get_welcome_message()
            edit_message(chat_id, message_id, text, reply_markup=reply_markup)
            return

        text, reply_markup = get_step_message(step, user.get("filters") or {})
        edit_message(chat_id, message_id, text, reply_markup=reply_markup)
        return

    if data == "hub:reset":
        db.update_user_filters(chat_id, {})
        db.update_onboarding_step(chat_id, "grade")
        db.clear_delivery_history(chat_id)
        text, reply_markup = get_step_message("grade", {})
        edit_message(chat_id, message_id, text, reply_markup=reply_markup)
        return

    if data.startswith("hub:"):
        _edit_fallback(chat_id, message_id)


def handle_more_callback(data, chat_id, message_id, callback_message, db=None):
    db = db or SupabaseService()

    if data == "more:stop":
        user = db.get_user(chat_id) or {}
        filters = user.get("filters") or {}
        undelivered = db.get_undelivered_vacancies(chat_id, limit=500)
        filtered = filter_vacancies_for_user(undelivered, filters)
        remaining_ids = [vacancy.get("id") for vacancy in filtered if vacancy.get("id")]
        db.mark_announced(chat_id, remaining_ids)
        edit_message(
            chat_id,
            message_id,
            "Остальные пришлю в ближайшей рассылке — проверяю утром и вечером.\n\n"
            "Ещё вакансии — /settings",
            reply_markup=None,
        )
        return

    if not data.startswith("more:"):
        return

    try:
        is_all = False
        if data.startswith("more:all:"):
            offset = int(data.split(":", 2)[2])
            is_all = True
        else:
            offset = int(data.split(":", 1)[1])
    except (ValueError, IndexError):
        edit_message(chat_id, message_id, "Не удалось обработать запрос. Попробуй ещё раз через /settings", reply_markup=None)
        return

    try:
        edit_message(chat_id, message_id, "⏳ Загружаю...", reply_markup=None)
        user = db.get_user(chat_id) or {}
        filters = user.get("filters") or {}
        chunk_size = None if is_all else 10
        _send_vacancies_chunk(chat_id, message_id, db, filters, offset=offset, chunk_size=chunk_size)
    except Exception:
        logging.exception("Ошибка при обработке more callback")
        edit_message(
            chat_id,
            message_id,
            "Произошла ошибка при загрузке вакансий. Попробуй позже или нажми /settings",
            reply_markup=None,
        )


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

        if data == "st:c:any":
            user = db.get_user(chat_id)
            merged = dict(user.get("filters") or {}) if user else {}
            merged["cities"] = []
            db.update_user_filters(chat_id, merged)
            refreshed_user = db.get_user(chat_id) or {}
            text, menu_markup = get_settings_menu(refreshed_user)
            edit_message(chat_id, message_id, text, reply_markup=menu_markup)
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
        if step == "company" and callback_value.startswith("page:"):
            try:
                page = int(callback_value.split(":", 1)[1])
            except ValueError:
                _edit_fallback(chat_id, message_id)
                return

            user = db.get_user(chat_id) or {}
            filters = user.get("filters") or {}
            companies_list = db.get_enabled_companies()
            text, step_markup = get_company_page(companies_list, filters, page=page)
            edit_message(chat_id, message_id, text, reply_markup=step_markup)
            return

        if step == "company":
            rows = (reply_markup or {}).get("inline_keyboard", [])
            company_name_by_slug = {}
            is_active_company = None

            for row in rows:
                for button in row:
                    callback_data = button.get("callback_data", "")
                    if not callback_data.startswith("st:co:"):
                        continue

                    company_slug = callback_data.split(":", 2)[2]
                    if company_slug.startswith("page:"):
                        continue

                    button_text = button.get("text", "")
                    company_name = button_text.split(" ", 1)[1].strip() if " " in button_text else button_text.strip()
                    company_name_by_slug[company_slug] = company_name

                    if company_slug == callback_value:
                        if button_text.startswith("🟢"):
                            is_active_company = True
                        elif button_text.startswith("🔴"):
                            is_active_company = False

            company_name = company_name_by_slug.get(callback_value)
            if not company_name or is_active_company is None:
                _edit_fallback(chat_id, message_id)
                return

            user = db.get_user(chat_id) or {}
            merged = dict(user.get("filters") or {})
            excluded_companies = [str(v).strip() for v in (merged.get("excluded_companies") or []) if str(v).strip()]

            if is_active_company:
                excluded_companies.append(company_name)
            else:
                excluded_companies = [name for name in excluded_companies if name != company_name]

            merged["excluded_companies"] = sorted(set(excluded_companies), key=lambda name: name.lower())
            db.update_user_filters(chat_id, merged)

            toggled_markup = toggle_selection(
                "company",
                reply_markup,
                callback_value,
                all_company_names=None,
                prefix="st",
            )
            edit_message(
                chat_id,
                message_id,
                (callback_message or {}).get("text", "⚙️ Компании"),
                reply_markup=toggled_markup,
            )
            return

        toggled_markup = toggle_selection(
            step,
            reply_markup,
            callback_value,
            all_company_names=None,
            prefix="st",
        )

        current_filters = parse_selections_from_markup(
            step,
            toggled_markup,
            companies_list=None,
            prefix="st",
        )
        text, next_markup = get_settings_step(step, current_filters, companies_list=None)
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

        if step == "company":
            refreshed_user = db.get_user(chat_id) or {}
            text, menu_markup = get_settings_menu(refreshed_user)
            edit_message(chat_id, message_id, text, reply_markup=menu_markup)
            return

        merged = dict(user.get("filters") or {})
        fragment = parse_selections_from_markup(step, reply_markup, companies_list=None, prefix="st")
        merged.update(fragment)
        db.update_user_filters(chat_id, merged)

        refreshed_user = db.get_user(chat_id) or {}
        text, menu_markup = get_settings_menu(refreshed_user)
        edit_message(chat_id, message_id, text, reply_markup=menu_markup)
        return

    if data == "st:deliver":
        _send_onboarding_batch(chat_id, message_id, db, filters=None)
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
        emoji = format_company_emoji(company_meta)
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


def handle_mute(chat_id, slug, db=None):
    db = db or SupabaseService()
    companies = db.get_enabled_companies()
    company = next((item for item in companies if item.get("slug") == slug), None)
    if not company:
        send_message(chat_id, "Компания не найдена.")
        return

    name = company.get("name")
    user = db.get_user(chat_id) or {}
    filters = dict(user.get("filters") or {})
    excluded_companies = [str(v).strip() for v in (filters.get("excluded_companies") or []) if str(v).strip()]
    if name in excluded_companies:
        send_message(chat_id, f"{name} уже заблокирована. Список: /blocked")
        return

    send_message(
        chat_id,
        f"Заблокировать вакансии от {name}?",
        reply_markup={
            "inline_keyboard": [[
                {"text": "Да, заблокировать", "callback_data": f"mute:{slug}:yes"},
                {"text": "Отмена", "callback_data": f"mute:{slug}:no"},
            ]]
        },
    )


def handle_unmute(chat_id, slug, db=None):
    db = db or SupabaseService()
    companies = db.get_enabled_companies()
    company = next((item for item in companies if item.get("slug") == slug), None)
    if not company:
        send_message(chat_id, "Компания не найдена.")
        return

    name = company.get("name")
    user = db.get_user(chat_id) or {}
    filters = dict(user.get("filters") or {})
    excluded_companies = [str(v).strip() for v in (filters.get("excluded_companies") or []) if str(v).strip()]
    if name not in excluded_companies:
        send_message(chat_id, f"{name} не заблокирована.")
        return

    send_message(
        chat_id,
        f"Разблокировать вакансии от {name}?",
        reply_markup={
            "inline_keyboard": [[
                {"text": "Да, разблокировать", "callback_data": f"unmute:{slug}:yes"},
                {"text": "Отмена", "callback_data": f"unmute:{slug}:no"},
            ]]
        },
    )


def handle_unmute_all(chat_id, db=None):
    db = db or SupabaseService()
    user = db.get_user(chat_id) or {}
    filters = dict(user.get("filters") or {})
    excluded_companies = [str(v).strip() for v in (filters.get("excluded_companies") or []) if str(v).strip()]
    if not excluded_companies:
        send_message(chat_id, "У тебя нет заблокированных компаний.")
        return

    send_message(
        chat_id,
        f"Разблокировать все компании ({len(excluded_companies)} шт.)?",
        reply_markup={
            "inline_keyboard": [[
                {"text": "Да, разблокировать все", "callback_data": "unmute_all:yes"},
                {"text": "Отмена", "callback_data": "unmute_all:no"},
            ]]
        },
    )


def handle_blocked(chat_id, db=None):
    db = db or SupabaseService()
    user = db.get_user(chat_id) or {}
    filters = dict(user.get("filters") or {})
    excluded_companies = [str(v).strip() for v in (filters.get("excluded_companies") or []) if str(v).strip()]
    if not excluded_companies:
        send_message(chat_id, "У тебя нет заблокированных компаний.")
        return

    companies = db.get_enabled_companies()
    companies_by_name = {company.get("name"): company for company in companies}

    lines = ["Заблокированные компании:", ""]
    for name in excluded_companies:
        company_meta = companies_by_name.get(name)
        if not company_meta:
            continue
        slug = company_meta.get("slug")
        if not slug:
            continue
        emoji = format_company_emoji(company_meta)
        lines.append(f"{emoji} {name}")
        lines.append(f"  └ /unmute_{slug}")

    if len(lines) == 2:
        send_message(chat_id, "У тебя нет заблокированных компаний.")
        return

    lines.append("")
    lines.append("/unmute_all — разблокировать все")
    send_message(
        chat_id,
        "\n".join(lines),
        reply_markup={"inline_keyboard": [[{"text": "Управлять компаниями", "callback_data": "st:edit:company"}]]},
    )


def handle_mute_callback(data, chat_id, message_id, db=None):
    db = db or SupabaseService()

    if data.startswith("mute:"):
        _, slug, action = data.split(":", 2)
        if action == "no":
            edit_message(chat_id, message_id, "Ок, ничего не меняю.", reply_markup=None)
            return

        companies = db.get_enabled_companies()
        company = next((item for item in companies if item.get("slug") == slug), None)
        if not company:
            edit_message(chat_id, message_id, "Компания не найдена.", reply_markup=None)
            return

        name = company.get("name")
        user = db.get_user(chat_id) or {}
        filters = dict(user.get("filters") or {})
        excluded_companies = [str(v).strip() for v in (filters.get("excluded_companies") or []) if str(v).strip()]
        if name not in excluded_companies:
            excluded_companies.append(name)
        filters["excluded_companies"] = excluded_companies

        has_used_mute = bool(filters.get("has_used_mute"))
        if not has_used_mute:
            filters["has_used_mute"] = True

        db.update_user_filters(chat_id, filters)

        if not has_used_mute:
            text = (
                f"Готово, вакансии от {name} больше не будут приходить.\n\n"
                "Управлять компаниями можно в /settings.\n"
                "Заблокированные: /blocked"
            )
        else:
            text = f"Готово, {name} заблокирована.\n\nЗаблокированные: /blocked"

        edit_message(
            chat_id,
            message_id,
            text,
            reply_markup={
                "inline_keyboard": [[
                    {"text": "Заблокировать другие компании", "callback_data": "st:edit:company"}
                ]]
            },
        )
        return

    if data.startswith("unmute:"):
        _, slug, action = data.split(":", 2)
        if action == "no":
            edit_message(chat_id, message_id, "Ок, ничего не меняю.", reply_markup=None)
            return

        companies = db.get_enabled_companies()
        company = next((item for item in companies if item.get("slug") == slug), None)
        if not company:
            edit_message(chat_id, message_id, "Компания не найдена.", reply_markup=None)
            return

        name = company.get("name")
        user = db.get_user(chat_id) or {}
        filters = dict(user.get("filters") or {})
        excluded_companies = [str(v).strip() for v in (filters.get("excluded_companies") or []) if str(v).strip()]
        filters["excluded_companies"] = [company_name for company_name in excluded_companies if company_name != name]
        db.update_user_filters(chat_id, filters)

        edit_message(
            chat_id,
            message_id,
            f"Готово, вакансии от {name} снова будут приходить.\n\nЗаблокированные: /blocked",
            reply_markup={
                "inline_keyboard": [[
                    {"text": f"📬 Показать вакансии от {name}", "callback_data": "st:deliver"}
                ]]
            },
        )
        return

    if data.startswith("unmute_all:"):
        _, action = data.split(":", 1)
        if action == "no":
            edit_message(chat_id, message_id, "Ок, ничего не меняю.", reply_markup=None)
            return

        user = db.get_user(chat_id) or {}
        filters = dict(user.get("filters") or {})
        filters["excluded_companies"] = []
        db.update_user_filters(chat_id, filters)
        edit_message(
            chat_id,
            message_id,
            "Все компании разблокированы.",
            reply_markup={
                "inline_keyboard": [[
                    {"text": "📬 Показать вакансии", "callback_data": "st:deliver"}
                ]]
            },
        )


def handle_unknown(chat_id):
    send_message(
        chat_id,
        "Вот что я умею:\n\n"
        "/settings — настроить фильтры вакансий\n"
        "/stats — статистика по рынку\n"
        "/start — начать сначала\n"
        "/stop — отписаться от рассылки\n"
        "/blocked — заблокированные компании\n\n"
        "Новые вакансии приходят автоматически — утром и вечером.",
    )
