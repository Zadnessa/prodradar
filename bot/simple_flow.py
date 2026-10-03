"""Короткое знакомство и общая лента project/bizdev для test-бота."""

from html import escape

from bot.telegram_api import send_message, edit_message, build_main_reply_keyboard
from bot.onboarding import GRADE_OPTIONS
from database.supabase_client import SupabaseService
from delivery.filters import filter_vacancies_for_user
from delivery.ranking import rank_vacancies
from delivery.telegram import format_vacancy_message

PAGE_SIZE = 8
ONBOARDING_STEP = "simple_grade"
COMPLETED_KEY = "simple_onboarding_completed"
GREETING_KEY = "simple_greeting_shown"


def onboarding_completed(user):
    return bool(((user or {}).get("filters") or {}).get(COMPLETED_KEY))


def show_onboarding(chat_id, db=None, message_id=None, *, greet=False):
    db = db or SupabaseService()
    user = db.get_user(chat_id) or {}
    selected = effective_filters(user.get("filters"))["grades"]
    text = ("Какие грейды показывать? Можно выбрать несколько или посмотреть все. "
            "Если грейд не указан, вакансию тоже покажу — вдруг там что-то интересное.\n\n"
            "Потом всё можно поменять в настройках. Компании, которые не подходят, можно скрыть.")
    if greet:
        text = ("Привет, Катюша! :-)\n\n"
                "Собрал проекты и развитие бизнеса в одну ленту. "
                "Не нужно выбирать что-то одно.\n\n") + text
    rows = [[{"text": ("✓ " if grade in selected else "") + grade,
              "callback_data": f"sm:onboard:grade:{index}"} for index, grade in enumerate(GRADE_OPTIONS)]]
    rows.extend([
        [{"text": "Поехали смотреть вакансии :-)" if selected else "Показать все грейды :-)",
          "callback_data": "sm:onboard:done", "style": "primary"}],
    ])
    if selected:
        rows.append([{"text": "Посмотреть все грейды", "callback_data": "sm:onboard:all", "style": "success"}])
    if message_id:
        return edit_message(chat_id, message_id, text, reply_markup={"inline_keyboard": rows})
    return send_message(chat_id, text, reply_markup={"inline_keyboard": rows})


def _begin_onboarding(chat_id, db):
    user = db.get_user(chat_id) or {}
    filters = dict(user.get("filters") or {})
    # Старый незавершённый онбординг тоже уже показывал приветствие.
    greet = not (filters.get(GREETING_KEY) or onboarding_completed(user) or
                 user.get("onboarding_step") == ONBOARDING_STEP)
    if not filters.get(GREETING_KEY):
        filters[GREETING_KEY] = True
        db.update_user_filters(chat_id, filters)
    db.update_onboarding_step(chat_id, ONBOARDING_STEP)
    return show_onboarding(chat_id, db, greet=greet)


def effective_filters(filters):
    # Старые города/компании/strict не должны незаметно сужать новый поиск.
    return {"grades": (filters or {}).get("grades") or [],
            "excluded_companies": (filters or {}).get("excluded_companies") or []}


def _all_available(db, chat_id, include_delivered=False):
    result = []
    while True:
        page = (db.get_active_vacancies_for_filter_check(limit=1000, offset=len(result)) if include_delivered
                else db.get_undelivered_vacancies(chat_id, limit=1000, offset=len(result)))
        result.extend(page)
        if len(page) < 1000:
            return result


