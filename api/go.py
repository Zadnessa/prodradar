"""Vercel serverless redirect для отслеживания кликов по вакансиям."""

import json
import logging
import urllib.parse
from http.server import BaseHTTPRequestHandler

from database.supabase_client import SupabaseService


class handler(BaseHTTPRequestHandler):
    """HTTP handler для редиректа по ссылке вакансии."""

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        target_url = (query_params.get("url") or [""])[0]

        if not target_url:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "error": "missing_url"}).encode("utf-8"))
            return

        redirect_url = target_url
        try:
            user_agent = self.headers.get("User-Agent", "")
            if "iPhone" in user_agent or "iPad" in user_agent:
                detected_os = "ios"
            elif "Android" in user_agent:
                detected_os = "android"
            elif "Windows" in user_agent:
                detected_os = "windows"
            elif "Macintosh" in user_agent:
                detected_os = "macos"
            else:
                detected_os = "unknown"

            optional_fields = [
                "vacancy_id",
                "chat_id",
                "source",
                "company",
                "grade",
                "title_confidence",
                "city",
                "work_format",
            ]
            properties = {}
            for field in optional_fields:
                field_value = (query_params.get(field) or [None])[0]
                if field_value not in (None, ""):
                    properties[field] = field_value
            properties["os"] = detected_os

            chat_id_raw = (query_params.get("chat_id") or [""])[0]
            try:
                chat_id = int(chat_id_raw)
            except (TypeError, ValueError):
                chat_id = 0

            try:
                db = SupabaseService()
                db.log_event(chat_id, "vacancy_clicked", properties)
            except Exception:
                logging.exception("Не удалось записать событие vacancy_clicked")
        except Exception:
            logging.exception("Ошибка в обработке параметров redirect")
        finally:
            self.send_response(302)
            self.send_header("Location", redirect_url)
            self.end_headers()
