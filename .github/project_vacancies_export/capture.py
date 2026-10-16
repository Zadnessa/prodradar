"""Чтение тестового пула вакансий без записи и обращения к Telegram."""
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError

ROOT = Path(".github/project_vacancies_export/data")
ROOT.mkdir(parents=True, exist_ok=True)
url = os.environ.get("TEST_SUPABASE_URL", "").strip().rstrip("/")
key = os.environ.get("TEST_SUPABASE_KEY", "").strip()
if url != "https://jmsdxgylyjxwdwmdrmxw.supabase.co" or not key:
    raise SystemExit("Не настроен доступ к тестовой базе")
columns = "id,title,company,url,grade,city,experience,description,is_active,selection_profile,role_families,first_seen_at,last_seen_at,source_json"
def read_all():
    rows = []
    while True:
        query = urlencode({"select": columns, "order": "id.asc", "limit": 500, "offset": len(rows)})
        request = Request(url + "/rest/v1/vacancies?" + query, headers={
            "apikey": key, "Authorization": "Bearer " + key, "Accept": "application/json"})
        try:
            with urlopen(request, timeout=50) as response:
                page = json.load(response)
        except HTTPError as error:
            raise SystemExit("Supabase: HTTP " + str(error.code)) from None
        if not isinstance(page, list):
            raise SystemExit("Supabase вернул неожиданный формат")
        rows.extend(page)
        if len(page) < 500:
            return rows
def digest(rows):
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
rows = read_all()
if digest(rows) != digest(read_all()):
    raise SystemExit("Пул изменился во время чтения; слепок не сохранён")
assert len(rows) == len({str(r["id"]) for r in rows})
inventory = []
for row in rows:
    raw = row.pop("source_json", None)
    # Сохраняем только известные публичные поля текстов, без служебных данных источника.
    native = {}
    if isinstance(raw, dict):
        inventory.append({"id": row["id"], "keys": {k: {"type": type(v).__name__, "length": len(v) if isinstance(v, (str, list, dict)) else None} for k,v in raw.items()}})
        for field in ("short_summary", "duties", "key_qualifications", "additional_requirements", "conditions", "description", "responsibilities", "requirements", "about", "intro"):
            value = raw.get(field)
            if isinstance(value, str) and value.strip():
                native[field] = value
    if native:
        row["native_sections"] = native
meta = {"snapshot_at": datetime.now(timezone.utc).isoformat(), "profile": "test",
        "total": len(rows), "active": sum(bool(r["is_active"]) for r in rows),
        "profiles": sorted({str(r.get("selection_profile")) for r in rows}),
        "source_sha256": digest(rows), "database_writes": 0, "telegram_calls": 0}
(ROOT / "snapshot_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
(ROOT / "native_inventory.json").write_text(json.dumps(inventory, ensure_ascii=False), encoding="utf-8")
for number, offset in enumerate(range(0, len(rows), 30), 1):
    batch = rows[offset:offset+30]
    (ROOT / ("snapshot_%02d.json" % number)).write_text(json.dumps({"rows":batch}, ensure_ascii=False, indent=2), encoding="utf-8")
print("SNAPSHOT_META=" + json.dumps(meta, ensure_ascii=False))
