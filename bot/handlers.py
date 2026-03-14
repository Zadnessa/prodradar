"""Обработка команд Telegram-бота."""

from bot.telegram_api import send_message
from database.supabase_client import SupabaseService


def handle_start(chat_id, username, db=None):
    db = db or SupabaseService()
    db.upsert_user(chat_id, username, bot_id="main")
    text = (
        "👋 Привет! Я бот Vacancy Radar.\n\n"
        "Я слежу за вакансиями Product Manager в крупных IT-компаниях и присылаю новые каждый день в 10:00 и 19:00.\n\n"
        "Компании: Wildberries, Yandex, Ozon, T-Bank, VK, Avito, Sber, Alfa-Bank.\n\n"
        "Чтобы отписаться, отправь /stop"
    )
    send_message(chat_id, text)


def handle_stop(chat_id, db=None):
    db = db or SupabaseService()
    db.deactivate_user(chat_id)
    send_message(chat_id, "Ты отписался от рассылки. Чтобы подписаться снова — отправь /start")


def handle_unknown(chat_id):
    send_message(chat_id, "Я пока умею только /start и /stop. Новые вакансии приходят автоматически в 10:00 и 19:00.")
