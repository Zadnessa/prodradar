"""Операции с Supabase в одном месте."""

import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone

from supabase import create_client

import config


CONTENT_HASH_FIELDS = (
    "title",
    "grade",
    "city",
    "work_format",
    "experience",
)


def compute_content_hash(vacancy):
    """Считает SHA-256 хеш ключевых полей вакансии."""
    normalized_values = []
    for field in CONTENT_HASH_FIELDS:
        value = vacancy.get(field, "")
        normalized_values.append("" if value is None else str(value))

    if vacancy.get("selection_profile") == "project_bizdev":
        normalized_values.extend(["project_bizdev", ",".join(sorted(vacancy.get("role_families") or [])),
                                  vacancy.get("selection_version") or ""])
    raw_value = "|".join(normalized_values)
    return hashlib.sha256(raw_value.encode("utf-8")).hexdigest()


class SupabaseService:
    """Обертка над supabase-py."""

    PAGE_SIZE = 1000

    def __init__(self):
        self.client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

    @staticmethod
    def _chunked(items, chunk_size):
        for index in range(0, len(items), chunk_size):
            yield items[index:index + chunk_size]

    @staticmethod
    def _guard_pool():
        if config.VACANCY_PROFILE != "project_bizdev" or config.SUPABASE_URL.rstrip('/') != "https://jmsdxgylyjxwdwmdrmxw.supabase.co":
            raise ValueError("Пул разрешён только в test")

    def _vacancies_select(self, columns, **kwargs):
        query = self.client.table("vacancies").select(columns, **kwargs)
        if config.VACANCY_PROFILE == "project_bizdev":
            query = query.eq("selection_profile", "project_bizdev")
        return query

    @staticmethod
    def _vacancy_columns():
        columns = "id,title,company,grade,city,work_format,experience,description,url,published_at,created_at,is_active,content_hash"
        if config.VACANCY_PROFILE == "project_bizdev":
            columns += ",selection_profile,role_families,selection_version"
        return columns

    def store_source_pool(self, source, vacancies, metadata):
        self._guard_pool()
        if len({v.get("id") for v in vacancies}) != len(vacancies) or any(
            not v.get("id") or not v.get("title") or not v.get("url") for v in vacancies):
            raise ValueError("Некорректный или дублирующийся pool id/title/url")
        capture = str(uuid.uuid4())
        try:
            for chunk in self._chunked(vacancies, 100):
                self.client.table("source_pool_stage").insert([
                    {"capture_id": capture, "source_name": source, "vacancy_id": v["id"], "vacancy": v}
                    for v in chunk]).execute()
            self.client.rpc("commit_source_pool", {"p_source": source, "p_capture": capture,
                "p_expected": len(vacancies), "p_metadata": metadata}).execute()
        finally:
            self.client.table("source_pool_stage").delete().eq("capture_id", capture).execute()

    def fail_source_pool(self, source, error):
        self._guard_pool()
        self.client.table("source_pool_status").upsert({"source_name": source, "status": "failed",
            "captured_at": datetime.now(timezone.utc).isoformat(), "metadata": {"error": error}},
            on_conflict="source_name").execute()

    def load_source_pool(self, source, max_age_hours=24):
        self._guard_pool()
        status_rows = self.client.table("source_pool_status").select("status,captured_at,raw_count,metadata").eq("source_name", source).execute().data or []
        if len(status_rows) != 1 or status_rows[0]["status"] not in {"ready", "empty"}:
            raise ValueError("Пул источника не подтверждён успешным сбором")
        status = status_rows[0]
        captured = datetime.fromisoformat(status["captured_at"].replace('Z', '+00:00'))
        age = datetime.now(timezone.utc) - captured
        if age > timedelta(hours=max_age_hours) or age < -timedelta(minutes=5):
            raise ValueError("Пул источника устарел")
        vacancies = []
        while True:
            rows = self.client.table("source_pool").select("vacancy").eq("source_name", source).order("vacancy_id").range(len(vacancies), len(vacancies) + self.PAGE_SIZE - 1).execute().data or []
            vacancies.extend(row["vacancy"] for row in rows)
            if len(rows) < self.PAGE_SIZE:
                break
        if len(vacancies) != status["raw_count"]:
            raise ValueError("Пул источника неполон")
        return vacancies

    def get_existing_vacancy_ids(self):
        result = self._vacancies_select("id").execute()
        return {row["id"] for row in result.data or []}

    def get_existing_vacancy_hashes(self):
        hashes = {}
        offset = 0
        page_size = self.PAGE_SIZE

        while True:
            result = (
                self._vacancies_select("id,content_hash")
                .range(offset, offset + page_size - 1)
                .execute()
            )
            rows = result.data or []
            for row in rows:
                hashes[row["id"]] = row.get("content_hash")

            if len(rows) < page_size:
                break
            offset += page_size

        return hashes

    def get_city_mappings(self):
        result = self.client.table("city_mappings").select("source,raw_value,normalized").execute()
        mappings = {}
        for row in result.data or []:
            mappings[(row["source"], row["raw_value"])] = row["normalized"]
        return mappings

    def get_enabled_companies(self):
        result = self.client.table("companies").select("*").eq("is_enabled", True).execute()
        return result.data or []

    def insert_vacancies(self, vacancies):
        if not vacancies:
            return 0

        last_seen_at = datetime.now(timezone.utc).isoformat()
        payload = [{**vacancy, "last_seen_at": last_seen_at, "is_active": True} for vacancy in vacancies]
        for chunk in self._chunked(payload, 50):
            self.client.table("vacancies").upsert(chunk, on_conflict="id").execute()
        return len(payload)

    def touch_vacancies(self, vacancy_ids):
        if not vacancy_ids:
            return 0

        last_seen_at = datetime.now(timezone.utc).isoformat()
        for chunk in self._chunked(vacancy_ids, 500):
            self.client.table("vacancies").update({"last_seen_at": last_seen_at}).in_("id", chunk).execute()
        return len(vacancy_ids)

    def update_vacancies(self, vacancies):
        if not vacancies:
            return 0

        last_seen_at = datetime.now(timezone.utc).isoformat()
        for chunk in self._chunked(vacancies, 50):
            payload = [{**vacancy, "last_seen_at": last_seen_at, "is_active": True} for vacancy in chunk]
            self.client.table("vacancies").upsert(payload, on_conflict="id").execute()
        return len(vacancies)

    def deactivate_missing_vacancies(self, active_ids, companies=None):
        active_ids = sorted(set(active_ids))
        if companies is not None:
            companies = sorted({company for company in companies if company})
            if not companies:
                return 0

        if active_ids and len(active_ids) <= 500:
            query = self._vacancies_select("id").eq("is_active", True)
            if companies:
                query = query.in_("company", companies)
            missing_result = query.not_.in_("id", active_ids).execute()
            missing_ids = sorted(row["id"] for row in missing_result.data or [])
        else:
            offset = 0
            page_size = self.PAGE_SIZE
            current_active_ids = set()

            while True:
                query = (
                    self._vacancies_select("id")
                    .eq("is_active", True)
                    .range(offset, offset + page_size - 1)
                )
                if companies:
                    query = query.in_("company", companies)
                current_active_result = query.execute()
                rows = current_active_result.data or []
                current_active_ids.update(row["id"] for row in rows)

                if len(rows) < page_size:
                    break
                offset += page_size

            missing_ids = sorted(current_active_ids - set(active_ids))

        if not missing_ids:
            return 0

        for chunk in self._chunked(missing_ids, 500):
            self.client.table("vacancies").update({"is_active": False}).in_("id", chunk).execute()
        return len(missing_ids)

    def count_active_vacancies(self):
        result = self._vacancies_select("id", count="exact").eq("is_active", True).execute()
        return result.count or 0

    def count_delivered(self, chat_id):
        result = (
            self.client.table("user_vacancy_delivery")
            .select("vacancy_id", count="exact")
            .eq("user_chat_id", chat_id)
            .eq("status", "delivered")
            .limit(1)
            .execute()
        )
        return result.count or 0

    def get_undelivered_vacancies(self, chat_id, limit=50, offset=0):
        delivered_ids = set()
        delivery_offset = 0
        page_size = self.PAGE_SIZE

        while True:
            delivered_result = (
                self.client.table("user_vacancy_delivery")
                .select("vacancy_id")
                .eq("user_chat_id", chat_id)
                .eq("status", "delivered")
                .range(delivery_offset, delivery_offset + page_size - 1)
                .execute()
            )
            rows = delivered_result.data or []
            delivered_ids.update(row["vacancy_id"] for row in rows)

            if len(rows) < page_size:
                break
            delivery_offset += page_size

        query = (
            self._vacancies_select(
                self._vacancy_columns()
            )
            .eq("is_active", True)
        )
        if delivered_ids:
            query = query.not_.in_("id", list(delivered_ids))

        end = offset + limit - 1
        result = query.order("published_at", desc=True).order("created_at", desc=True).range(offset, end).execute()
        return result.data or []

    def get_active_vacancies_for_filter_check(self, limit=500, offset=0):
        query = (
            self._vacancies_select(
                self._vacancy_columns()
            )
            .eq("is_active", True)
        )
        end = offset + limit - 1
        result = query.order("published_at", desc=True).order("created_at", desc=True).range(offset, end).execute()
        return result.data or []

    def mark_delivered(self, chat_id, vacancy_ids, source="scheduled"):
        if not vacancy_ids:
            return

        _ = source
        delivered_at = datetime.now(timezone.utc).isoformat()
        payload = [
            {
                "user_chat_id": chat_id,
                "vacancy_id": vacancy_id,
                "status": "delivered",
                "delivered_at": delivered_at,
            }
            for vacancy_id in vacancy_ids
        ]
        self.client.table("user_vacancy_delivery").upsert(
            payload,
            on_conflict="user_chat_id,vacancy_id",
        ).execute()

    def mark_announced(self, chat_id, vacancy_ids):
        if not vacancy_ids:
            return

        announced_at = datetime.now(timezone.utc).isoformat()
        payload = [
            {
                "user_chat_id": chat_id,
                "vacancy_id": vacancy_id,
                "status": "announced",
                "announced_at": announced_at,
                "delivered_at": None,
            }
            for vacancy_id in vacancy_ids
        ]
        self.client.table("user_vacancy_delivery").upsert(
            payload,
            on_conflict="user_chat_id,vacancy_id",
            ignore_duplicates=True,
        ).execute()

    def get_announced_vacancy_ids(self, chat_id):
        announced_ids = set()
        delivery_offset = 0
        page_size = self.PAGE_SIZE

        while True:
            result = (
                self.client.table("user_vacancy_delivery")
                .select("vacancy_id")
                .eq("user_chat_id", chat_id)
                .eq("status", "announced")
                .range(delivery_offset, delivery_offset + page_size - 1)
                .execute()
            )
            rows = result.data or []
            announced_ids.update(row["vacancy_id"] for row in rows)

            if len(rows) < page_size:
                break
            delivery_offset += page_size

        return announced_ids

    def count_new_for_user(self, chat_id):
        delivery_ids = set()
        delivery_offset = 0
        page_size = self.PAGE_SIZE

        while True:
            result = (
                self.client.table("user_vacancy_delivery")
                .select("vacancy_id")
                .eq("user_chat_id", chat_id)
                .range(delivery_offset, delivery_offset + page_size - 1)
                .execute()
            )
            rows = result.data or []
            delivery_ids.update(row["vacancy_id"] for row in rows)

            if len(rows) < page_size:
                break
            delivery_offset += page_size

        if not delivery_ids:
            result = self._vacancies_select("id", count="exact").eq("is_active", True).execute()
            return result.count or 0

        if len(delivery_ids) <= 500:
            result = (
                self._vacancies_select("id", count="exact")
                .eq("is_active", True)
                .not_.in_("id", list(delivery_ids))
                .execute()
            )
            return result.count or 0

        count = 0
        offset = 0
        while True:
            result = (
                self._vacancies_select("id")
                .eq("is_active", True)
                .range(offset, offset + page_size - 1)
                .execute()
            )
            rows = result.data or []
            count += sum(1 for row in rows if row["id"] not in delivery_ids)
            if len(rows) < page_size:
                break
            offset += page_size
        return count

    def count_announced_for_user(self, chat_id):
        announced_ids = self.get_announced_vacancy_ids(chat_id)
        if not announced_ids:
            return 0

        count = 0
        for chunk in self._chunked(list(announced_ids), 500):
            result = self._vacancies_select("id").eq("is_active", True).in_("id", chunk).execute()
            count += len(result.data or [])
        return count

    def clear_delivery_history(self, chat_id):
        self.client.table("user_vacancy_delivery").delete().eq("user_chat_id", chat_id).execute()

    def get_active_users(self, bot_id="main"):
        users = []
        offset = 0
        page_size = self.PAGE_SIZE

        while True:
            result = (
                self.client.table("users")
                .select("chat_id,username,filters,bot_id,paused")
                .eq("is_active", True)
                .eq("bot_id", bot_id)
                .range(offset, offset + page_size - 1)
                .execute()
            )
            rows = result.data or []
            users.extend(rows)

            if len(rows) < page_size:
                break
            offset += page_size

        return users

    def update_user_filters(self, chat_id, filters):
        self.client.table("users").update({"filters": filters}).eq("chat_id", chat_id).execute()

    def update_onboarding_step(self, chat_id, step):
        self.client.table("users").update({"onboarding_step": step}).eq("chat_id", chat_id).execute()

    def set_user_paused(self, chat_id, paused):
        self.client.table("users").update({"paused": paused}).eq("chat_id", chat_id).execute()

    def get_user(self, chat_id):
        result = (
            self.client.table("users")
            .select("chat_id,filters,onboarding_step,paused,is_active")
            .eq("chat_id", chat_id)
            .execute()
        )
        rows = result.data or []
        return rows[0] if rows else None

    def get_vacancy_stats(self):
        cutoff = datetime.now(timezone.utc) - timedelta(days=config.VACANCY_TTL_DAYS)
        rows = []
        offset = 0
        page_size = self.PAGE_SIZE

        while True:
            result = (
                self._vacancies_select("company")
                .eq("is_active", True)
                .gte("first_seen_at", cutoff.isoformat())
                .range(offset, offset + page_size - 1)
                .execute()
            )
            page_rows = result.data or []
            rows.extend(page_rows)

            if len(page_rows) < page_size:
                break
            offset += page_size

        by_company = {}
        for row in rows:
            company = row.get("company") or "Не указана"
            by_company[company] = by_company.get(company, 0) + 1

        return {
            "total": len(rows),
            "by_company": by_company,
        }

    def upsert_user(
        self,
        chat_id,
        username,
        bot_id="main",
        language_code=None,
        is_premium=None,
        first_name=None,
        last_name=None,
    ):
        payload = {
            "chat_id": chat_id,
            "username": username,
            "is_active": True,
            "bot_id": bot_id,
        }
        if language_code is not None:
            payload["language_code"] = language_code
        if is_premium is not None:
            payload["is_premium"] = is_premium
        if first_name is not None:
            payload["first_name"] = first_name
        if last_name is not None:
            payload["last_name"] = last_name
        self.client.table("users").upsert(payload).execute()

    def deactivate_user(self, chat_id):
        try:
            self.client.table("users").update({"is_active": False}).eq("chat_id", chat_id).execute()
        except Exception as exc:
            logging.warning("Не удалось деактивировать пользователя chat_id=%s: %s", chat_id, exc)

    def log_event(self, chat_id, event, properties=None):
        try:
            payload = {
                "chat_id": chat_id,
                "event": event,
                "properties": properties or {},
            }
            self.client.table("user_events").insert(payload).execute()
        except Exception as exc:
            logging.warning("Не удалось записать user_event chat_id=%s event=%s: %s", chat_id, event, exc)
