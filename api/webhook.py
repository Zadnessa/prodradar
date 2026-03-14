"""Vercel serverless webhook для Telegram."""

import json
import os
from http.server import BaseHTTPRequestHandler

from bot.handlers import handle_start, handle_stop, handle_unknown
from bot.telegram_api import answer_callback
from database.supabase_client import SupabaseService


class handler(BaseHTTPRequestHandler):
    """HTTP handler для Telegram update."""

    def do_POST(self):
        try:
            secret = os.getenv("TELEGRAM_WEBHOOK_SECRET")
            header_token = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
            if secret and header_token != secret:
                self.send_response(403)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": "forbidden"}).encode("utf-8"))
                return

            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)
            update = json.loads(body.decode("utf-8"))

            callback_query = update.get("callback_query")
            if callback_query:
                callback_query_id = callback_query.get("id")
                if callback_query_id:
                    answer_callback(callback_query_id)

            message = update.get("message", {})
            chat = message.get("chat", {})
            chat_id = chat.get("id")
            username = (message.get("from") or {}).get("username")
            text = (message.get("text") or "").strip()

            if chat_id:
                db = SupabaseService()
                if text == "/start":
                    handle_start(chat_id, username, db=db)
                elif text == "/stop":
                    handle_stop(chat_id, db=db)
                else:
                    handle_unknown(chat_id)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))
        except Exception:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False}).encode("utf-8"))
