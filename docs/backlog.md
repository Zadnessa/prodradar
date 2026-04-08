# Бэклог ProductRadar

## Правила ведения:

- Документ имеет ровно 4 секции: «До релиза», «После релиза», «Бэклог», «Архив». Новые секции и подсекции не создаются без явного решения.
- Секция «Бэклог» имеет фиксированные подзаголовки: Парсеры, AI, HH-сканер, Аналитика рынка, Инфра. Новые подзаголовки не создаются без явного решения.
- Формат задачи: - [ ] Краткое описание (файлы). Одна строка, без вложенных списков, без абзацев.
- Выполненная задача помечается [x] и переносится в «Архив». Удалять задачи запрещено.
- Новые задачи добавляются в конец соответствующей секции. Порядок внутри секции не меняется без явного указания.
- Статус [?] — задача с неопределённым состоянием, требует ручной проверки. Не трогать без явного указания.

## До релиза

- [ ] Написание и тестирование парсеров (parsers/).
- [ ] Для каждого нового парсера — INSERT в таблицу companies в Supabase (parsers/, database/).
- [ ] Формат выдачи вакансий: довести трёхэтапную модель announced/delivered до полностью завершённого состояния (bot/handlers.py, delivery/telegram.py).
- [ ] Stream 3C: ReplyKeyboardMarkup с двумя кнопками «Вакансии» и «Настройки» в постоянном UX-потоке (bot/handlers.py, bot/telegram_api.py).
- [ ] Полная ревизия текстов бота — строго после функциональных тестов (bot/).
- [ ] Ревизия quick-path текстов без strict_mode disclaimer и с честной сводкой «весь рынок» (bot/handlers.py).
- [ ] `Начать заново` сбрасывает только фильтры, без очистки delivery-истории (bot/handlers.py, delivery/).
- [ ] После onboarding/settings показывать выбор `N новых + M ранее просмотренных` → `Показать все` / `Только новые` (bot/handlers.py, delivery/telegram.py).
- [ ] В `/settings` показывать кнопку `Заблокированные (N)` только если `N > 0` (bot/handlers.py).
- [ ] Stream 3F: BUG-067 — не передавать ReplyKeyboardMarkup в editMessageText (bot/handlers.py, bot/telegram_api.py).
- [ ] Stream 3F: Толерантная обработка битых вакансий — skipped_count, не падать на одной записи (main.py).
- [ ] Stream 3F: Устойчивое сохранение — чанки, retry, поштучный fallback, finally для admin report (main.py, database/supabase_client.py).
- [ ] Stream 3F: SELECT без source_json — убрать поле из runtime-запросов к vacancies (database/supabase_client.py).
- [ ] Stream 3F: Контрактный тест — `vacancy.company` совпадает с `companies.name` (tests/, parsers/).
- [ ] Stream 3F: MTS Link bearer-токен вынести в env, добавить обработку 401 и skip без падения пайплайна (parsers/mtslink.py, config.py).
- [ ] Stream 3F: insert_vacancies заменить на upsert с чанками по 50 (database/supabase_client.py).
- [ ] Stream 3F: Удалить вызов generate_summary() из _prepare_vacancy (main.py).
- [ ] Stream 3F: MTS enrich — description только если новое длиннее текущего (parsers/mts.py).
- [ ] Stream 3F: Добавить REDIRECT_BASE_URL в env блок collect.yml (.github/workflows/collect.yml).
- [ ] Wave 4a: Код-ревью от внешнего аудитора (подготовить цели/промпт и провести аудит) (docs/, репозиторий).
- [ ] Wave 4a: Фиксы по результатам код-ревью (репозиторий).
- [ ] Wave 4a: Проверить необработанные исключения, способные уронить весь пайплайн (main.py, parsers/).
- [ ] Wave 4a: Проверить соответствие main.py порядку из AGENTS.md (main.py, AGENTS.md).
- [ ] Wave 4a: Проверить рассинхрон документации и кода (AGENTS.md, docs/context.md, код).
- [ ] Wave 4a: Проверить контракт BaseParser — MTS нарушает, зафиксировать и исправить (parsers/mts.py).
- [ ] Wave 4c: SQL-проверки data integrity (Supabase).
- [ ] Wave 4c: Проверить, что все companies.parser_name зарегистрированы в PARSER_REGISTRY (database/, parsers/__init__.py).
- [ ] Wave 4c: Проверить отсутствие orphan-записей в user_vacancy_delivery (database/).
- [ ] Wave 4c: Выполнить проверки после финального сброса и полного прогона парсеров (main.py, database/).
- [ ] Wave 4d: Функциональные тесты всех основных сценариев (bot/handlers.py, delivery/, main.py).
- [ ] Wave 4d: Критерий — все кнопки/тексты/колбэки работают без зависаний (bot/handlers.py).
- [ ] Stream 3F: Scheduled-intro без «по твоим фильтрам» для quick-path пользователей (bot/handlers.py).

