# Антибот: справочник диагностики и решений

## 1. Классификация блокировок

### Cookie-based
Сервер проверяет наличие определённых cookies (обычно ставятся JS-скриптами аналитики).

**Симптом:** 302 на `/captcha` без cookies, 200 JSON с cookies.

**Решение:** Playwright в `parsers/browser.py` собирает cookies, парсер получает их через `browser_secrets`.

### TLS fingerprint
WAF определяет HTTP-клиент по параметрам TLS handshake (JA3/JA4).

**Симптом:** запрос с правильными cookies и заголовками всё равно даёт captcha; curl из терминала тоже блокируется; Playwright и curl_cffi проходят. В ответе есть `waf-verdict: challenge`.

**Решение:** `curl_cffi` с `impersonate`.

### JS challenge
Сервер отдаёт JS, который должен выполниться и поставить cookie/token.

**Симптом:** HTML-ответ содержит script с eval/challenge, нет полезного контента.

**Решение:** Playwright.

### Header validation
Сервер проверяет `sec-fetch-*`, `Origin`, `Referer`.

**Симптом:** без sec-заголовков — captcha, с ними — OK.

**Решение:** добавить полный набор sec-заголовков.

## 2. Диагностический алгоритм

1. Сделать запрос через `requests` с минимальными заголовками. Если OK — антибота нет, тип A.
2. Добавить полные заголовки (`sec-fetch-*`, `Origin`, `Referer`, `User-Agent`). Если OK — header validation, решение: хардкод заголовков.
3. Добавить cookies из браузера. Если OK — cookie-based, решение: Playwright в `browser.py`.
4. Попробовать `curl_cffi` с `impersonate` без cookies. Если OK — TLS fingerprint, решение: `curl_cffi`.
5. Попробовать `curl_cffi` с `impersonate` + cookies из Playwright. Если OK — комбинация TLS + cookies.
6. Если ничего не помогает — Playwright для полного рендеринга (тип D, максимальная сложность).

## 3. Реестр компаний и их защит

| Компания | Блокировка | Транспорт | Примечания |
| --- | --- | --- | --- |
| Циан (API) | cookies + headers | aiohttp + browser_secrets cookies | `_yasc` обязательна, sec-заголовки обязательны; API не требует TLS impersonate, нужны только cookies + заголовки |
| Циан (enrichment) | TLS fingerprint | curl_cffi impersonate="chrome131" | cookies не нужны, CSR-страница |
| СберЗдоровье | JS challenge | Playwright | buildId из HTML |

## 4. Инструменты

- `requests`: стандартный HTTP-клиент. TLS fingerprint OpenSSL, легко определяется WAF.
- `curl_cffi`: обёртка над `curl-impersonate`. Имитирует TLS fingerprint Chrome. Установка: `pip install curl_cffi` (~15 MB). Ключевой параметр: `impersonate="chrome131"`.
- Playwright: headless-браузер. Проходит любую защиту, но тяжёлый. Использовать только для генерации сессии (cookies, tokens), не для массовых запросов.

## 5. Типичные ошибки диагностики

- «cookies не работают» — проверь, не протухли ли они. Время жизни `_yasc` ~10 минут.
- «requests блокируется с правильными cookies» — возможно, TLS fingerprint. Проверь `curl_cffi`.
- «SSR-страница пустая» — возможно, сайт перешёл на CSR. Проверь с `render_js=true`.
- «cURL из терминала работает, requests — нет» — TLS fingerprint (системный curl может использовать другую библиотеку SSL).
- «cURL из Colab не работает, из терминала — работает» — разные IP, cookies привязаны к IP/сессии.
