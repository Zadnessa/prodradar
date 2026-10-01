"""Настройка только GitHub environment prodradar-test из отдельного Actions job."""

import argparse
import base64
import json
import os
from pathlib import Path
import sys

import requests

REPOSITORY = "Zadnessa/prodradar"
ENVIRONMENT = "prodradar-test"
PROJECT_REF = "jmsdxgylyjxwdwmdrmxw"
REPOSITORY_ID = 1180065648
API = f"https://api.github.com/repos/{REPOSITORY}/environments/{ENVIRONMENT}"
VARIABLE_NAMES = {"SUPABASE_URL", "ADMIN_CHAT_ID"}
SECRET_NAMES = {"SUPABASE_KEY", "TELEGRAM_BOT_TOKEN"}


class SetupError(Exception):
    """Безопасная ошибка без реквизитов HTTP-запроса."""


def api_request(method, path, token, body=None):
    base = (f"https://api.github.com/repositories/{REPOSITORY_ID}/environments/{ENVIRONMENT}"
            if path.startswith("/secrets") else API)
    response = requests.request(
        method, base + path,
        headers={"Authorization": f"Bearer {token}",
                 "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
        json=body, timeout=30,
    )
    if not response.ok:
        raise SetupError(f"GitHub HTTP {response.status_code}; операция {method} {path}")
    return response.json() if response.content else None


def get_public_key(token):
    # Не начинаем запись до успешного чтения environment и его ключа.
    api_request("GET", "/variables", token)
    result = api_request("GET", "/secrets/public-key", token)
    return {"repository": REPOSITORY, "environment": ENVIRONMENT,
            "key_id": result["key_id"], "key": result["key"]}


def validate_settings(settings, public_key):
    if settings.get("repository") != REPOSITORY or settings.get("environment") != ENVIRONMENT:
        raise SetupError("Пакет предназначен для другого репозитория или environment")
    if settings.get("key_id") != public_key["key_id"]:
        raise SetupError("Публичный ключ GitHub изменился; требуется новый зашифрованный пакет")
    variables = settings.get("variables")
    secrets = settings.get("secrets")
    if not isinstance(variables, dict) or set(variables) != VARIABLE_NAMES:
        raise SetupError("Допустимы только SUPABASE_URL и ADMIN_CHAT_ID")
    if not isinstance(secrets, dict) or set(secrets) != SECRET_NAMES:
        raise SetupError("Допустимы только SUPABASE_KEY и TELEGRAM_BOT_TOKEN")
    if variables["SUPABASE_URL"] != f"https://{PROJECT_REF}.supabase.co":
        raise SetupError("Пакет не соответствует тестовой БД")
    try:
        admin = int(variables["ADMIN_CHAT_ID"])
        if admin <= 0:
            raise ValueError
        for value in secrets.values():
            if not isinstance(value, str) or len(base64.b64decode(value, validate=True)) <= 48:
                raise ValueError
    except (TypeError, ValueError):
        raise SetupError("Невалидный admin ID или зашифрованный секрет") from None


def apply_settings(token, settings):
    public_key = get_public_key(token)
    validate_settings(settings, public_key)
    existing = api_request("GET", "/variables", token)["variables"]
    existing_names = {row["name"] for row in existing}
    # Каждая операция идемпотентна: неполный перенос можно безопасно повторить.
    for name, encrypted in settings["secrets"].items():
        api_request("PUT", f"/secrets/{name}", token,
                    {"key_id": public_key["key_id"], "encrypted_value": encrypted})
        print(f"Секрет {name}: обновлён")
    for name, value in settings["variables"].items():
        if name in existing_names:
            api_request("PATCH", f"/variables/{name}", token, {"name": name, "value": str(value)})
        else:
            api_request("POST", "/variables", token, {"name": name, "value": str(value)})
        print(f"Переменная {name}: обновлена")
    actual = {row["name"]: row["value"] for row in api_request("GET", "/variables", token)["variables"]}
    if any(actual.get(name) != str(value) for name, value in settings["variables"].items()):
        raise SetupError("Проверка записанных переменных не прошла")
    # Метаданные подтверждают наличие; значения секретов GitHub не раскрывает.
    actual_secrets = {row["name"] for row in api_request("GET", "/secrets", token)["secrets"]}
    if not SECRET_NAMES.issubset(actual_secrets) or "HH_ACCESS_TOKEN" not in actual_secrets:
        raise SetupError("Отсутствует обязательный environment secret; выполните read-only check")
    print("Настройка prodradar-test завершена; следующим запуском проверьте реальные API")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-key", type=Path)
    parser.add_argument("--settings-env", help="Имя env с зашифрованным пакетом")
    args = parser.parse_args()
    if bool(args.export_key) == bool(args.settings_env):
        parser.error("Выберите ровно одну операцию")
    token = os.getenv("GH_TOKEN", "")
    if not token:
        print("Добавьте environment secret PRODRADAR_GITHUB_TOKEN в prodradar-test", file=sys.stderr)
        return 1
    try:
        if args.export_key:
            public_key = get_public_key(token)
            args.export_key.write_text(json.dumps(public_key, indent=2) + "\n")
            print("Публичный ключ prodradar-test получен; секретные значения не выгружаются")
        else:
            apply_settings(token, json.loads(os.environ[args.settings_env]))
    except SetupError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        # Не печатаем client exception: он может содержать токен или body.
        print(f"Настройка остановлена: {type(exc).__name__}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