def show_vacancies(chat_id, db=None, family="all", include_delivered=False, offset=0):
    db = db or SupabaseService()
    user = db.get_user(chat_id) or {}
    if not onboarding_completed(user):
        return _begin_onboarding(chat_id, db)
    filters = effective_filters(user.get("filters"))
    companies = {c["name"]: c for c in db.get_enabled_companies()}
    # Старые кнопки направлений открывают ту же общую ленту.
    available = [v for v in _all_available(db, chat_id, include_delivered) if set(v.get("role_families") or []) & {"project", "bizdev"}
                 and v.get("company") in companies]
    vacancies = rank_vacancies(filter_vacancies_for_user(available, filters), filters["grades"])
    delivered = []
    for vacancy in vacancies[offset:offset + PAGE_SIZE]:
        text = format_vacancy_message(vacancy, companies.get(vacancy.get("company"), {}),
                                      chat_id=chat_id, source="simple")
        result = send_message(chat_id, text)
        # Отмечаем каждую успешно отправленную карточку до следующей API операции.
        if result is None:
            return delivered
        if not include_delivered:
            db.mark_delivered(chat_id, [vacancy["id"]], source="simple")
        delivered.append(vacancy["id"])
    rows = []
    remaining = max(len(vacancies) - offset - len(delivered), 0)
    if remaining:
        callback = f"sm:seen:all:{offset + PAGE_SIZE}" if include_delivered else "sm:more:all"
        rows.append([{"text": f"Ещё вакансии ({remaining})", "callback_data": callback, "style": "primary"}])
    if not vacancies and not include_delivered:
        rows.append([{"text": "Посмотреть текущие ещё раз", "callback_data": "sm:seen:all:0", "style": "primary"}])
    rows.append([{"text": "Настройки", "callback_data": "sm:settings", "style": "success"}])
    if not vacancies:
        text = "Непросмотренных вакансий по этим настройкам пока нет :-)"
        if filters["grades"]:
            text += " Можно изменить грейды в настройках."
    else:
        text = f"Ещё вакансий: {len(delivered)} :-) " + (f"Осталось: {remaining}." if remaining else "На сегодня всё в этой подборке.")
    send_message(chat_id, text, reply_markup={"inline_keyboard": rows})
    db.log_event(chat_id, "simple_vacancies_shown", {"family": "all", "delivered": len(delivered), "remaining": remaining})
    return delivered


def show_settings(chat_id, db=None, message_id=None):
    db = db or SupabaseService()
    user = db.get_user(chat_id) or {}
    filters = effective_filters(user.get("filters"))
    selected = filters["grades"]
    paused = bool(user.get("paused"))
    text = "<b>Настройки</b>\nГрейды: " + escape(", ".join(selected) if selected else "все")
    text += "\nВакансии без указанного грейда тоже показываются.\nСкрытых компаний: " + str(len(filters["excluded_companies"]))
    text += "\nРассылка: " + ("на паузе" if paused else "включена")
    rows = [[{"text": ("✓ " if grade in selected else "") + grade, "callback_data": f"sm:grade:{index}"}
             for index, grade in enumerate(GRADE_OPTIONS)]]
    rows.extend([
        [{"text": "Все грейды", "callback_data": "sm:grades:all", "style": "success"}],
        [{"text": "Скрытые компании", "callback_data": "sm:blocked"}],
        [{"text": "Возобновить рассылку" if paused else "Пауза рассылки", "callback_data": "sm:pause"}],
        [{"text": "К вакансиям :-)", "callback_data": "sm:more:all", "style": "primary"}],
    ])
    if message_id:
        edit_message(chat_id, message_id, text, reply_markup={"inline_keyboard": rows})
    else:
        send_message(chat_id, text, reply_markup={"inline_keyboard": rows})


def show_blocked(chat_id, db=None):
    db = db or SupabaseService()
    excluded = effective_filters((db.get_user(chat_id) or {}).get("filters"))["excluded_companies"]
    companies = {c["name"]: c for c in db.get_enabled_companies()}
    rows = [[{"text": f"Вернуть {name}", "callback_data": f"sm:unmute:{companies[name]['slug']}"}]
            for name in excluded if name in companies and companies[name].get("slug")]
    rows.append([{"text": "Настройки", "callback_data": "sm:settings", "style": "primary"}])
    send_message(chat_id, "Скрытые компании: " + escape(", ".join(excluded) if excluded else "нет"),
                 reply_markup={"inline_keyboard": rows})


