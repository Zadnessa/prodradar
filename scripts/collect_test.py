"""Ручной сбор только в отдельную БД и только для @ProdRadar_bot."""

import argparse
import asyncio
import logging
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot.telegram_api import _post
from database.supabase_client import SupabaseService
from main import run


ORIGINAL_PROJECT_REF = "ykbtejjedefibdgyfgov"


def check_target(project_ref):
    if not project_ref or project_ref == ORIGINAL_PROJECT_REF:
        raise ValueError("Исходная БД запрещена для тестового сбора")
    if os.getenv("SUPABASE_URL", "").rstrip('/') != f"https://{project_ref}.supabase.co":
        raise ValueError("SUPABASE_URL не совпадает с ожидаемой отдельной БД")
    identity = _post("getMe", {}, allow_retry=False)
    if not identity or identity.get("username") != "ProdRadar_bot":
        raise ValueError("Тестовый сбор разрешён только для @ProdRadar_bot")
    admin_chat_id = int(os.environ["ADMIN_CHAT_ID"])
    db = SupabaseService()
    # Сканируем и неактивных: перенос старых пользователей в тест недопустим.
    offset = 0
    while True:
        result = db.client.table("users").select("chat_id").range(offset, offset + 999).execute()
        users = result.data or []
        if any(row["chat_id"] != admin_chat_id for row in users):
            raise ValueError("В тестовой БД найдены пользователи кроме администратора")
        if len(users) < 1000:
            break
        offset += 1000


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-ref", required=True)
    args = parser.parse_args()
    if os.getenv("PRODRADAR_PROFILE") != "test":
        print("Запустите сбор через scripts/run_profile.py --profile test collect")
        return 1
    # До проверки нельзя вызывать run(): он сохраняет вакансии и отправляет сообщения.
    logging.disable(logging.CRITICAL)
    try:
        check_target(args.project_ref)
    except Exception as exc:
        print(f"Тестовый сбор остановлен до записи и рассылки: {type(exc).__name__}")
        return 1
    logging.disable(logging.NOTSET)
    asyncio.run(run())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
