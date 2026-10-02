# ProductRadar

## Что это

ProductRadar — Telegram-бот для мониторинга вакансий Product Manager напрямую с карьерных сайтов 16+ компаний.

- Без агрегаторов: бот ходит в API и карьерные страницы компаний напрямую.
- Новые вакансии доставляются в Telegram дважды в день.
- Пользователь получает только те вакансии, которые ещё не были доставлены именно ему.

## Архитектура

Проект состоит из четырёх основных частей:

- **Vercel** — serverless webhook для Telegram-команд, callback-кнопок и пользовательских сценариев.
- **Supabase (PostgreSQL)** — хранение вакансий, пользователей, фильтров, справочника компаний, маппинга городов и истории доставки.
- **GitHub Actions** — cron-задача, которая запускает сбор вакансий дважды в день.
- **Telegram Bot API** — канал доставки вакансий и интерфейс пользователя.

### Pipeline

1. Парсеры забирают вакансии из API компаний.
2. Для новых вакансий вызывается enrichment через API отдельной вакансии, если парсер поддерживает этот шаг.
3. Данные нормализуются: `grade`, `experience`, `city`, `work_format`.
3.1. Вакансии сортируются по дате публикации (`published_at DESC`, `NULL` в конце), затем по дате обнаружения (`created_at DESC`).
4. Вакансии сохраняются в Supabase.
5. Доставка идёт per-user через Telegram с учётом пользовательских фильтров.

### Модель доставки

- История доставки хранится в таблице `user_vacancy_delivery`.
- Пользовательские фильтры хранятся в `users.filters`.
- Глобальная модель `notified_at` устарела и заменена per-user доставкой.

## Команды бота

- `/start` — запускает онбординг для нового пользователя или показывает хаб действий для returning user.
- `/settings` — настройки фильтров, пауза рассылки, управление подпиской.
- `/stats` — временно отключена (вернётся после релиза в обновлённом виде).
- `/stop` — отписка от рассылки.
- Постоянная клавиатура `ReplyKeyboardMarkup`: кнопки `Вакансии` и `Настройки` закрепляются после онбординга и остаются до `/stop`.

## Структура проекта

```text
prodradar/
├── .github/
│   └── workflows/
│       └── collect.yml            # cron-сбор вакансий
├── api/
│   └── webhook.py                 # webhook для Telegram update/message/callback_query
├── bot/
│   ├── __init__.py
│   ├── handlers.py                # обработчики команд, callback-логика, выдача вакансий
│   ├── onboarding.py              # state machine онбординга и тексты шагов
│   ├── settings.py                # UI и логика меню настроек
│   └── telegram_api.py            # единая обёртка над Telegram Bot API
├── database/
│   ├── __init__.py
│   └── supabase_client.py         # доступ к Supabase и delivery-операции
├── delivery/
│   ├── __init__.py
│   ├── filters.py                 # фильтрация вакансий по users.filters
│   └── telegram.py                # форматирование Telegram-сообщений и legacy-код
├── docs/
│   ├── api_spec.md                # спецификация внешних API компаний
│   ├── backlog.md                 # бэклог проекта
│   ├── bugs.md                    # лог исправленных багов
│   └── context.md                 # продуктовый контекст, решения и backlog
├── enrichment/
│   ├── __init__.py
│   ├── ai_summary.py              # AI-саммари вакансий
│   └── normalizer.py              # нормализация grade/experience/work_format
├── parsers/
│   ├── __init__.py                # PARSER_REGISTRY (16 парсеров, полный список здесь)
│   ├── base.py                    # базовый интерфейс BaseParser
│   ├── utils.py                   # вспомогательные функции парсеров
│   └── ...
├── AGENTS.md                      # инструкции для AI-агента
├── README.md                      # документация для разработчика
├── config.py                      # конфигурация проекта
├── main.py                        # cron-пайплайн парсинга, нормализации и доставки
├── requirements.txt               # Python-зависимости
└── vercel.json                    # конфигурация Vercel
```

## Компании-источники