## После релиза

- [ ] On-demand витрина и ранжирование: первая пачка — витрина, дальше — релевантностное ранжирование (delivery/telegram.py, bot/handlers.py).
- [ ] Сводка `N новых + M ранее просмотренных` в scheduled/выдаче (delivery/telegram.py, bot/handlers.py).
- [ ] Scheduled: сценарий `new=0, announced>0` с action-oriented кнопками (bot/handlers.py).
- [ ] Уплотнение служебных сообщений без дублей в mute/returning /start (bot/handlers.py).
- [ ] Лонгрид Telegraph и ссылка из сводки перед первой выдачей (docs/, bot/handlers.py).
- [ ] career_url в companies + гиперссылка на название компании (database/supabase_client.py, delivery/telegram.py).
- [ ] Кластеризация похожих вакансий в выдаче (delivery/filters.py, delivery/telegram.py).
- [ ] Каталог с навигацией по кластерам вместо плоской пагинации (bot/handlers.py, delivery/telegram.py).
- [ ] Дайджест как альтернативный формат выдачи (delivery/telegram.py).
- [ ] Верифицировать referer-policy карьерных сайтов при >100 пользователей (parsers/).
- [ ] Песочница debug.yml (.github/workflows/).
- [ ] CustDev: 5-7 интервью с целевыми пользователями (docs/).
- [ ] Метрики: retention, time-to-first-relevant-vacancy (database/, docs/).
- [ ] SQL-запросы для 9 продуктовых гипотез (после появления первых данных) (database/, docs/).
- [ ] /broadcast: Colab-скрипт, затем полноценная команда (scripts/, bot/handlers.py).
- [ ] /stats переработка: «всего на рынке», «под фильтры», «просмотрено», «новых» (bot/handlers.py, database/supabase_client.py).
- [ ] Дашборд аналитики — отложить до VPS (docs/, infra/).
- [ ] Аудит хардкода по всем парсерам: полный скан 28 парсеров, замена хардкода на конфиг/БД (parsers/).
- [ ] Сбор фидбека по формату выдачи (карточки vs дайджест) (docs/).
- [ ] Inline mute-кнопка на карточке вакансии (delivery/telegram.py, bot/handlers.py).

## Бэклог

### Парсеры

- [ ] Wave 6: Транспортный слой transport.py с retry/backoff/timeout и уважением Retry-After (parsers/transport.py, parsers/).
- [ ] Wave 6: Типизированные исключения парсеров и классификация в админ-отчёте (parsers/, main.py).
- [ ] Wave 6: self.logger в BaseParser и унификация логирования по парсерам (parsers/base_parser.py, parsers/).
- [ ] Wave 6: Счётчики операций в BaseParser + enrichment-статистика в админ-отчёте (parsers/base_parser.py, main.py).
- [ ] Wave 6: Retry/backoff для enrichment-запросов (parsers/).
- [ ] Wave 6: Debug-артефакты (HTML/JSON/screenshot/trace) как GitHub Actions artifacts (parsers/, .github/workflows/).
- [ ] Wave 6: Общий HTML-extractor с quality_score и источником description (parsers/, utils/).
- [ ] Wave 6: Перевести хрупкие парсеры (T-Bank, Точка, VK, Avito, Циан) на общий extractor (parsers/).
- [ ] Wave 6: CI-тест на хешированные CSS-селекторы (tests/, CI).
- [ ] Wave 6: Автоэскалация http → browser по сигналам антибота/пустых данных (parsers/).
- [ ] Wave 6: Наблюдаемость парсеров (parser_status, last_success_at, last_item_count, consecutive_failures, browser_fallback_used, enrichment_quality_score) (main.py, reporting/).
- [ ] Wave 6: GenericJsonApiParser + parser_specs с JMESPath (parsers/, parser_specs/).
- [ ] Wave 6: Onboarding-kit для новых компаний и docs/new_company_checklist.md (docs/, parsers/).
- [ ] Wave 6: Fetcher-абстракция и fetch_method в companies (parsers/, database/).
- [ ] Wave 6: description_source (database/, parsers/).
- [ ] Wave 6: last_enriched_at (database/, parsers/).
- [ ] Wave 6: Тестовый режим компании через status в companies (database/, parsers/).
- [ ] Wave 6: sanitize_description как общая функция очистки HTML (utils/, parsers/).
- [ ] Wave 6: Хардинг delivery pipeline по нагрузке (SQL anti-join, батчинг Telegram, параллелизация) (delivery/, database/).
- [ ] Wave 6: Чистка хардкодов источников и общий extractor HTML-секций (parsers/).
- [ ] Wave 6: MTS Link — автоматическое получение токена или переход на HH как fallback-источник (parsers/mtslink.py, parsers/hh.py).
- [ ] Wave 6: Аудит всех парсеров на соблюдение контракта enrich() (parsers/).
- [ ] Wave 6: Фикстуры parsers и минимальные контрактные тесты parse/enrich (fixtures/, tests/).

