"""Операции с Supabase в одном месте."""

from datetime import datetime, timezone

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
        result = self.client.table("vacancies").select("*").is_("notified_at", None).eq("is_active", True).execute()
        return result.data or []

    def get_active_users(self, bot_id="main"):
        result = (
            self.client.table("users")
            .select("chat_id,username,filters,bot_id")
            .eq("is_active", True)
            .eq("bot_id", bot_id)
            .execute()
        )
        return result.data or []

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