| Компания | ID | Категория | Кастомные эмодзи |
| --- | --- | --- | --- |
| Яндекс | ya | IT | Да |
| Т-Банк | tbank | Финтех | Да |
| Альфа-Банк | alfa | Финтех | Да |
| Сбер | sber | Финтех | Да |
| Wildberries | wb | E-commerce | Да |
| Ozon | ozon | E-commerce | Да |
| Avito | avito | Классифайды | Да |
| VK | vk | IT | Да |
| Точка | tochka | Финтех | Да |
| Контур | kontur | SaaS | Да |
| Lamoda | lamoda | E-commerce | Да |
| ДомКлик | domclick | PropTech | Да |
| Циан | cian | PropTech | Да |
| Купер | kuper | FoodTech | Да |
| Dodo | dodo | FoodTech | Да |
| МТС | mts | Телеком | Да |
| МТС Банк | mts_bank | Финтех | Да |
| KION | kion | IT | Да |
| Юрент | urent | IT | Да |
| MWS.AI | mws_ai | SaaS | Да |

МТС, МТС Банк, KION, Юрент и MWS.AI обслуживаются одним парсером mts. Список расширяется до 22+ компаний к релизу.

## Как добавить нового парсера

1. Создать новый файл в `parsers/` по принципу «один парсер = один файл».
2. Унаследовать класс от `BaseParser`.
3. Реализовать `parse()`.
4. При необходимости реализовать `enrich()` для обогащения данными из API отдельной вакансии.
5. Зарегистрировать парсер в `PARSER_REGISTRY` в `parsers/__init__.py`.
6. Добавить запись о компании в таблицу `companies` в Supabase.
7. Если у компании есть `custom_emoji_id` — добавить его в таблицу `companies`.
8. Словарь вакансии из `parse()` не должен содержать служебных полей (с префиксом `_` или отсутствующих в таблице `vacancies`). Для передачи данных между `parse()` и `enrich()` использовать атрибут экземпляра (`self._mapping`).
9. Если API требует динамический ключ (токен из HTML страницы) — парсер получает его при каждом запуске через `GET + regex`. Не хардкодить ключи.

## Деплой

### Переменные окружения

Минимально нужны:

- `SUPABASE_URL`
- `SUPABASE_KEY`
- `TELEGRAM_BOT_TOKEN`
- `ADMIN_CHAT_ID`
- `TELEGRAM_WEBHOOK_SECRET` (обязателен, без него webhook возвращает 500)

### Инфраструктура

- **Vercel** — принимает webhook от Telegram.
- **GitHub Actions** — запускает cron-сбор вакансий дважды в день.

### Проверка тестового окружения

Границы рефреша, подтверждённое состояние и поручение следующему чату описаны
в [плане фаз](docs/refresh_plan.md). Прежний флоу тестового бота проверен
пользователем; delivery подтверждён в отдельной БД.

Для рефреша используется бот `@ProdRadar_bot` и отдельное окружение GitHub Actions
`prodradar-test`. Настройки существующего сборщика остаются в его прежнем окружении.

В `Settings → Environments → prodradar-test` заполнить:

| Раздел | Имена |
| --- | --- |
| Environment variables | `SUPABASE_URL`, `ADMIN_CHAT_ID` |
| Environment secrets | `SUPABASE_KEY`, `TELEGRAM_BOT_TOKEN`, `HH_ACCESS_TOKEN` |

Workflow `Check Test Environment` читает URL и ID через `vars`, ключи и токены —
через `secrets`. Дубли URL/ID в secrets не используются. По умолчанию он выполняет только
SELECT в Supabase (включая проверку доступа к `description`), Telegram
`getMe`/`getWebhookInfo`/`getChat` и один запрос вакансий HH. Он не меняет webhook,
не записывает данные и не отправляет сообщения. Безопасный JSON-отчёт сохраняется
как artifact на 7 дней; значения ключей и тексты вакансий в отчёт не попадают.

В текущей ветке отдельный `collect_test.yml` ещё не зарегистрирован в Actions.
Ручной сбор доступен через уже зарегистрированный `Check Test Environment`:
в `Run workflow` выбрать `codex/restore-test-bot` и включить `collect_test`, либо:

