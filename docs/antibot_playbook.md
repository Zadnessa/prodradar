# Антибот: справочник диагностики и решений

## 1. Классификация блокировок

### Недостающая цепочка CA
`CERTIFICATE_VERIFY_FAILED` / `ERR_CERT_AUTHORITY_INVALID` возникают до HTTP
и JavaScript; это не TLS fingerprint. Проверить issuer и подпись сертификата.
Для трёх банков официальная российская цепочка в `parsers/certificates` добавляется
к системным CA через `parsers/tls.py` только в запросах этих источников.
Hostname и CERT_REQUIRED обязательны; `ssl=False` / `ignore_https_errors` запрещены.

### Блокировка сети или региона
Страница может запрещать адреса облачных/VPN сетей ещё до приложения.
Chromium с того же IP получает такую же блокировку; cookie/token сам по себе
не решает её. Сравнить ответы разных разрешённых сред и явно записать ограничение.

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
6. Если API всё ещё недоступен — исследовать актуальный endpoint и запрос в DevTools, сравнить допустимые сети, зафиксировать неуспех. Браузерный runtime служит только получению доступа; выгрузка вакансий через браузер запрещена. Обычный HTTP HTML-enrichment допустим для полного описания, отсутствующего в API.

## 3. Реестр компаний и их защит

| Компания | Блокировка | Транспорт | Примечания |
| --- | --- | --- | --- |
| Циан (API) | cookies + headers | aiohttp + browser_secrets cookies | `_yasc` обязательна, sec-заголовки обязательны; API не требует TLS impersonate, нужны только cookies + заголовки |
| Циан (enrichment) | TLS fingerprint | curl_cffi impersonate="chrome131" | cookies не нужны, CSR-страница |
| СберЗдоровье | JS challenge | Playwright | buildId из HTML |
| ДомКлик | header validation / QRator на HTML | aiohttp с Referer и Sec-Fetch | Текущий career.domclick.ru API проходит без cookies в проверенном runtime; HTML открывается Chromium и получает qrator_ssid2 |
| МТС Линк | публичный API | aiohttp | Huntflow list/detail сайта доступны без Bearer; старый categoryId исключён |
| Dodo | новый backend, текущий 503 | aiohttp | apiURL из публичного Nuxt config; transport/browser tokens ещё проверяются в Actions |
| Альфа-Банк, Т-Банк, Точка | недостающий официальный CA | aiohttp + scoped SSLContext | Actions подтвердил Russian Trusted Sub CA; проверка hostname сохранена, исходные API дают HTTP 200 |
| Купер | блокировка облачной/VPN сети | firm API пока требует сверки | team.kuper.ru отвечает 403 с просьбой отключить VPN и в Chromium; старый API содержит лишь одну вакансию контактного центра |

## 4. Инструменты

- `requests`: стандартный HTTP-клиент. TLS fingerprint OpenSSL, легко определяется WAF.
- `curl_cffi`: обёртка над `curl-impersonate`. Имитирует TLS fingerprint Chrome. Установка: `pip install curl_cffi` (~15 MB). Ключевой параметр: `impersonate="chrome131"`.
- Playwright: headless-браузер для JavaScript, cookies и tokens; сам по себе
  не исправляет недоверенный CA или блокировку IP/региона. Runtime использует
  общий browser stage; отдельная read-only DevTools-диагностика исследует API.

## 5. Типичные ошибки диагностики

- «cookies не работают» — проверь, не протухли ли они. Время жизни `_yasc` ~10 минут.
- «requests блокируется с правильными cookies» — возможно, TLS fingerprint. Проверь `curl_cffi`.
- «SSR-страница пустая» — возможно, сайт перешёл на CSR. Проверь с `render_js=true`.
- «cURL из терминала работает, requests — нет» — TLS fingerprint (системный curl может использовать другую библиотеку SSL).
- «cURL из Colab не работает, из терминала — работает» — разные IP, cookies привязаны к IP/сессии.
