"""Операции с Supabase в одном месте."""

from datetime import datetime, timedelta, timezone

from supabase import create_client

import config


class SupabaseService:
    """Обертка над supabase-py."""

    def __init__(self):
        self.client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

    def get_existing_vacancy_ids(self):
        result = self.client.table("vacancies").select("id").execute()
        return {row["id"] for row in result.data or []}

    def get_city_mappings(self):
        result = self.client.table("city_mappings").select("source,raw_value,normalized").execute()
        mappings = {}
        for row in result.data or []:
            mappings[(row["source"], row["raw_value"])] = row["normalized"]
        return mappings

    def get_enabled_companies(self):
        result = self.client.table("companies").select("*").eq("is_enabled", True).execute()
        return result.data or []

    def save_vacancies(self, vacancies):
        if not vacancies:
            return
        self.client.table("vacancies").insert(vacancies).execute()

    def mark_vacancies_notified(self, vacancy_ids):
        if not vacancy_ids:
            return
        notified_at = datetime.now(timezone.utc).isoformat()
        self.client.table("vacancies").update({"notified_at": notified_at}).in_("id", vacancy_ids).execute()

    def get_unnotified_vacancies(self):
        result = self.client.table("vacancies").select("*").is_("notified_at", "null").eq("is_active", True).execute()
        return result.data or []

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
            query = query.not_in("id", list(delivered_ids))

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
            .maybe_single()
            .execute()
        )
        return result.data

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