```bash
gh workflow run 372368844 --repo Zadnessa/prodradar --ref codex/restore-test-bot -f collect_test=true
```

Без этого флага workflow остаётся read-only, в том числе при push. Сбор начинается
только после успешной проверки доступов, использует environment `prodradar-test`,
проверяет изоляцию через `collect_test.py` и не включает cron.

Локальная проверка с переменными текущего процесса:

```bash
python scripts/check_environment.py --require-hh
```

Для проверки управления размещением добавить в среду Codex сетевой секрет
`VERCEL_TOKEN` с доменом `api.vercel.com` и выполнить:

```bash
python scripts/check_environment.py --require-hh --require-vercel
```

Vercel проверяется только если передан токен; GitHub-диагностика его не требует.
Отсутствующий обязательный доступ или неуспешный API-запрос дают exit code 1.
Наличие webhook в Telegram не подтверждает работоспособность его обработчика:
HTTP-проверка и тест пользовательского флоу выполняются отдельно после настройки
размещения. `TELEGRAM_WEBHOOK_SECRET` для этих read-only проверок не требуется.

## Проверка и восстановление источников

- `python scripts/audit_sources.py --output reports/sources.json` проверяет включённые
  парсеры, пагинацию, контракт карточек и примеры полных описаний без записи в БД
  и отправки сообщений. Можно ограничить источники через `--sources 2gis lamoda`.
  Ошибки и нарушения контрактов дают ненулевой exit code; пустой корректный список
  отделён от ошибки API. Workflow `Audit Sources (Read Only)` повторяет проверку
  в GitHub Actions с environment `prodradar-test`.
  `--full-enrich-sources alfa tochka tbank domclick aviasales` проверяет все
  product-описания этих источников в единственном сборе; Т-Банк дополнительно
  подтверждает полные HTML-секции и включает «Мы предлагаем» в description.
  Отдельный job `bank_contracts` проверяет все описания банков с `--no-browser`,
  чтобы установка Chromium не блокировала проверку их публичных API.
  Общий job использует `--exclude-sources tbank`: Т-Банк не опрашивается
  одновременно дважды. Concurrency отменяет предыдущий audit той же ветки.
  Для Т-Банка отчёт содержит `api_collected_count` и `api_total_count` до
  объединения по городам; фирменный query выбирает IT/back-office.
  API отдаёт по 10 строк, поэтому bounded parse timeout Т-Банка в audit —
  360 секунд при паузах между страницами; остальные источники — 180 секунд.
  Т-Банк повторяет 429 с паузами 30/60 секунд и соблюдает Retry-After;
  более длинное ожидание оставляет источник ошибкой до следующего сбора.
  Audit явно показывает восстановленные rate limits и требует полный результат.
  Actions 36919821912 подтвердил 385/385 строк, 25/25 полных описаний
  и семь восстановленных 429 (627,8 секунды для bank audit Т-Банка).
  Для HTML-описаний оставлена пауза 5 секунд; audit timeout одного enrichment
  Т-Банка — 150 секунд, чтобы не обрывать разрешённые повторы 30/60 секунд.
- `python scripts/backup_database.py /path/outside/repository/snapshot` выгружает
  шесть таблиц в NDJSON, OpenAPI и manifest с количеством строк и SHA-256.
  Используйте ключ, видящий пользовательские таблицы. Выгрузка ограничивает
  верхний первичный ключ, проверяет число строк до/после и не перезаписывает каталог.
  Это REST-снимок, не транзакционный PostgreSQL dump; SQL-схема, RLS, индексы,
  триггеры и изменения существующих строк сохраняются/проверяются отдельно.
- `python -m unittest discover -s tests -v` запускает регрессии контрактов и выгрузки.
- МТС Линк использует публичный фирменный API без Bearer. Aviasales и МТС Линк
  читают общий список: прежние специализация/categoryId возвращали ложные `[]`.
- ДомКлик использует текущий API `/api/v1/vacancy/` с пагинацией и
  `/api/v1/vacancy/detail/{slug}/` для полного описания; нужны Referer/Sec-Fetch.
