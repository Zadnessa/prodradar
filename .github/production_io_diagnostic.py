"""Разовая диагностика production: только метрики и системная статистика."""
import base64
from datetime import datetime, timezone
import json
import os
import re
import time
import urllib.error
import urllib.request

REF = "ykbtejjedefibdgyfgov"
URL = "https://" + REF + ".supabase.co"
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None
opener = urllib.request.build_opener(NoRedirect)
def fetch(url, headers, payload=None):
    req = urllib.request.Request(url, headers=headers,
        data=json.dumps(payload).encode() if payload is not None else None)
    try:
        with opener.open(req, timeout=20) as response:
            return {"status":response.status,"body":response.read(2_000_000).decode("utf-8")}
    except urllib.error.HTTPError as exc:
        return {"status":exc.code}
    except Exception as exc:
        return {"error":type(exc).__name__}
def emit(name, data):
    print(json.dumps({"name":name,"at":datetime.now(timezone.utc).isoformat(),"data":data},
                     ensure_ascii=False),flush=True)

emit("target",{"project_ref":REF,"database_writes":0,"telegram_calls":0})
key=os.environ.get("SUPABASE_KEY","")
configured_url=os.environ.get("SUPABASE_URL","").rstrip("/")
emit("credentials",{"project_url_matches":configured_url==URL,"service_key_present":bool(key),
                    "management_token_present":bool(os.environ.get("SUPABASE_ACCESS_TOKEN"))})

def metrics():
    if configured_url != URL or not key:
        return {"status":"not_configured"}
    auth=base64.b64encode(("service_role:"+key).encode()).decode()
    result=fetch(URL+"/customer/v1/privileged/metrics",{"Authorization":"Basic "+auth})
    body=result.pop("body","")
    if result.get("status")!=200:
        return result
    lines=[]
    for line in body.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        metric=line.split("{")[0].split(" ")[0]
        # Не сохраняем SQL, адреса клиентов и пользовательские значения меток.
        if not re.match(r"^(pg_stat_database_|pg_stat_bgwriter_|pg_stat_wal_|pg_stat_io_|pg_stat_user_tables_|pg_statio_user_tables_|pg_database_size_|pg_postmaster_|pg_settings_|node_memory_|node_vmstat_|node_disk_|node_cpu_|node_load|supabase_)",metric):
            continue
        if "query=" in line or "client_addr=" in line:
            continue
        if "pg_settings_" in metric and not any(x in metric for x in ("shared_buffers","work_mem","max_connections","effective_cache_size")):
            continue
        lines.append(line)
    return {"status":200,"series":lines}

token=os.environ.get("SUPABASE_ACCESS_TOKEN","")
if token:
    queries = {
      "database":"""select datname, numbackends, xact_commit, xact_rollback, blks_read, blks_hit,
        tup_returned,tup_fetched,tup_inserted,tup_updated,tup_deleted,temp_files,temp_bytes,
        deadlocks,blk_read_time,blk_write_time,stats_reset from pg_catalog.pg_stat_database
        where datname=pg_catalog.current_database()""",
      "tables":"""select s.schemaname,s.relname,s.seq_scan,s.seq_tup_read,s.idx_scan,s.n_live_tup,
        s.n_dead_tup,s.n_tup_ins,s.n_tup_upd,s.n_tup_del,s.last_autovacuum,s.last_autoanalyze,
        pg_catalog.pg_total_relation_size(s.relid) as total_bytes
        from pg_catalog.pg_stat_user_tables s
        order by pg_catalog.pg_total_relation_size(s.relid) desc limit 20""",
      "activity":"""select application_name,backend_type,state,wait_event_type,wait_event,count(*) as connections
        from pg_catalog.pg_stat_activity where datname=pg_catalog.current_database()
        group by application_name,backend_type,state,wait_event_type,wait_event order by connections desc limit 20""",
      "io_queries":"""select pg_catalog.md5(s.query) as fingerprint,
        case when s.query ~* '^\\s*insert' then 'INSERT' when s.query ~* '^\\s*update' then 'UPDATE'
        when s.query ~* '^\\s*delete' then 'DELETE' else 'SELECT/other' end as operation,
        pg_catalog.concat_ws(',',case when s.query ilike '%user_events%' then 'user_events' end,
        case when s.query ilike '%vacancies%' then 'vacancies' end,
        case when s.query ilike '%source_pool%' then 'source_pool' end,
        case when s.query ilike '%users%' then 'users' end,
        case when s.query ilike '%user_vacancy_delivery%' then 'user_vacancy_delivery' end) as table_tags,
        s.calls,s.total_exec_time,s.mean_exec_time,s.rows,s.shared_blks_hit,s.shared_blks_read,
        s.shared_blks_dirtied,s.shared_blks_written,s.temp_blks_read,s.temp_blks_written
        from extensions.pg_stat_statements s where s.dbid=(select oid from pg_catalog.pg_database
        where datname=pg_catalog.current_database())
        order by s.shared_blks_read desc,s.total_exec_time desc limit 20""",
      "indexes":"""select schemaname,tablename,indexname,indexdef from pg_catalog.pg_indexes
        where schemaname='public' and tablename in ('vacancies','user_events','user_vacancy_delivery','users')
        order by tablename,indexname limit 40"""
    }
    for name,query in queries.items():
        result=fetch("https://api.supabase.com/v1/projects/"+REF+"/database/query/read-only",
                     {"Authorization":"Bearer "+token,"Content-Type":"application/json"},
                     {"query":query})
        if result.get("body"):
            try: result["rows"]=json.loads(result.pop("body"))
            except Exception: result.pop("body",None)
        emit(name,result)
emit("metrics_1",metrics())
time.sleep(30)
emit("metrics_2",metrics())
