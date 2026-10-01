"""Проверка parse/enrich и контрактов без сохранения вакансий и рассылки."""

import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys
import time

import aiohttp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
from database.supabase_client import SupabaseService
from delivery.ranking import classify_title
from main import _diagnose_blacklist, _prepare_vacancy
from parsers import PARSER_REGISTRY
from parsers.browser import fetch_browser_secrets

VACANCY_COLUMNS = {
    "id", "company", "title", "grade", "city", "work_format", "url", "description",
    "experience", "published_at", "source_json", "is_active", "created_at", "first_seen_at",
    "last_seen_at", "notified_at", "content_hash",
}


def selected(vacancy):
    zone = classify_title(vacancy.get("title") or "")
    return zone == "exact" or bool(zone and not _diagnose_blacklist(vacancy["title"]))


async def audit_sources(names=None, enrichment_limit=2, parser_timeout=180, use_browser=True,
                        full_enrich_sources=()):
    logging.disable(logging.CRITICAL)
    db = SupabaseService()
    companies = db.get_enabled_companies()
    city_mappings = db.get_city_mappings()
    expected_companies = {c["name"] for c in companies}
    enabled = list(dict.fromkeys(c["parser_name"] for c in companies))
    requested = names or enabled
    report = {"created_at": datetime.now(timezone.utc).isoformat(), "read_only": True, "sources": {}}
    browser_secrets = {}
    if use_browser:
        try:
            browser_secrets = await asyncio.wait_for(fetch_browser_secrets(), timeout=60)
            report["browser"] = {key: bool(value) for key, value in browser_secrets.items()}
        except Exception as exc:
            report["browser"] = {"error_type": type(exc).__name__}
    semaphore = asyncio.Semaphore(3)

    async def audit(name):
        async with semaphore:
            started = time.monotonic()
            result = {"status": "failed", "http_statuses": {}}
            statuses = Counter()
            trace = aiohttp.TraceConfig()

            async def on_end(session, context, params):
                statuses[str(params.response.status)] += 1

            trace.on_request_end.append(on_end)
            parser = None
            try:
                parser = PARSER_REGISTRY[name]()
                async with aiohttp.ClientSession(trust_env=True, timeout=aiohttp.ClientTimeout(total=30),
                                                 trace_configs=[trace]) as session:
                    # Т-Банк отдаёт страницы по 10; 385 строк с безопасными паузами
                    # требуют более трёх минут, что подтверждено live audit.
                    source_timeout = max(parser_timeout, 360) if name == 'tbank' else parser_timeout
                    vacancies = await asyncio.wait_for(parser.parse(session, set(), city_mappings,
                                                       browser_secrets=browser_secrets), timeout=source_timeout)
                    issues = set()
                    for vacancy in vacancies:
                        if not vacancy.get("id") or not vacancy.get("title") or not vacancy.get("url"):
                            issues.add("missing_required_field")
                        if vacancy.get("company") not in expected_companies:
                            issues.add("unknown_company")
                        issues.update("extra_column:" + column for column in vacancy if column not in VACANCY_COLUMNS)
                    ids = [v.get("id") for v in vacancies]
                    if len(set(ids)) != len(ids):
                        issues.add("duplicate_ids")
                    product_vacancies = [v for v in vacancies if selected(v)]
                    samples = []
                    sample_limit = len(product_vacancies) if name in full_enrich_sources else enrichment_limit
                    for vacancy in product_vacancies[:sample_limit]:
                        before = dict(vacancy)
                        try:
                            await asyncio.wait_for(parser.enrich(session, vacancy), timeout=45)
                            if len(vacancy.get("description") or "") < len(before.get("description") or ""):
                                issues.add("description_shortened")
                            for field in ("grade", "city", "work_format", "experience"):
                                if before.get(field) not in (None, "", "Не указан", "не указан") and before[field] != vacancy.get(field):
                                    issues.add("overwritten:" + field)
                            _prepare_vacancy(vacancy, city_mappings)
                            samples.append({key: vacancy.get(key) for key in
                                            ("id", "title", "company", "url", "grade", "city", "work_format")})
                            samples[-1]["description_length"] = len(vacancy.get("description") or "")
                            if name == 'tbank':
                                sections = (vacancy.get('source_json') or {}).get('html_sections') or {}
                                samples[-1]['description_sections'] = sorted(sections)
                                if not sections:
                                    issues.add('missing_full_description_sections')
                            if not samples[-1]["description_length"]:
                                issues.add("missing_description")
                        except Exception as exc:
                            issues.add("enrich_error:" + type(exc).__name__)
                    result.update({"status": "contract_failed" if issues else "ready" if vacancies else "empty",
                                   "raw_count": len(vacancies), "product_count": len(product_vacancies),
                                   "issues": sorted(issues), "samples": samples})
                    if getattr(parser, "captcha_hit", False) or any(int(code) >= 400 for code in statuses):
                        result["status"] = "failed"
                    if name == "sberhealth" and not browser_secrets.get("sberhealth_build_id"):
                        result["status"] = "failed"
            except Exception as exc:
                result["error_type"] = type(exc).__name__
                if isinstance(exc, aiohttp.ClientResponseError):
                    result["http_status"] = exc.status
            result["http_statuses"] = dict(statuses)
            if name == 'tbank':
                result['api_total_count'] = getattr(parser, '_api_total_count', None)
                result['api_collected_count'] = getattr(parser, '_api_collected_count', 0)
            result["duration_seconds"] = round(time.monotonic() - started, 1)
            report["sources"][name] = result
            print(json.dumps({"source": name, **{key: value for key, value in result.items() if key != "samples"}},
                             ensure_ascii=False), flush=True)

    # HH запускается последовательно, чтобы снизить риск captcha на общем токене.
    await asyncio.gather(*(audit(name) for name in requested if not name.startswith("hh")))
    for name in requested:
        if name.startswith("hh"):
            await audit(name)
    report["ok"] = all(item["status"] in {"ready", "empty"} for item in report["sources"].values())
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--enrich-limit", type=int, default=2)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--full-enrich-sources", nargs='+', default=[],
                        help="Проверить описания всех product-вакансий указанных источников")
    args = parser.parse_args()
    report = asyncio.run(audit_sources(args.sources, args.enrich_limit, use_browser=not args.no_browser,
                                       full_enrich_sources=args.full_enrich_sources))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