- Dodo получает backend из публичного Nuxt config при каждом запуске.
- Альфа, Точка и Т-Банк используют дополнительную официальную цепочку CA только
  для своих hosts. Т-Банк читает IT-каталог с плоскими limit/offset, проверяя
  totalCount; прежняя вложенная пагинация давала ложный пустой ответ.
- `python scripts/inspect_source_browser.py --output reports/browser.json`
  собирает DevTools-метаданные страниц без сохранения значений cookies/токенов.
  Такой же отчёт сохраняется в read-only Actions audit. Браузер не выгружает
  вакансии. Для отдельного исследования публичного POST каталога Т-Банка
  используйте явный `--probe-tbank-pagination`; в обычном audit клика нет.
- `python scripts/check_source_tls.py --output reports/tls.json` в GitHub Actions
  сравнивает TLS банков с системными и официальными дополнительными CA.
  Происхождение цепочки и границы доверия: `parsers/certificates/README.md`.
  В облачном runtime с обязательным proxy этот прямой TLS-пробник не запускать.
- `python scripts/inspect_bank_api.py --output reports/banks.json` сравнивает
  структуру публичного API Т-Банка с прежним фильтром и без фильтра, без секретов.
  В Actions Chromium получает временный пользовательский root CA через
  `inspect_source_browser.py --source-ca`; после диагностики сертификат удаляется.
- `python scripts/backup_schema.py /path/sql --project-ref PROJECT_REF` сохраняет
  прикладную SQL-схему public, RLS, индексы, sequences и ACL через Management API
  (`SUPABASE_ACCESS_TOKEN`). Внутренние схемы платформы не входят в копию.
- `python scripts/provision_test_database.py --project-ref TEST_REF --schema-directory /path/sql --data-directory /path/snapshot`
  восстанавливает схему и справочники в пустом отдельном проекте, сверяя SHA-256.
  Пользователи, вакансии и история в тест не копируются. Default privileges
  платформенных ролей должны уже точно совпадать с копией: облачный postgres
  не может менять supabase_admin; несовпадение останавливает provision до записи.
- `python scripts/collect_test.py --project-ref jmsdxgylyjxwdwmdrmxw` выполняет
  ручной тестовый сбор только после проверки новой БД, @ProdRadar_bot и списка
  пользователей. Workflow `Collect Test Vacancies (Manual Only)` не имеет cron;
  env `prodradar-test` необходимо сначала переключить на новую БД.
- Pipeline сохраняет успешные источники и отправляет admin report, затем завершает
  процесс с ошибкой при проблемах сбора или доставки. Ошибка HH не возвращает
  частичный список как успешный результат. ДомКлик не маскирует HTTP 404 пустой выдачей.

## Статус восстановления

