"""Догрузить описания близких/native кандидатов; без core vacancies/Telegram."""
import asyncio
from collections import Counter
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import aiohttp
from scripts.collect_test import check_target
from database.supabase_client import SupabaseService
from delivery.roles import classify, native_groups
from parsers import PARSER_REGISTRY
from parsers.browser import fetch_browser_secrets


def candidate(v):
    decision = classify(v)
    if decision['status'] in {'selected', 'review'}:
        return True
    groups = ' '.join(native_groups(v)).lower()
    return bool(re.search(r'управление[^\n]*проект|project management|руководитель проектов|продажи и развитие бизнеса|менеджер по работе с партнерами', groups))


async def review():
    db = SupabaseService()
    sources = os.getenv('REVIEW_SOURCES', '').split()
    statuses = db.client.table('source_pool_status').select('source_name,status,captured_at').execute().data
    browser = await fetch_browser_secrets()
    reports = []
    async with aiohttp.ClientSession(trust_env=True, timeout=aiohttp.ClientTimeout(total=60)) as session:
        for status in statuses:
            source = status['source_name']
            if sources and source not in sources:
                continue
            if status['status'] not in {'ready', 'empty'}:
                reports.append({'source':source, 'status':'unavailable'}); continue
            parser = PARSER_REGISTRY[source]()
            if source == 'sberhealth':
                parser._build_id = browser.get('sberhealth_build_id')
            vacancies = db.merge_role_reviews(source, db.load_source_pool(source))
            candidates = [v for v in vacancies if candidate(v)]
            enriched = []
            failures = []
            for vacancy in candidates:
                try:
                    # Intro/короткий API snippet не заменяет полный текст обязанностей.
                    if len(str(vacancy.get('description') or '')) < 1000:
                        await parser.enrich(session, vacancy)
                    enriched.append(vacancy)
                except Exception as exc:
                    failures.append({'id':vacancy['id'], 'error_type':type(exc).__name__})
            db.store_role_reviews(source, status['captured_at'], enriched)
            report = {'source':source, 'candidates':len(candidates), 'descriptions':sum(bool(v.get('description')) for v in enriched), 'failures':failures}
            reports.append(report)
            print(json.dumps(report, ensure_ascii=False), flush=True)
    print(json.dumps({'review_pool':reports}, ensure_ascii=False), flush=True)


def main():
    check_target('jmsdxgylyjxwdwmdrmxw')
    asyncio.run(review())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
