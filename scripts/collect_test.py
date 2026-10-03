"""Сбор только в тестовую БД и для пользователей @ProdRadar_bot."""

import argparse
import asyncio
import logging
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot.telegram_api import _post
from main import run
from runtime_profiles import PROFILES


class TestTargetError(ValueError):
    """Причина остановки, которую можно вывести без раскрытия реквизитов."""


def check_target(project_ref):
    if os.getenv("PRODRADAR_PROFILE") != "test":
        raise TestTargetError("Нужен явный профиль test")
    if project_ref != PROFILES["test"]["project_ref"]:
        raise TestTargetError("Сбор разрешён только в настроенную тестовую БД")
    if os.getenv("SUPABASE_URL", "").rstrip('/') != f"https://{project_ref}.supabase.co":
        raise TestTargetError("SUPABASE_URL не совпадает с ожидаемой тестовой БД")
    identity = _post("getMe", {}, allow_retry=False)
    if not identity or not identity.get("is_bot") or identity.get("username") != PROFILES["test"]["bot"]:
        raise TestTargetError("Тестовый сбор разрешён только для @ProdRadar_bot")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-ref", required=True)
    parser.add_argument("--use-source-pool", action="store_true", help="Использовать проверенный свежий пул без повторного сбора")
    args = parser.parse_args()
    if os.getenv("PRODRADAR_PROFILE") != "test":
        print("Запустите сбор через scripts/run_profile.py --profile test collect")
        return 1
    # До проверки нельзя вызывать run(): он сохраняет вакансии и отправляет сообщения.
    logging.disable(logging.CRITICAL)
    try:
        check_target(args.project_ref)
    except TestTargetError as exc:
        print(f"Тестовый сбор остановлен до записи и рассылки: {exc}")
        return 1
    except Exception as exc:
        print(f"Тестовый сбор остановлен до записи и рассылки: {type(exc).__name__}")
        return 1
    logging.disable(logging.NOTSET)
    asyncio.run(run())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
