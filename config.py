"""Конфигурация проекта Vacancy Radar."""

import os

SHOW_DESCRIPTION = False
TEST_MODE = False
TEST_LIMIT = 2

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}

BOTS = {
    "main": {
        "token_env": "TELEGRAM_BOT_TOKEN",
        "name": "Vacancy Radar",
    }
}

SBER_EXPERIENCE_MAP = {
    "4a14da73-ed71-43f0-aa42-0c5ffe5033e7": "Без опыта / Стажер",
    "07544111-3b15-475c-9980-1d0fa3d031c5": "От 1 до 3 лет",
    "7d2adf16-4635-4f0f-bf6e-f6089a702b5d": "От 3 до 6 лет",
    "17b55c6a-0559-499b-aa2c-d76559d46dc0": "От 6 лет",
}

ALFA_EXPERIENCE_MAP = {
    "custom_voc_5_entry_1": "Без опыта",
    "custom_voc_5_entry_2": "До 1 года",
    "custom_voc_5_entry_5": "От 1 до 3 лет",
    "custom_voc_5_entry_6": "От 3 до 5 лет",
    "custom_voc_5_entry_4": "От 5 лет",
}

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "")