Тестовый [@ProdRadar_bot](https://t.me/ProdRadar_bot) размещён в существующем
`prodradar-test`, webhook ведёт на `https://prodradar-test.vercel.app/api/webhook`.
Подключена отдельная БД `jmsdxgylyjxwdwmdrmxw`: схема и справочники загружены,
пользовательская история исходного бота в тест не переносилась. Webhook принимает
Content-Length и HTTP chunked тела; запрос без секрета даёт 403. У тестового
Vercel-проекта отключена SSO-защита размещения для доступа Telegram.

В тесте сохранены 135 вакансий с полными описаниями. Локальный общий collector
завершился частично: после установки Chromium СберЗдоровье проверено отдельно,
пять источников ещё не проходят через proxy текущей среды. GitHub environment
`prodradar-test` не обновлён из-за 403. Cron не включён. Пользователь подтвердил
прежний флоу; в БД один пользователь и 22 записи delivered без потерянных
vacancy_id. Песочница T-052 завершена, полный сбор источников остаётся открытым.
Актуальная передача и критерии находятся в [docs/refresh_plan.md](docs/refresh_plan.md).


### Явные профили test/prod

Команды Codex запускаются через `scripts/run_profile.py` до импорта `config`:

```bash
python scripts/run_profile.py --profile test check --require-hh
python scripts/run_profile.py --profile test audit --sources alfa tbank vk --full-enrich-sources alfa tbank vk --output reports/sources.json
python scripts/run_profile.py --profile test collect --project-ref jmsdxgylyjxwdwmdrmxw
```

Профиль `test` требует `TEST_SUPABASE_URL`, `TEST_SUPABASE_KEY` и
`TEST_TELEGRAM_BOT_TOKEN`, проверяет БД `jmsdxgylyjxwdwmdrmxw` и identity
`@ProdRadar_bot`. Redirect устанавливается в `prodradar-test.vercel.app`.
`ADMIN_CHAT_ID` и HH остаются общими. Общие реквизиты БД/Telegram не используются
при отсутствии TEST_*. Выбор влияет только на дочерний процесс.

Будущий `prod` требует отдельные `PROD_SUPABASE_URL`, `PROD_SUPABASE_KEY`,
`PROD_TELEGRAM_BOT_TOKEN`, БД `ykbtejjedefibdgyfgov` и `@findproductjob_bot`.
Команда `collect-prod` предназначена для явно выбранного production;
в текущем восстановлении она не запускается. Переключение после импорта config
запрещено. Прямой тестовый collector без выбранного профиля отказывается работать.
Vercel webhook сохраняет установленную конфигурацию своего проекта.

`Check Test Environment` также имеет отдельный ручной `audit_sources=true`:
публичные справочники передаются JSON input `source_catalog` из тестовой БД.
Этот job не получает ключ БД или Telegram token, не сохраняет данные и не
отправляет сообщения. Полные публичные product-вакансии и raw IDs выгружаются
в artifact для проверки описаний. Обычный collector по-прежнему требует
обновлённый environment, успешный check и отдельный `collect_test=true`.


### Автоматическая настройка GitHub environment

В облачной среде Codex запросы api.github.com автоматически авторизуются
GitHub-приложением Codex; эта авторизация подменяет явный PAT, а приложение не
имеет Environments permission. Настройка выполняется отдельным Actions job,
в котором используется настоящий PAT из environment secret.

Единственный ручной шаг: GitHub → Settings → Environments → `prodradar-test` →
Environment secrets → Add environment secret:
`PRODRADAR_GITHUB_TOKEN` = существующий fine-grained PAT для Zadnessa/prodradar
с Environments read/write и Actions read/write. Добавление секрета выполняется
через GitHub UI: текущая интеграция Codex не имеет права создать его сама.

Дальше всё выполняет одна команда в Codex с выбранным test-профилем:

```bash
python -m pip install PyNaCl
python scripts/run_profile.py --profile test configure-github
```

Команда автоматически:
1. Запускает `Check Test Environment` с `setup_github=export-key` и получает
   публичный ключ тестового environment через annotation GitHub API.
2. Берёт реальный test service_role из Supabase Management API и test bot token
   из существующего Vercel `prodradar-test`, проверяет доступ к тестовой БД и
   identity `@ProdRadar_bot`, шифрует значения в памяти sealed box GitHub.
3. Запускает `setup_github=apply`: обновляет environment secrets `SUPABASE_KEY`,
   `TELEGRAM_BOT_TOKEN` и variables `SUPABASE_URL`, `ADMIN_CHAT_ID`. Значения
   секретов в inputs/logs не передаются: только ciphertext. Публичный ключ,
   repo/environment, test URL и набор имён проверяются до первой записи.
4. Запускает отдельный read-only check реальных API с `collect_test=false`.
   Существующий environment `HH_ACCESS_TOKEN` сохраняется и проверяется.

Повторный запуск безопасен при частичной настройке; смена публичного ключа
останавливает запись старого пакета. Скрипты не обращаются к repo Secrets,
production environment или исходному Telegram token. Сбор и доставка этой
командой не запускаются. `prepare-github` и `setup_test_github.py` позволяют
выполнить отдельные этапы; основной путь — `configure-github`.


### Бесплатный Vercel: зависимости и старые деплои

`requirements.txt` содержит только зависимости HTTP webhook/redirect; сборщик
и Playwright устанавливаются отдельным `requirements-collector.txt` в Actions.
`.vercelignore` исключает parsers/scripts/tests/docs и сборщик из пакета функций.
В `vercel.json` отключены Git preview deployments только ветки
`codex/restore-test-bot`; ручное test размещение сохраняется. Это предотвращает
накопление тяжёлых preview при каждом коммите восстановления.

```bash
python scripts/vercel_storage.py
python scripts/vercel_storage.py --apply
```

По умолчанию скрипт только показывает план очистки. Он полностью читает
страницы deployments/aliases двух известных проектов, сохраняет все active
aliases и два последних здоровых production deployments. Original historical
production остаётся защищённым; удаляются только непривязанные preview и
устаревшие test deployments. Перед каждым удалением защита проверяется заново;
ошибка/неполная пагинация останавливает очистку. Cron не добавлен.

1 октября 2026 (UTC) удалены 28 устаревших deployments (26 original preview и
2 test); после двух новых компактных test сборок осталось 26 вместо 52.
Все 28 alias bindings сохранены. Test production dpl_8MRFgWvvZ2FSwrRTfqsA9iRwres9
проверен на стабильном домене: unauth webhook 403, auth unknown user 200,
redirect без цели 400. Original production не переразмещался. Повторный dry-run
не нашёл кандидатов для безопасной очистки.
Размер установленного Python dependency tree уменьшен с 223 до 39 МБ;
фактическая квота Function Storage зависит от упаковки/дедупликации Vercel и
не определяется суммой этих оценок.

### Диагностика текущих источников

В `Check Test Environment` input `inspect_sources` запускает только read-only
браузерную и HTTP/Chrome-TLS проверку указанных имён, например `mts vk kuper`.
Job не получает DB/Telegram secrets; отчёт содержит публичные пути, статусы,
JSON-схемы и имена cookies/headers. Значения credentials не записываются.
Live `Audit Sources` запускается вручную: push не повторяет сетевой аудит и
не конкурирует со сборщиком за лимиты источников.

Т-Банк допускает до двух повторов одного read-only запроса при обрыве ответа;
MTS/VK проверяют полноту каталога. Недоступный Купер возвращает ошибку
источника: остальные собираются и доставляются, а итог явно отмечается
частичным. 403 не считается основанием для паузы как при origin 5xx.

Итог live collector 36935834198: 224 активные product-вакансии с описаниями
из 21 компании, 25/25 полных описаний Т-Банка, 10 scheduled карточек и одна
контрольная Т-Банка доставлены. В delivery 43 записи. Единственный blocked
источник — Купер 403; Dodo остаётся на прежней паузе, полного покрытия всех
компаний пока нет. Webhook pending=0, ошибок нет. 51 локальная регрессия проходит.

Новый test срез project/bizdev использует полный доступный пул:

```bash
python scripts/run_profile.py --profile test prepare-roles
python scripts/run_profile.py --profile test pool --project-ref jmsdxgylyjxwdwmdrmxw
python scripts/run_profile.py --profile test collect --project-ref jmsdxgylyjxwdwmdrmxw --use-source-pool
```

prepare-roles создаёт source_pool/статусы и поля роли только в test БД; pool
не отправляет карточки и не изменяет текущую выдачу. Check Test Environment
input capture_pool_only сохраняет пул; collect_test + use_source_pool
повторно фильтрует свежий проверенный пул, не повторяя список запросов API.
Тестовый профиль теперь project_bizdev, production профиль остаётся product.

В test-срезе project/bizdev сильные названия дополняются проверенными по
обязанностям алиасами компаний; project выше bizdev. Известный алиас при
live сборе сначала догружает detail API/HTML, затем проходит проверку цитат.
Монетизация не влияет на ранжирование. `pool` сохраняет общий каталог без
доставки; `collect --use-source-pool` использует только свежие успешные снимки.

Упрощённый test бот: первый `/start` начинает мини-онбординг «Привет, Катюша! :-)».
Один вопрос про грейды, возможность выбрать несколько или пропустить. После
подтверждения — общая лента проектов и развития бизнеса; две project карточки
чередуются с одной bizdev, пока обе группы доступны. Вакансия с обеими ролями
показывается один раз. Карточки отмечены «Проекты»/«Развитие бизнеса» и содержат
прямые ссылки работодателей: test click redirect отключён, product сохраняет его.
Следующий `/start` и кнопка «Вакансии» продолжают эту же ленту без повторного
опроса. `/settings` — грейды, скрытые компании, пауза; старые city/company/strict
фильтры не ограничивают этот флоу. `/pause` и `/stop` ставят рассылку на паузу,
ручной просмотр доступен. `/start` не отменяет выбранную паузу. История доставки
не сбрасывается; явный повтор — «Посмотреть текущие ещё раз» (`sm:seen:all:offset`).
До завершения онбординга карточки не отправляются ни вручную, ни сборщиком.
Подробный сценарий и выводы виртуального walkthrough: [docs/test_bot_flow.md](docs/test_bot_flow.md).

