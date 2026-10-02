"""Проверка доступов без изменения данных, webhook и отправки сообщений."""

import argparse
import json
import logging
import os
from pathlib import Path
import re
import sys

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot.telegram_api import _post
from database.supabase_client import SupabaseService


def check_environment(expected_bot="ProdRadar_bot", require_hh=False, require_vercel=False):
    # Исключения HTTP-клиентов могут содержать URL с токеном Telegram.
    logging.disable(logging.CRITICAL)
    checks = []

    def record(name, status, **details):
        checks.append({"name": name, "status": status, **details})

    required = ("SUPABASE_URL", "SUPABASE_KEY", "TELEGRAM_BOT_TOKEN", "ADMIN_CHAT_ID")
    for name in required:
        record(name, "present" if os.getenv(name) else "failed")

    if os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY"):
        try:
            db = SupabaseService()
            for table, columns in (
                ("companies", "name,slug,parser_name,is_enabled"),
                ("city_mappings", "source,raw_value,normalized"),
                ("users", "chat_id"),
                ("user_vacancy_delivery", "vacancy_id,status"),
            ):
                db.client.table(table).select(columns).limit(1).execute()
                record(f"Supabase:{table}", "ready")
            vacancies = db.client.table("vacancies").select("id", count="exact").limit(1).execute()
            descriptions = (
                db.client.table("vacancies")
                .select("id,description", count="exact")
                .not_.is_("description", "null")
                .neq("description", "")
                .limit(1)
                .execute()
            )
            record("Supabase:vacancies", "ready", count=vacancies.count)
            record("Supabase:descriptions", "ready", count=descriptions.count)
        except Exception as exc:
            record("Supabase", "failed", error_type=type(exc).__name__)

    if os.getenv("TELEGRAM_BOT_TOKEN"):
        try:
            identity = _post("getMe", {}, allow_retry=False)
            if not identity or not identity.get("is_bot"):
                record("Telegram:getMe", "failed")
            else:
                username = identity.get("username")
                record(
                    "Telegram:getMe",
                    "ready" if username == expected_bot else "failed",
                    username=username,
                    expected_username=expected_bot,
                )
            webhook = _post("getWebhookInfo", {}, allow_retry=False)
            if webhook is not None:
                record(
                    "Telegram:getWebhookInfo",
                    "ready",
                    registered=bool(webhook.get("url")),
                    pending_updates=webhook.get("pending_update_count"),
                    has_last_error=bool(webhook.get("last_error_message")),
                )
            else:
                record("Telegram:getWebhookInfo", "failed")
            if os.getenv("ADMIN_CHAT_ID"):
                chat_id = int(os.environ["ADMIN_CHAT_ID"])
                chat = _post("getChat", {"chat_id": chat_id}, allow_retry=False)
                record("Telegram:admin_chat", "ready" if chat else "failed")
        except Exception as exc:
            record("Telegram", "failed", error_type=type(exc).__name__)

    hh_token = os.getenv("HH_ACCESS_TOKEN")
    if not hh_token:
        record("HH_ACCESS_TOKEN", "failed" if require_hh else "not_configured")
    else:
        try:
            response = requests.get(
                "https://api.hh.ru/vacancies",
                params={"employer_id": "1455", "per_page": 1},
                headers={
                    "Authorization": f"Bearer {hh_token}",
                    "HH-User-Agent": "ProductRadar/1.0 (prodradar.ru)",
                },
                timeout=20,
            )
            body = response.json()
            valid = response.status_code == 200 and isinstance(body.get("items"), list)
            error_types = []
            for error in body.get("errors") or []:
                value = error.get("type") if isinstance(error, dict) else None
                if isinstance(value, str) and re.fullmatch(r"[a-zA-Z0-9_]{1,60}", value):
                    error_types.append(value)
            record("HeadHunter:vacancies", "ready" if valid else "failed",
                   http_status=response.status_code, error_types=error_types)
        except Exception as exc:
            record("HeadHunter", "failed", error_type=type(exc).__name__)

    vercel_token = os.getenv("VERCEL_TOKEN")
    if not vercel_token:
        record("VERCEL_TOKEN", "failed" if require_vercel else "not_configured")
    else:
        try:
            response = requests.get(
                "https://api.vercel.com/v9/projects/prodradar",
                params={"slug": "zadnessas-projects"},
                headers={"Authorization": f"Bearer {vercel_token}"},
                timeout=20,
            )
            project = response.json()
            valid = response.status_code == 200 and project.get("name") == "prodradar"
            record("Vercel:prodradar", "ready" if valid else "failed",
                   http_status=response.status_code)
        except Exception as exc:
            record("Vercel", "failed", error_type=type(exc).__name__)

    return {"ok": all(check["status"] != "failed" for check in checks), "checks": checks}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-bot", default="ProdRadar_bot")
    parser.add_argument("--require-hh", action="store_true")
    parser.add_argument("--require-vercel", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = check_environment(args.expected_bot, args.require_hh, args.require_vercel)
    if args.output:
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    for check in report["checks"]:
        print(json.dumps(check, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
