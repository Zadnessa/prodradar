"""Выгрузка таблиц через REST с пагинацией и проверкой полноты, без записи в БД."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

TABLE_KEYS = {
    "companies": "id",
    "city_mappings": "id",
    "vacancies": "id",
    "users": "chat_id",
    "user_vacancy_delivery": "id",
    "user_events": "id",
}


def backup_database(destination, url, key, page_size=1000):
    """Сохраняет полный REST-снимок; схема PostgreSQL резервируется отдельно."""
    destination = Path(destination)
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    session = requests.Session()
    session.headers.update({"apikey": key, "Authorization": f"Bearer {key}"})
    session.mount("https://", HTTPAdapter(max_retries=Retry(
        total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )))
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_url": url.rstrip("/"),
        "complete": False,
        "scope": "REST: данные и OpenAPI; без SQL-схемы, RLS, индексов и триггеров",
        "tables": {},
    }

    bounds = {}

    def selection(table):
        value = bounds.get(table)
        return {TABLE_KEYS[table]: f"lte.{value}"} if value is not None else {}

    def count(table):
        response = session.get(f"{url.rstrip('/')}/rest/v1/{table}",
                               params={"select": TABLE_KEYS[table], "limit": 1, **selection(table)},
                               headers={"Prefer": "count=exact"}, timeout=60)
        response.raise_for_status()
        return int(response.headers["Content-Range"].rsplit("/", 1)[1])

    try:
        response = session.get(f"{url.rstrip('/')}/rest/v1/", timeout=60)
        response.raise_for_status()
        schema = response.json()
        schema_path = destination / "rest-schema.json"
        schema_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n")
        schema_path.chmod(0o600)
        for table, primary_key in TABLE_KEYS.items():
            columns = list(schema["definitions"][table]["properties"])
            response = session.get(f"{url.rstrip('/')}/rest/v1/{table}", params={
                "select": primary_key, "order": f"{primary_key}.desc", "limit": 1,
            }, timeout=60)
            response.raise_for_status()
            newest = response.json()
            bounds[table] = newest[0][primary_key] if newest else None
            expected = count(table)
            path = destination / f"{table}.ndjson"
            rows = 0
            digest = hashlib.sha256()
            with path.open("xb") as output:
                path.chmod(0o600)
                while True:
                    response = session.get(f"{url.rstrip('/')}/rest/v1/{table}", params={
                        "select": ",".join(columns), "order": f"{primary_key}.asc",
                        "offset": rows, "limit": page_size, **selection(table),
                    }, timeout=60)
                    response.raise_for_status()
                    page = response.json()
                    if not isinstance(page, list):
                        raise ValueError(f"{table}: ответ не является списком")
                    if not page:
                        break
                    for row in page:
                        encoded = (json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8")
                        output.write(encoded)
                        digest.update(encoded)
                    rows += len(page)
            after = count(table)
            manifest["tables"][table] = {
                "count_before": expected, "rows": rows, "count_after": after,
                "sha256": digest.hexdigest(), "columns": columns, "upper_key": bounds[table],
            }
            print(json.dumps({"table": table, "rows": rows, "expected": expected}), flush=True)
            if rows != expected or after != expected:
                raise ValueError(f"{table}: число строк изменилось или выгрузка неполная")
        manifest["complete"] = True
        return manifest
    finally:
        manifest_path = destination / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        manifest_path.chmod(0o600)
        session.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    try:
        backup_database(args.destination, os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    except Exception as exc:
        # Не выводим exception text: HTTP-клиент может включить реквизиты запроса.
        print(json.dumps({"ok": False, "error_type": type(exc).__name__}))
        return 1
    print(json.dumps({"ok": True, "destination": str(args.destination)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
