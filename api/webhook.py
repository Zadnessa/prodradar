"""Vercel serverless webhook для Telegram."""

import json
import logging
import os
from http.server import BaseHTTPRequestHandler

import aiohttp
import httpx
import requests
from postgrest.exceptions import APIError

from bot.handlers import (
    handle_blocked,
    handle_callback,
    handle_hub_callback,
    handle_main_keyboard_text,
    handle_mute,
    handle_mute_callback,
    handle_more_callback,
    handle_pause,
    handle_settings,
    handle_settings_callback,
    handle_start,
    handle_stats,
    handle_stop,
    handle_unmute,
    handle_unmute_all,
    handle_unknown,
)
from bot.telegram_api import answer_callback
from database.supabase_client import SupabaseService


TRANSIENT_EXCEPTIONS = (
    TimeoutError,
    ConnectionError,
    requests.RequestException,
    httpx.HTTPError,
    aiohttp.ClientError,
    APIError,
)


def _is_transient_error(exc):
    return isinstance(exc, TRANSIENT_EXCEPTIONS)


class handler(BaseHTTPRequestHandler):
    """HTTP handler для Telegram update."""

    def do_POST(self):
        try:
            secret = os.getenv("TELEGRAM_WEBHOOK_SECRET")
            if not secret:
                logging.error("TELEGRAM_WEBHOOK_SECRET не задан, webhook отключён")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": "webhook_secret_missing"}).encode("utf-8"))
                return

            header_token = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
            if header_token != secret:
                self.send_response(403)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": "forbidden"}).encode("utf-8"))
                return

            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)
            update = json.loads(body.decode("utf-8"))
            logging.info(
                "Webhook update received: callback=%s message=%s",
                ((update.get("callback_query") or {}).get("data")),
                ((update.get("message") or {}).get("text")),
            )
            db = SupabaseService()

            callback_query = update.get("callback_query")
            if callback_query:
                callback_query_id = callback_query.get("id")
                data = callback_query.get("data") or ""
                chat_id = (callback_query.get("from") or {}).get("id")
                callback_message = callback_query.get("message") or {}
                message_chat_id = ((callback_message.get("chat") or {}).get("id"))
                message_id = callback_message.get("message_id")

                if callback_query_id:
                    answer_callback(callback_query_id)

                user = db.get_user(chat_id) if chat_id else None
                if not user:
                    logging.info("Неизвестный chat_id=%s, игнорирую", chat_id)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": True, "chat_id": message_chat_id}).encode("utf-8"))
                    return

                prefix = data.split(":", 1)[0] if ":" in data else data

                if prefix == "ob" and chat_id and message_id:
                    handle_callback(data, chat_id, message_id, callback_message, db=db)
                elif prefix == "st" and chat_id and message_id:
                    handle_settings_callback(data, chat_id, message_id, callback_message, db=db)
                elif prefix == "more" and chat_id and message_id:
                    handle_more_callback(data, chat_id, message_id, callback_message, db=db)
                elif prefix == "hub" and chat_id and message_id:
                    handle_hub_callback(data, chat_id, message_id, callback_message, db=db)
                elif prefix in {"mute", "unmute", "unmute_all"} and chat_id and message_id:
                    handle_mute_callback(data, chat_id, message_id, db=db)

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True, "chat_id": message_chat_id}).encode("utf-8"))
                return

            message = update.get("message", {})
            chat = message.get("chat", {})
            from_user = message.get("from") or {}
            chat_id = chat.get("id")
            username = from_user.get("username")
            language_code = from_user.get("language_code")
            is_premium = from_user.get("is_premium")
            first_name = from_user.get("first_name")
            last_name = from_user.get("last_name")
            text = (message.get("text") or "").strip()

            if chat_id:
                user = db.get_user(chat_id)
                if user is None and text != "/start":
                    logging.info("Неизвестный chat_id=%s, игнорирую", chat_id)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))
                    return

                if text == "/start":
                    handle_start(
                        chat_id,
                        username,
                        db=db,
                        language_code=language_code,
                        is_premium=is_premium,
                        first_name=first_name,
                        last_name=last_name,
                    )
                elif text == "/stop":
                    handle_stop(chat_id, db=db)
                elif text == "/settings":
                    handle_settings(chat_id, db=db)
                elif text == "/pause":
                    handle_pause(chat_id, db=db)
                elif text == "/stats":
                    handle_stats(chat_id, db=db)
                elif text == "/blocked":
                    handle_blocked(chat_id, db=db)
                elif text == "/unmute_all":
                    handle_unmute_all(chat_id, db=db)
                elif text.startswith("/unmute_"):
                    slug = text[len("/unmute_"):].strip()
                    handle_unmute(chat_id, slug, db=db)
                elif text.startswith("/mute_"):
                    slug = text[len("/mute_"):].strip()
                    handle_mute(chat_id, slug, db=db)
                elif handle_main_keyboard_text(chat_id, text, db=db):
                    pass
                else:
                    handle_unknown(chat_id)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))
        except Exception as exc:
            is_transient = _is_transient_error(exc)
            error_type = type(exc).__name__
            logging.exception("Webhook error type=%s transient=%s", error_type, is_transient)
            self.send_response(500 if is_transient else 200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False}).encode("utf-8"))