### AI

- [ ] Создать архитектуру AI-фазы: таблица vacancy_ai_enrichment, LEFT JOIN при выдаче, kill switch (database/, delivery/, main.py).
- [ ] Создать таблицу vacancy_ai_enrichment (database/).
- [ ] Определение сегмента вакансии (B2B/B2C/e-com/fintech/classified) по описанию (ai/, prompts/).
- [ ] Определение сегмента на уровне вакансии (не компании) внутри экосистем (ai/, delivery/filters.py).
- [ ] Уточнение грейда по описанию (few-shot на Senior-выборке) (ai/).
- [ ] Генерация краткого описания для карточки (1 абзац) (ai/, delivery/telegram.py).
- [ ] Рыночная аналитика зарплат как отдельное AI/партнёрское направление (docs/, ai/).
- [ ] CJE-вакансии: вернуть в выдачу после AI-классификации описаний (ai/, main.py).
- [ ] Сбер: ловить PM-вакансии без продуктовых слов в заголовке через анализ description (ai/, parsers/sber.py).
- [ ] Dodo: проверить полноту данных (description/grade) при появлении PM-вакансий (parsers/dodo.py, ai/).
- [ ] Дедупликация описаний фирменный сайт vs HH через embeddings + cosine similarity (ai/, parsers/).
- [ ] Добавить ai_is_product и перенести серую зону в AI-классификацию (database/, ai/, main.py).
- [ ] Нормализация заголовков вакансий через LLM к формату `[Grade] [Функция] Product Manager` (ai/, main.py).
- [ ] Gray-зона фильтрации: AI-классификация `is_product + confidence + reason` по `title + description` (ai/, main.py).
- [ ] content_hash считать после enrichment и _prepare_vacancy (main.py).
- [ ] re-enrichment для вакансий с пустым/коротким description (main.py, ai/).
- [ ] Выделение raw-данных в отдельный журнал/таблицу (database/, main.py).

### HH-сканер

- [ ] Wave 8: Дедупликация вакансий через embeddings + cosine similarity (parsers/hh.py, ai/).
- [ ] Wave 8: HH.ru как валидатор полноты фирменных источников по employer_id (parsers/hh.py, reports/).
- [ ] Wave 8: Публичная документация HH API как источник ресерча (docs/).
- [ ] Wave 8: Применить трёхзонную фильтрацию Stream 3A в HH-сканере (config.py, parsers/hh.py).
- [ ] Wave 8: Единый HH-сканер с колонкой hh_employer_id в companies (database/, parsers/hh.py).

### Аналитика рынка

- [ ] Wave 9: Добавить deactivated_at в vacancies (database/).
- [ ] Wave 9: Аналитика времени жизни вакансий (медиана по компаниям и отраслям) (analytics/, database/).
- [ ] Wave 9: Динамика открытий/закрытий по неделям и месяцам (analytics/, database/).
- [ ] Wave 9: Сезонность найма по отраслям (analytics/, database/).
- [ ] Wave 9: Интеграция аналитики в /stats или отдельный дашборд (bot/handlers.py, analytics/).

### Инфра

- [ ] Wave 10: Переезд на VPS с бэкапами и планом замены webhook.py на FastAPI (infra/, webhook.py).
- [ ] Wave 10: Довести ENV-based конфигурацию до конца (config.py, infra/).
- [ ] Wave 10: Расшивка main.py на отдельные модули сбора/обогащения/доставки (main.py, modules/).
- [ ] Wave 10: Расшивка bot/handlers.py на onboarding/settings/delivery модули (bot/handlers.py, bot/).
- [ ] Wave 10: Расшивка SupabaseService на доменные репозитории (database/supabase_client.py, database/).
- [ ] Wave 10: Дашборд аналитики (Metabase/Grafana) после переезда на VPS (infra/, analytics/).

