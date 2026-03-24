"""Операции с Supabase в одном месте."""

import hashlib
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

    raw_value = "|".join(normalized_values)
    return hashlib.sha256(raw_value.encode("utf-8")).hexdigest()


class SupabaseService:
    """Обертка над supabase-py."""

    def __init__(self):
        self.client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

    @staticmethod
    def _chunked(items, chunk_size):
        for index in range(0, len(items), chunk_size):
            yield items[index:index + chunk_size]

    def get_existing_vacancy_ids(self):
        result = self.client.table("vacancies").select("id").execute()
        return {row["id"] for row in result.data or []}

    def get_existing_vacancy_hashes(self):
        result = self.client.table("vacancies").select("id,content_hash").execute()
        return {row["id"]: row.get("content_hash") for row in result.data or []}

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
        self.client.table("vacancies").insert(payload).execute()
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
            query = self.client.table("vacancies").select("id").eq("is_active", True)
            if companies:
                query = query.in_("company", companies)
            missing_result = query.not_.in_("id", active_ids).execute()
            missing_ids = sorted(row["id"] for row in missing_result.data or [])
        else:
            query = self.client.table("vacancies").select("id").eq("is_active", True)
            if companies:
                query = query.in_("company", companies)
            current_active_result = query.execute()
            current_active_ids = {row["id"] for row in current_active_result.data or []}
            missing_ids = sorted(current_active_ids - set(active_ids))

        if not missing_ids:
            return 0

        for chunk in self._chunked(missing_ids, 500):
            self.client.table("vacancies").update({"is_active": False}).in_("id", chunk).execute()
        return len(missing_ids)

    def count_active_vacancies(self):
        result = self.client.table("vacancies").select("id", count="exact").eq("is_active", True).execute()
        return result.count or 0

    def get_undelivered_vacancies(self, chat_id, limit=50, offset=0):
        delivered_result = (
            self.client.table("user_vacancy_delivery")
            .select("vacancy_id")
            .eq("user_chat_id", chat_id)
            .execute()
        )
        delivered_ids = {row["vacancy_id"] for row in delivered_result.data or []}

        query = self.client.table("vacancies").select("*").eq("is_active", True)
        if delivered_ids:
            query = query.not_.in_("id", list(delivered_ids))

        end = offset + limit - 1
        result = query.order("created_at", desc=True).range(offset, end).execute()
        return result.data or []

    def mark_delivered(self, chat_id, vacancy_ids, source="scheduled"):
        if not vacancy_ids:
            return

        delivered_at = datetime.now(timezone.utc).isoformat()
        payload = [
            {
                "user_chat_id": chat_id,
                "vacancy_id": vacancy_id,
                "source": source,
                "delivered_at": delivered_at,
            }
            for vacancy_id in vacancy_ids
        ]
        self.client.table("user_vacancy_delivery").upsert(
            payload,
            on_conflict="user_chat_id,vacancy_id",
            ignore_duplicates=True,
        ).execute()

    def clear_delivery_history(self, chat_id):
        self.client.table("user_vacancy_delivery").delete().eq("user_chat_id", chat_id).execute()

    def get_active_users(self, bot_id="main"):
        result = (
            self.client.table("users")
            .select("chat_id,username,filters,bot_id,paused")
            .eq("is_active", True)
            .eq("bot_id", bot_id)
            .execute()
        )
        return result.data or []

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
        result = (
            self.client.table("vacancies")
            .select("company")
            .eq("is_active", True)
            .gte("first_seen_at", cutoff.isoformat())
            .execute()
        )

        rows = result.data or []
        by_company = {}
        for row in rows:
            company = row.get("company") or "Не указана"
            by_company[company] = by_company.get(company, 0) + 1

        return {
            "total": len(rows),
            "by_company": by_company,
        }

    def upsert_user(self, chat_id, username, bot_id="main"):
        payload = {
            "chat_id": chat_id,
            "username": username,
            "is_active": True,
            "bot_id": bot_id,
        }
        self.client.table("users").upsert(payload).execute()

    def deactivate_user(self, chat_id):
        self.client.table("users").update({"is_active": False}).eq("chat_id", chat_id).execute()
