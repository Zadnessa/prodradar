"""Обработка команд Telegram-бота."""

import os

import requests

import config
from database.supabase_client import SupabaseService


def _send_text(chat_id, text, bot_id="main"):
    token = os.getenv(config.BOTS[bot_id]["token_env"], "")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=20).raise_for_status()


def handle_start(chat_id, username, db=None):
    db = db or SupabaseService()
    db.upsert_user(chat_id, username, bot_id="main")
    text = (
        "👋 Привет! Я бот Vacancy Radar.\n\n"
        "Я слежу за вакансиями Product Manager в крупных IT-компаниях и присылаю новые каждый день в 10:00 и 19:00.\n\n"
        "Компании: Wildberries, Yandex, Ozon, T-Bank, VK, Avito, Sber, Alfa-Bank.\n\n"
        "Чтобы отписаться, отправь /stop"
    )
    _send_text(chat_id, text)


def handle_stop(chat_id, db=None):
    db = db or SupabaseService()
    db.deactivate_user(chat_id)
    _send_text(chat_id, "Ты отписался от рассылки. Чтобы подписаться снова — отправь /start")


def handle_unknown(chat_id):
    _send_text(chat_id, "Я пока умею только /start и /stop. Новые вакансии приходят автоматически в 10:00 и 19:00.")