## Архив

- [x] Wave 1: Удалить мёртвый код deliver_vacancies() и send_telegram_message() (delivery/telegram.py).
- [x] Wave 1: Удалить мёртвый код mark_vacancies_notified() и get_unnotified_vacancies() (database/supabase_client.py).
- [x] Wave 1: Удалить FINAL_TEXT (bot/handlers.py).
- [x] Wave 1: Переписать edit_message() через _post() (bot/telegram_api.py).
- [x] Wave 1: Удалить salary из парсеров Alfa и Sber (parsers/).
- [x] Wave 1: Переименовать short_description в description (database/, код).
- [x] Wave 1: Исправить _send_vacancies_chunk() — проверять send_message() перед sent_ids (bot/handlers.py).
- [x] Wave 1: Сделать TELEGRAM_WEBHOOK_SECRET обязательным (webhook.py).
- [x] Wave 1: Игнорировать webhook/callback для неизвестных chat_id (webhook.py, database/).
- [x] Wave 1: Деактивация вакансий per-company при ошибке парсера (main.py).
- [x] Wave 1: Зафиксировать контракт enrich() в AGENTS.md (AGENTS.md).
- [x] Wave 1: Привести docs/context.md в актуальное состояние (docs/context.md).
- [x] Wave 2: Кастомные эмодзи брендов из companies.custom_emoji_id (database/, delivery/telegram.py).
- [x] Wave 2: Блок «опубликовано» только при реальном published_at (delivery/telegram.py).
- [x] Wave 2: Сортировка выдачи published_at DESC, затем created_at DESC (database/supabase_client.py).
- [x] Stream 3A: Добавить Касперский (HH) (parsers/).
- [x] Stream 3A: Добавить Циан (HH) (parsers/).
- [x] Stream 3A: Добавить Звук (HH) (parsers/).
- [x] Stream 3A: Семантическое ядро PM-заголовков, whitelist/blacklist/grey-zone (config.py, scripts/, docs/).
- [x] Stream 3A: Единая трёхзонная фильтрация и рефакторинг main.py (main.py, config.py).
- [x] Stream 3B: Определить индустрии (docs/, database/).
- [x] Stream 3B: Привязать компании к индустриям и проверить распределение (database/).
- [x] Stream 3B: SQL-миграция category в companies (database/).
- [x] Stream 3C: Убрать шаг «компании» из онбординга (bot/handlers.py).
- [x] Stream 3C: Пагинированный /settings со списком компаний и blocked-first (bot/handlers.py).
- [x] Stream 3C: F8 title_confidence и сортировка выдачи (delivery/, database/).
- [x] Stream 3C: Виртуальная эмпатия по формату выдачи проведена (docs/).
- [x] Stream 3C: Кнопка «Показать вакансии» после unmute/unmute_all (`st:deliver`) (bot/handlers.py).
- [x] Stream 3D: Определить список событий аналитики (bot/handlers.py, database/).
- [x] Stream 3D: Выбрать хранилище user_events в Supabase (database/).
- [x] Stream 3D: Zero-impact fire-and-forget логирование событий (database/supabase_client.py, bot/handlers.py).
- [x] Stream 3D: Redirect `api/go` для vacancy_clicked + 302 (api/go, database/).
- [x] Stream 3D: Добавить language_code/is_premium/first_name/last_name в users (database/).
- [x] Stream 3F: Пагинация get_existing_vacancy_hashes() (database/supabase_client.py).
- [x] Stream 3F: Пагинация get_active_users() (database/supabase_client.py).
- [x] Stream 3F: Пагинация get_vacancy_stats() (database/supabase_client.py).
- [x] Stream 3F: Пагинация deactivate_missing_vacancies() для больших наборов (database/supabase_client.py).
- [x] Stream 3F: Пагинация Yandex-парсера (parsers/yandex.py).
- [x] Stream 3F: Единое логирование парсеров и per-parser статистика в админ-отчёте (main.py).
- [x] Stream 3F: Автообновление Chrome UA из CHROME_VERSION (config.py).
- [x] Wave 4b: CJM-прогон — зафиксировать как выполненный этап (docs/backlog.md).
- [x] Wave 8: Парсер HH.ru по employer_id (parsers/hh.py).
- [x] Wave 8: Реализован HH-парсер employer_id=1455 (parsers/hh.py).
- [x] Wave 8: Решение — HH как источник для hh_* и валидатор для фирменных парсеров (docs/, parsers/hh.py).
