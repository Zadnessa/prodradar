"""Явные профили процесса: без наследования реквизитов другого окружения."""

import os
import sys


PROFILES = {
    "test": {
        "prefix": "TEST",
        "project_ref": "jmsdxgylyjxwdwmdrmxw",
        "bot": "ProdRadar_bot",
        "redirect": "prodradar-test.vercel.app",
    },
    "prod": {
        "prefix": "PROD",
        "project_ref": "ykbtejjedefibdgyfgov",
        "bot": "findproductjob_bot",
        "redirect": "prodradar.vercel.app",
    },
}


def select_profile(name):
    """Проверить все реквизиты и только затем переключить текущий процесс."""
    if name not in PROFILES:
        raise ValueError("Укажите профиль test или prod")
    if "config" in sys.modules:
        raise RuntimeError("Профиль должен выбираться до импорта config")
    profile = PROFILES[name]
    values = {}
    for target in ("SUPABASE_URL", "SUPABASE_KEY", "TELEGRAM_BOT_TOKEN"):
        source = f"{profile['prefix']}_{target}"
        value = os.environ.get(source, "").strip()
        if not value:
            raise ValueError(f"Не задан {source}; общие реквизиты не используются")
        values[target] = value
    if values["SUPABASE_URL"].rstrip("/") != f"https://{profile['project_ref']}.supabase.co":
        raise ValueError("БД не совпадает с выбранным профилем")
    values["SUPABASE_URL"] = values["SUPABASE_URL"].rstrip("/")
    values["REDIRECT_BASE_URL"] = profile["redirect"]
    values["PRODRADAR_PROFILE"] = name
    os.environ.update(values)
    return profile


def verify_bot(profile):
    """Identity проверяется до запуска команды, только через общий Telegram helper."""
    import logging
    from bot.telegram_api import _post

    previous = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        identity = _post("getMe", {}, allow_retry=False)
    finally:
        logging.disable(previous)
    if not identity or not identity.get("is_bot") or identity.get("username") != profile["bot"]:
        raise ValueError("Telegram identity не совпадает с выбранным профилем")
