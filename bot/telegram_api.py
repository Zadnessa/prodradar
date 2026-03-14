"""Единый helper для Telegram Bot API."""

import logging
import os
import time

import requests

import config


_API_TIMEOUT = 20


def _get_bot_token(bot_id="main"):
    token_env = config.BOTS[bot_id]["token_env"]
    return os.getenv(token_env, "")


def _post(method, payload, bot_id="main", allow_retry=True):
    token = _get_bot_token(bot_id)
    if not token:
        logging.error("Не задан токен для бота %s", bot_id)
        return None

    url = f"https://api.telegram.org/bot{token}/{method}"

    try:
        response = requests.post(url, json=payload, timeout=_API_TIMEOUT)
    except requests.RequestException as exc:
        logging.exception("Ошибка запроса к Telegram %s: %s", method, exc)
        return None

    if response.status_code == 403:
        logging.warning("Telegram %s: 403 для chat_id=%s", method, payload.get("chat_id"))
        return None

    if response.status_code == 429:
        try:
            body = response.json()
            retry_after = (body.get("parameters") or {}).get("retry_after", 1)
        except ValueError:
            retry_after = 1
        if allow_retry:
            time.sleep(retry_after)
            return _post(method, payload, bot_id=bot_id, allow_retry=False)
        logging.warning("Telegram %s: повторный 429, chat_id=%s", method, payload.get("chat_id"))
        return None

    if response.status_code >= 400:
        logging.error("Telegram %s: HTTP %s, body=%s", method, response.status_code, response.text)
        return None

    try:
        data = response.json()
    except ValueError:
        logging.error("Telegram %s: невалидный JSON в ответе", method)
        return None

    if not data.get("ok"):
        logging.error("Telegram %s: API error=%s", method, data)
        return None

    return data.get("result")


def send_message(chat_id, text, reply_markup=None, bot_id="main"):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return _post("sendMessage", payload, bot_id=bot_id)


def edit_message(chat_id, message_id, text, reply_markup=None, bot_id="main"):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    token = _get_bot_token(bot_id)
    if not token:
        logging.error("Не задан токен для бота %s", bot_id)
        return None

    url = f"https://api.telegram.org/bot{token}/editMessageText"
    try:
        response = requests.post(url, json=payload, timeout=_API_TIMEOUT)
    except requests.RequestException as exc:
        logging.exception("Ошибка запроса к Telegram editMessageText: %s", exc)
        return None

    if response.status_code == 400 and "message is not modified" in response.text.lower():
        return None

    if response.status_code == 403:
        logging.warning("Telegram editMessageText: 403 для chat_id=%s", chat_id)
        return None

    if response.status_code == 429:
        try:
            body = response.json()
            retry_after = (body.get("parameters") or {}).get("retry_after", 1)
        except ValueError:
            retry_after = 1
        time.sleep(retry_after)
        retry = _post("editMessageText", payload, bot_id=bot_id, allow_retry=False)
        return retry

    if response.status_code >= 400:
        logging.error("Telegram editMessageText: HTTP %s, body=%s", response.status_code, response.text)
        return None

    try:
        data = response.json()
    except ValueError:
        logging.error("Telegram editMessageText: невалидный JSON в ответе")
        return None

    if not data.get("ok"):
        logging.error("Telegram editMessageText: API error=%s", data)
        return None

    return data.get("result")


def answer_callback(callback_query_id, text=None, bot_id="main"):
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    return _post("answerCallbackQuery", payload, bot_id=bot_id)


def build_inline_keyboard(buttons, columns=2):
    rows = []
    current_row = []

    for button in buttons:
        current_row.append({"text": button["text"], "callback_data": button["callback_data"]})
        if len(current_row) == columns:
            rows.append(current_row)
            current_row = []

    if current_row:
        rows.append(current_row)

    return {"inline_keyboard": rows}
