"""Проверить test-реквизиты и зашифровать их публичным ключом GitHub environment."""

import argparse
import base64
import json
import logging
import os
from pathlib import Path
import sys

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.setup_test_github import ENVIRONMENT, PROJECT_REF, REPOSITORY

VERCEL_PROJECT = "prj_3WEWtX8vujb0llpvmuA1Umovf623"
VERCEL_TEAM = "team_OIdVeiXMtcQdNxXpseWNqQtV"


def fetch_json(url, token, **params):
    response = requests.get(url, headers={"Authorization": f"Bearer {token}"},
                            params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def encrypt_settings(public_key, database_key, bot_token, admin_chat_id):
    from nacl.public import PublicKey, SealedBox
    if public_key.get("repository") != REPOSITORY or public_key.get("environment") != ENVIRONMENT:
        raise ValueError("Нужен публичный ключ prodradar-test")
    box = SealedBox(PublicKey(base64.b64decode(public_key["key"], validate=True)))
    return {"repository": REPOSITORY, "environment": ENVIRONMENT, "key_id": public_key["key_id"],
            "variables": {"SUPABASE_URL": f"https://{PROJECT_REF}.supabase.co", "ADMIN_CHAT_ID": str(admin_chat_id)},
            "secrets": {name: base64.b64encode(box.encrypt(value.encode())).decode()
                        for name, value in {"SUPABASE_KEY": database_key, "TELEGRAM_BOT_TOKEN": bot_token}.items()}}


def prepare(public_key):
    if os.getenv("PRODRADAR_PROFILE") != "test":
        raise ValueError("Выберите test через scripts/run_profile.py")
    # Берём реальные значения у их владельцев. TEST_* в Codex могут быть proxy placeholders.
    keys = fetch_json(f"https://api.supabase.com/v1/projects/{PROJECT_REF}/api-keys",
                      os.environ["SUPABASE_ACCESS_TOKEN"])
    service_keys = [row["api_key"] for row in keys if row.get("name") == "service_role"]
    if len(service_keys) != 1:
        raise ValueError("Не найден однозначный service_role тестового проекта")
    database_key = service_keys[0]
    env_list = fetch_json(f"https://api.vercel.com/v10/projects/{VERCEL_PROJECT}/env",
                          os.environ["VERCEL_TOKEN"], teamId=VERCEL_TEAM)
    candidates = [row for row in env_list["envs"]
                  if row.get("key") == "TELEGRAM_BOT_TOKEN" and "production" in row.get("target", [])
                  and not row.get("gitBranch")]
    if len(candidates) != 1:
        raise ValueError("Не найден однозначный токен тестового Vercel-проекта")
    env = fetch_json(f"https://api.vercel.com/v1/projects/{VERCEL_PROJECT}/env/{candidates[0]['id']}",
                     os.environ["VERCEL_TOKEN"], teamId=VERCEL_TEAM, decrypt="true")
    bot_token = env["value"]
    admin_chat_id = int(os.environ["ADMIN_CHAT_ID"])
    from bot.telegram_api import _post
    # Проверяем identity именно значения, которое будет зашифровано, а не placeholder.
    os.environ["TELEGRAM_BOT_TOKEN"] = bot_token
    previous = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        identity = _post("getMe", {}, allow_retry=False)
    finally:
        logging.disable(previous)
    if not identity or not identity.get("is_bot") or identity.get("username") != "ProdRadar_bot":
        raise ValueError("Реальный token не принадлежит тестовому боту")
    response = requests.get(f"https://{PROJECT_REF}.supabase.co/rest/v1/companies",
                            params={"select": "name", "limit": 1},
                            headers={"apikey": database_key, "Authorization": f"Bearer {database_key}"}, timeout=30)
    response.raise_for_status()
    return encrypt_settings(public_key, database_key, bot_token, admin_chat_id)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-key", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    try:
        settings = prepare(json.loads(args.public_key.read_text()))
        args.output.write_text(json.dumps(settings, indent=2) + "\n")
    except Exception as exc:
        print(f"Подготовка остановлена: {type(exc).__name__}", file=sys.stderr)
        return 1
    print("Пакет prodradar-test зашифрован; реальные ключи и token не записаны на диск")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
