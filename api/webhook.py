"""Vercel serverless webhook для Telegram."""

import json
from http.server import BaseHTTPRequestHandler

from bot.handlers import handle_start, handle_stop, handle_unknown
from database.supabase_client import SupabaseService


class handler(BaseHTTPRequestHandler):
    """HTTP handler для Telegram update."""

    def do_POST(self):
        try:
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)
            update = json.loads(body.decode("utf-8"))

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
