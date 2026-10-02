"""Сразу вакансии: project — основной поиск, bizdev — запасной вариант."""

from html import escape

from bot.telegram_api import send_message, edit_message, build_main_reply_keyboard
from bot.onboarding import GRADE_OPTIONS
from database.supabase_client import SupabaseService
from delivery.filters import filter_vacancies_for_user
from delivery.ranking import rank_vacancies
from delivery.telegram import format_vacancy_message

PAGE_SIZE = 8


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


def show_vacancies(chat_id, db=None, family="project", include_delivered=False, offset=0):
    db = db or SupabaseService()
    if family not in {"project", "bizdev"}:
        family = "project"
    user = db.get_user(chat_id) or {}
    filters = effective_filters(user.get("filters"))
    companies = {c["name"]: c for c in db.get_enabled_companies()}
    available = [v for v in _all_available(db, chat_id, include_delivered) if family in (v.get("role_families") or [])
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
        callback = f"sm:seen:{family}:{offset + PAGE_SIZE}" if include_delivered else f"sm:more:{family}"
        rows.append([{"text": f"Ещё вакансии ({remaining})", "callback_data": callback}])
    if not vacancies and not include_delivered:
        rows.append([{"text": "Посмотреть текущие ещё раз", "callback_data": f"sm:seen:{family}:0"}])
    rows.append([{"text": "Запасной вариант: bizdev" if family == "project" else "К проектным вакансиям",
                  "callback_data": "sm:more:bizdev" if family == "project" else "sm:more:project"}])
    rows.append([{"text": "Настройки", "callback_data": "sm:settings"}])
    if not vacancies:
        text = "Непросмотренных проектных вакансий по текущим настройкам пока нет." if family == "project" else "Непросмотренных bizdev-вакансий по текущим настройкам пока нет."
        if filters["grades"]:
            text += " Можно изменить грейды в настройках."
    else:
        text = f"Показано: {len(delivered)}. " + (f"Осталось: {remaining}." if remaining else "Все текущие вакансии этого направления просмотрены.")
    send_message(chat_id, text, reply_markup={"inline_keyboard": rows})
    db.log_event(chat_id, "simple_vacancies_shown", {"family": family, "delivered": len(delivered), "remaining": remaining})
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
        [{"text": "Все грейды", "callback_data": "sm:grades:all"}],
        [{"text": "Скрытые компании", "callback_data": "sm:blocked"}],
        [{"text": "Возобновить рассылку" if paused else "Пауза рассылки", "callback_data": "sm:pause"}],
        [{"text": "Проектные вакансии", "callback_data": "sm:more:project"}],
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
    rows.append([{"text": "Настройки", "callback_data": "sm:settings"}])
    send_message(chat_id, "Скрытые компании: " + escape(", ".join(excluded) if excluded else "нет"),
                 reply_markup={"inline_keyboard": rows})


def handle_simple_callback(data, chat_id, message_id, db=None):
    db = db or SupabaseService()
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
        db.update_onboarding_step(chat_id, None)
        db.set_user_paused(chat_id, False)
        send_message(chat_id, "Проектные вакансии — основной поиск. Bizdev доступен как запасной вариант.",
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
    return send_message(chat_id, "Нажми «Вакансии» для проектного поиска или «Настройки» для грейдов и mute.",
                        reply_markup=build_main_reply_keyboard())