Адресное восстановление пула: workflow `capture_pool_only=true` и
`inspect_sources="alfa sber tbank"`. Для него и cached collect проверка
`--skip-hh` не обращается к несвязанному HH API; полномасштабный live сбор
сохраняет обязательную проверку HH.

Офлайн-измерение title-среза: `python scripts/evaluate_role_slice.py --pool
/tmp/prodradar-full-pool.json --output reports/project_bizdev`. Ручная разметка
хранится в `tests/fixtures/project_bizdev_gold.json`; precision/recall относятся
к размеченным названиям, недоступные источники не включаются в знаменатель.

`evaluate_role_slice.py` также сохраняет `ablation.json`: общий пул → только
названные роли → технический blacklist → guard другой основной роли → проверенные алиасы компаний →
контрольный возврат legacy internship blacklist. Видны потери target каждого
шага и потери от возврата product native групп Alfa/VK/Ozon. Стажировки с
явным project/bizdev названием сохранены: автоматическое отсечение теряет
целевые роли; пользовательский грейд остаётся отдельным выбором.

Уточнённая цель среза: 95% релевантных ролей внутри подходящих native групп
компаний, не 95% всех вакансий компании. `review-roles` / workflow
`enrich_role_pool=true` сохраняет полные описания близких/native кандидатов
в `role_reviews`, не отправляя сообщения и не меняя core vacancies. Затем
близкое название может стать алиасом компании в `delivery/role_aliases.py`
только с цитатами обязанностей и положительными/отрицательными регрессами.
Общие каталоги остаются материалом для поиска пропусков и абляции групп.