def handle_simple_callback(data, chat_id, message_id, db=None):
    db = db or SupabaseService()
    if data.startswith("sm:onboard:"):
        user = db.get_user(chat_id) or {}
        if onboarding_completed(user):
            return show_settings(chat_id, db, message_id)
        filters = dict(user.get("filters") or {})
        if data.startswith("sm:onboard:grade:"):
            index = data.rsplit(":", 1)[-1]
            if not index.isdigit() or int(index) >= len(GRADE_OPTIONS):
                return
            grade = GRADE_OPTIONS[int(index)]
            grades = list(filters.get("grades") or [])
            grades.remove(grade) if grade in grades else grades.append(grade)
            filters["grades"] = grades
            db.update_user_filters(chat_id, filters)
            return show_onboarding(chat_id, db, message_id)
        if data not in {"sm:onboard:done", "sm:onboard:all"}:
            return
        if data == "sm:onboard:all":
            filters["grades"] = []
        filters[COMPLETED_KEY] = True
        db.update_user_filters(chat_id, filters)
        db.update_onboarding_step(chat_id, None)
        edit_message(chat_id, message_id, "Поехали! :-)\nПроекты и развитие бизнеса — в одной ленте.")
        send_message(chat_id, "В каждой карточке — прямая ссылка на вакансию. "
                     "Неподходящую компанию можно скрыть командой под карточкой.",
                     reply_markup=build_main_reply_keyboard())
        return show_vacancies(chat_id, db)
    if data.startswith("sm:seen:"):
        parts = data.split(":")
        if len(parts) == 4 and parts[3].isdigit():
            return show_vacancies(chat_id, db, parts[2], include_delivered=True, offset=int(parts[3]))
        return
    if data.startswith("sm:more:"):
        return show_vacancies(chat_id, db, data.split(":", 2)[2])
    if data in {"more:0", "st:deliver"} or data.startswith(("more:", "hub:", "ob:")):
        return show_vacancies(chat_id, db)
    if data in {"sm:blocked", "st:edit:company", "st:blocked"}:
        return show_blocked(chat_id, db)
    filters = dict((db.get_user(chat_id) or {}).get("filters") or {})
    if data.startswith("sm:grade:"):
        index = data.split(":", 2)[2]
        if not index.isdigit() or int(index) >= len(GRADE_OPTIONS):
            return
        grade = GRADE_OPTIONS[int(index)]
        grades = list(filters.get("grades") or [])
        grades.remove(grade) if grade in grades else grades.append(grade)
        filters["grades"] = grades
        db.update_user_filters(chat_id, filters)
    elif data == "sm:grades:all":
        filters["grades"] = []
        db.update_user_filters(chat_id, filters)
    elif data == "sm:pause":
        user = db.get_user(chat_id) or {}
        db.set_user_paused(chat_id, not bool(user.get("paused")))
    elif data.startswith("sm:unmute:"):
        slug = data.split(":", 2)[2]
        company = next((c for c in db.get_enabled_companies() if c.get("slug") == slug), None)
        if not company:
            return
        filters["excluded_companies"] = [n for n in filters.get("excluded_companies", []) if n != company["name"]]
        db.update_user_filters(chat_id, filters)
        return show_blocked(chat_id, db)
    return show_settings(chat_id, db, message_id)


def handle_simple_message(chat_id, text, username=None, db=None, **profile):
    db = db or SupabaseService()
    if text == "/start":
        db.upsert_user(chat_id, username, **profile)
        if not onboarding_completed(db.get_user(chat_id)):
            return _begin_onboarding(chat_id, db)
        send_message(chat_id, "Открываю вакансии :-)",
                     reply_markup=build_main_reply_keyboard())
        return show_vacancies(chat_id, db)
    if text in {"/settings", "Настройки"}:
        return show_settings(chat_id, db)
    if text in {"/pause", "/stop"}:
        db.set_user_paused(chat_id, True)
        send_message(chat_id, "Рассылка на паузе. Смотреть вакансии можно по кнопке; возобновить — в настройках.",
                     reply_markup=build_main_reply_keyboard())
        return
    if text == "/blocked":
        return show_blocked(chat_id, db)
    if text.startswith(("/mute_", "/unmute_")) or text == "/unmute_all":
        from bot.handlers import handle_mute, handle_unmute, handle_unmute_all
        if text == "/unmute_all":
            return handle_unmute_all(chat_id, db=db)
        if text.startswith("/unmute_"):
            return handle_unmute(chat_id, text[len("/unmute_"):], db=db)
        return handle_mute(chat_id, text[len("/mute_"):], db=db)
    if text in {"Вакансии", "/vacancies"}:
        return show_vacancies(chat_id, db)
    if not onboarding_completed(db.get_user(chat_id)):
        return _begin_onboarding(chat_id, db)
    return send_message(chat_id, "Продолжить просмотр — «Вакансии» :-) "
                        "В «Настройках» можно поменять грейды и вернуть скрытые компании.",
                        reply_markup=build_main_reply_keyboard())