`native_role_cohorts.py` оценивает полный размеченный native срез по ID
и функциям (`tests/fixtures/native_role_cohorts.json`): Ozon107/партнёры,
VK2261/specialty263, Sber project specializations, WB project direction.
`native_cohorts.json` отделяет новые/переписанные и отсутствующие IDs от
проверенных; 100% calibration не означает независимые 95% всех компаний.
В main/user выдаче скрыты disabled компании, все страницы загружаются до
grade/mute фильтрации. `source_json` сохраняет native metadata API МТС,
МТС Линк, Авиасейлс и Lamoda для следующего аудита групп.

Отчёт о размерах категорий работодателей, долях отбора и ошибках:
[docs/test_role_slice.md](docs/test_role_slice.md). `selection_rate` считается
от всех записей группы; recall только от подтверждённых положительных ролей.

Текущий test срез в @ProdRadar_bot: первый `/start` — короткий вопрос про грейд,
затем общая project/bizdev лента. Снимок от2 октября2026:248 project,132 bizdev
(6 пересечений). Объём и ограничения native полноты — в отчёте выше.
Исходный бот не переключён.

В test основные кнопки продолжения после грейдов и возврата из настроек
в ленту — зелёные (native Telegram style=success). Тестовый сбор остаётся
ручным: собственного cron пока нет. Original schedule10:00/19:00 Москва
отключён GitHub за неактивность; просмотр карточек сам не обновляет каталог.

Тестовый @ProdRadar_bot обновляется отдельным GitHub расписанием с3 октября2026:
10:00 и19:00 Москва. Код берётся из codex/restore-test-bot, только test secrets;
исходный product workflow остаётся отключённым. Контракт и ручная проверка без
доставки: [docs/test_schedule.md](docs/test_schedule.md).
