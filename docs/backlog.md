# Бэклог ProductRadar

## Правила ведения

- Документ имеет ровно 4 секции: «До релиза», «После релиза», «Бэклог», «Архив». Новые секции и подсекции не создаются без явного решения.
- Секция «Бэклог» имеет фиксированные подзаголовки: Парсеры, AI, HH-сканер, Аналитика рынка, Инфра. Новые подзаголовки не создаются без явного решения.
- Формат задачи: `- [ ] Краткое описание (файлы)`. Одна строка, без вложенных списков, без абзацев.
- Каждая задача отвечает на три вопроса: ЧТО изменится (поведение), ГДЕ (файлы), КОГДА ГОТОВО (критерий). Если задачу можно прочитать двумя способами и получить разный код — формулировка недопустима. При сомнении — дополнить уточняющей фразой через точку с запятой, не выносить в подпункт.
- Выполненная задача помечается `[x]` и переносится в «Архив» с очисткой индекса T-XXX (только формулировка). Удалять задачи запрещено.
- Новые задачи добавляются в конец соответствующей секции. Порядок внутри секции не меняется без явного указания.
- Статус `[?]` — задача с неопределённым состоянием, требует ручной проверки. Не трогать без явного указания.


## До релиза

- [x] Витрина: заменить _grade_priority на grade_score по матрице пользовательского грейда; синхронизировать ранжирование on-demand и scheduled через delivery/ranking.py (delivery/ranking.py, bot/handlers.py, main.py).
- [x] T-002 Quick-path сводка: после ob:quick первая сводка явно сообщает «показываю весь рынок без фильтров» и предлагает /settings для настройки; strict_mode disclaimer не показывается quick-path пользователям (bot/handlers.py, bot/onboarding.py).
- [x] T-004 Сводка новых vs просмотренных: при любом входе в «Вакансии» (on-demand, after onboarding, after settings save) если есть и новые, и ранее announced вакансии — показывать «N новых + M ранее просмотренных» с кнопками «Показать все» / «Только новые» (bot/handlers.py, database/supabase_client.py).
- [x] T-006 BUG-067 — не передавать ReplyKeyboardMarkup в editMessageText (bot/handlers.py, bot/telegram_api.py).
- [x] T-007 Толерантная обработка битых вакансий: try/except вокруг _prepare_vacancy для каждой вакансии; битая запись пропускается без сохранения в БД; skipped_count агрегируется и выводится в admin report (main.py).
- [x] T-008 Устойчивое сохранение: insert/update/touch/deactivate чанками по 50; retry при transient-ошибках Supabase; при data error в чанке — поштучный fallback с логированием проблемной записи; admin report отправляется в finally даже при частичном падении пайплайна (main.py, database/supabase_client.py).
- [x] T-009 SELECT без source_json — убрать поле из runtime-запросов к vacancies (database/supabase_client.py).
- [x] T-011 insert_vacancies заменить на upsert с чанками по 50 (database/supabase_client.py).
- [x] T-012 Удалить вызов generate_summary() из _prepare_vacancy (main.py).
- [x] T-014 Ручная проверка: порядок этапов в main.py (parse → blacklist → whitelist → content_hash → enrich → normalize) соответствует AGENTS.md; при расхождении — зафиксировать задачу на фикс (main.py, AGENTS.md).
- [x] T-015 Ручная проверка: callback-префиксы, архитектурные правила и контракты в AGENTS.md и context.md соответствуют реальному коду; устаревшие пункты — удалить или обновить (AGENTS.md, docs/context.md).
- [x] T-016 Проверка контракта enrich(): прогнать все парсеры с enrich-методом и убедиться, что ни один не перезаписывает заполненные поля и заменяет description только если новое длиннее; MTS — известное нарушение, исправляется задачей 13 (parsers/).
- [x] T-017 SQL-проверки data integrity (Supabase).
- [x] T-018 Проверить, что все companies.parser_name зарегистрированы в PARSER_REGISTRY (database/, parsers/__init__.py).
- [x] T-019 Проверить отсутствие orphan-записей в user_vacancy_delivery (database/).
- [ ] T-020 Выполнить проверки после финального сброса и полного прогона парсеров (main.py, database/).
- [ ] T-021 Ручной тест-прогон: пройти сценарии /start (новый), /start (returning), онбординг полный цикл, quick-path, settings toggle, mute/unmute/unmute_all, /blocked, пагинация (Ещё 10, Все, Хватит), scheduled-рассылка, /stats, /stop; чеклист составляется отдельно перед прогоном (bot/, delivery/, main.py).
- [x] T-022 Scheduled-intro без «по твоим фильтрам» для quick-path пользователей (bot/handlers.py).
- [x] T-023 Уплотнить mute/unmute/unmute_all: каждый сценарий завершается одним сообщением (edit) с inline-кнопкой действия, без второго дублирующего send_message; делать совместно с BUG-067 (bot/handlers.py).
- [x] T-048 Убрать прямой db.client.table из _count_delivered_before_request; использовать метод SupabaseService.count_delivered (bot/handlers.py, database/supabase_client.py).
- [ ] T-024 Полная ревизия текстов бота — строго после функциональных тестов (bot/).

## После релиза
- [ ] T-010 Контрактный тест: для каждого парсера из PARSER_REGISTRY прогнать parse() на фикстуре и проверить, что все vacancy["company"] присутствуют в companies.name; тест падает при рассинхроне (tests/, parsers/, fixtures/).
- [ ] T-025 MTS Link bearer-токен вынести в env, добавить обработку 401 и skip без падения пайплайна (parsers/mtslink.py, config.py).
- [ ] T-026 On-demand витрина и ранжирование: первая пачка — витрина, дальше — релевантностное ранжирование (delivery/telegram.py, bot/handlers.py).
- [ ] T-027 Сводка `N новых + M ранее просмотренных` в scheduled/выдаче (delivery/telegram.py, bot/handlers.py).
- [ ] T-028 Scheduled: сценарий `new=0, announced>0` с action-oriented кнопками (bot/handlers.py).
- [ ] T-029 Уплотнение служебных сообщений без дублей в mute/returning /start (bot/handlers.py).
- [ ] T-030 Лонгрид Telegraph и ссылка из сводки перед первой выдачей (docs/, bot/handlers.py).
- [ ] T-031 career_url в companies + гиперссылка на название компании (database/supabase_client.py, delivery/telegram.py).
- [ ] T-032 Кластеризация похожих вакансий в выдаче (delivery/filters.py, delivery/telegram.py).
- [ ] T-033 Каталог с навигацией по кластерам вместо плоской пагинации (bot/handlers.py, delivery/telegram.py).
- [ ] T-034 Дайджест как альтернативный формат выдачи (delivery/telegram.py).
- [ ] T-035 Верифицировать referer-policy карьерных сайтов при >100 пользователей (parsers/).
- [ ] T-036 Песочница debug.yml (.github/workflows/).
- [ ] T-037 CustDev: 5-7 интервью с целевыми пользователями (docs/).
- [ ] T-038 Метрики: retention, time-to-first-relevant-vacancy (database/, docs/).
- [ ] T-039 SQL-запросы для 9 продуктовых гипотез (после появления первых данных) (database/, docs/).
- [ ] T-040 /broadcast: Colab-скрипт, затем полноценная команда (scripts/, bot/handlers.py).
- [ ] T-041 /stats переработка: «всего на рынке», «под фильтры», «просмотрено», «новых» (bot/handlers.py, database/supabase_client.py).
- [ ] T-042 Дашборд аналитики — отложить до VPS (docs/, infra/).
- [ ] T-043 Аудит хардкода по всем парсерам: полный скан 28 парсеров, замена хардкода на конфиг/БД (parsers/).
- [ ] T-044 Сбор фидбека по формату выдачи (карточки vs дайджест) (docs/).
- [ ] T-045 Inline mute-кнопка на карточке вакансии (delivery/telegram.py, bot/handlers.py).
- [ ] T-049 VK enrich: добавить проверку existing значений grade и description перед перезаписью; description заменять только если len(new) > len(current) (parsers/vk.py).
- [ ] T-050 AGENTS.md: добавить callback-префиксы more:new:, more:new:all:, more:new:stop в документацию (AGENTS.md).
- [ ] T-051 Вернуть технические PM-вакансии после AI-классификации по категориям (классик, growth, tech, AI/ML); до AI-фазы отсекать blacklist-ом (config.py, ai/).

 
## Бэклог

### Парсеры

- [ ] Транспортный слой transport.py с retry/backoff/timeout и уважением Retry-After (parsers/transport.py, parsers/).
- [ ] Типизированные исключения парсеров и классификация в админ-отчёте (parsers/, main.py).
- [ ] self.logger в BaseParser и унификация логирования по парсерам (parsers/base_parser.py, parsers/).
- [ ] Счётчики операций в BaseParser + enrichment-статистика в админ-отчёте (parsers/base_parser.py, main.py).
- [ ] Retry/backoff для enrichment-запросов (parsers/).
- [ ] Debug-артефакты (HTML/JSON/screenshot/trace) как GitHub Actions artifacts (parsers/, .github/workflows/).
- [ ] Общий HTML-extractor с quality_score и источником description (parsers/, utils/).
- [ ] Перевести хрупкие парсеры (T-Bank, Точка, VK, Avito, Циан) на общий extractor (parsers/).
- [ ] CI-тест на хешированные CSS-селекторы (tests/, CI).
- [ ] Автоэскалация http → browser по сигналам антибота/пустых данных (parsers/).
- [ ] Наблюдаемость парсеров (parser_status, last_success_at, last_item_count, consecutive_failures, browser_fallback_used, enrichment_quality_score) (main.py, reporting/).
- [ ] GenericJsonApiParser + parser_specs с JMESPath (parsers/, parser_specs/).
- [ ] Onboarding-kit для новых компаний и docs/new_company_checklist.md (docs/, parsers/).
- [ ] Fetcher-абстракция и fetch_method в companies (parsers/, database/).
- [ ] description_source (database/, parsers/).
- [ ] last_enriched_at (database/, parsers/).
- [ ] Тестовый режим компании через status в companies (database/, parsers/).
- [ ] sanitize_description как общая функция очистки HTML (utils/, parsers/).
- [ ] Хардинг delivery pipeline по нагрузке (SQL anti-join, батчинг Telegram, параллелизация) (delivery/, database/).
- [ ] Чистка хардкодов источников и общий extractor HTML-секций (parsers/).
- [ ] MTS Link — автоматическое получение токена или переход на HH как fallback-источник (parsers/mtslink.py, parsers/hh.py).
- [ ] Аудит всех парсеров на соблюдение контракта enrich() (parsers/).
- [ ] Фикстуры parsers и минимальные контрактные тесты parse/enrich (fixtures/, tests/).

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

- [ ] Дедупликация вакансий через embeddings + cosine similarity (parsers/hh.py, ai/).
- [ ] HH.ru как валидатор полноты фирменных источников по employer_id (parsers/hh.py, reports/).
- [ ] Публичная документация HH API как источник ресерча (docs/).
- [ ] Применить трёхзонную фильтрацию Stream 3A в HH-сканере (config.py, parsers/hh.py).
- [ ] Единый HH-сканер с колонкой hh_employer_id в companies (database/, parsers/hh.py).

### Аналитика рынка

- [ ] Добавить deactivated_at в vacancies (database/).
- [ ] Аналитика времени жизни вакансий (медиана по компаниям и отраслям) (analytics/, database/).
- [ ] Динамика открытий/закрытий по неделям и месяцам (analytics/, database/).
- [ ] Сезонность найма по отраслям (analytics/, database/).
- [ ] Интеграция аналитики в /stats или отдельный дашборд (bot/handlers.py, analytics/).

### Инфра

- [ ] Переезд на VPS с бэкапами и планом замены webhook.py на FastAPI (infra/, webhook.py).
- [ ] Довести ENV-based конфигурацию до конца (config.py, infra/).
- [ ] Расшивка main.py на отдельные модули сбора/обогащения/доставки (main.py, modules/).
- [ ] Расшивка bot/handlers.py на onboarding/settings/delivery модули (bot/handlers.py, bot/).
- [ ] Расшивка SupabaseService на доменные репозитории (database/supabase_client.py, database/).
- [ ] Дашборд аналитики (Metabase/Grafana) после переезда на VPS (infra/, analytics/).

## Архив

- [x] Витрина: заменить _grade_priority на grade_score по матрице пользовательского грейда; синхронизировать ранжирование on-demand и scheduled через delivery/ranking.py (delivery/ranking.py, bot/handlers.py, main.py).
- [x] hub:reset: убрать вызов clear_delivery_history(); сброс обнуляет только фильтры и перезапускает онбординг, ранее доставленные вакансии остаются в user_vacancy_delivery (bot/handlers.py).
- [x] В меню /settings показывать кнопку «Заблокированные (N)» только если excluded_companies не пуст; по нажатию вызывать handle_blocked — список замьюченных компаний с /unmute-командами (bot/handlers.py, bot/settings.py).
- [x] Толерантная обработка битых вакансий: try/except вокруг _prepare_vacancy для каждой вакансии; битая запись пропускается без сохранения в БД; skipped_count агрегируется и выводится в admin report (main.py).
- [x] Устойчивое сохранение: insert/update/touch/deactivate чанками по 50; retry при transient-ошибках Supabase; при data error в чанке — поштучный fallback с логированием проблемной записи; admin report отправляется в finally даже при частичном падении пайплайна (main.py, database/supabase_client.py).
- [x] SELECT без source_json — убрать поле из runtime-запросов к vacancies (database/supabase_client.py).
- [x] insert_vacancies заменить на upsert с чанками по 50 (database/supabase_client.py).
- [x] Удалить вызов generate_summary() из _prepare_vacancy (main.py).
- [x] Удалить мёртвый код deliver_vacancies() и send_telegram_message() (delivery/telegram.py).
- [x] Удалить мёртвый код mark_vacancies_notified() и get_unnotified_vacancies() (database/supabase_client.py).
- [x] Удалить FINAL_TEXT (bot/handlers.py).
- [x] Переписать edit_message() через _post() (bot/telegram_api.py).
- [x] Удалить salary из парсеров Alfa и Sber (parsers/).
- [x] Переименовать short_description в description (database/, код).
- [x] Исправить _send_vacancies_chunk() — проверять send_message() перед sent_ids (bot/handlers.py).
- [x] Сделать TELEGRAM_WEBHOOK_SECRET обязательным (webhook.py).
- [x] Игнорировать webhook/callback для неизвестных chat_id (webhook.py, database/).
- [x] Деактивация вакансий per-company при ошибке парсера (main.py).
- [x] Зафиксировать контракт enrich() в AGENTS.md (AGENTS.md).
- [x] Привести docs/context.md в актуальное состояние (docs/context.md).
- [x] Кастомные эмодзи брендов из companies.custom_emoji_id (database/, delivery/telegram.py).
- [x] Блок «опубликовано» только при реальном published_at (delivery/telegram.py).
- [x] Сортировка выдачи published_at DESC, затем created_at DESC (database/supabase_client.py).
- [x] Добавить Касперский (HH) (parsers/).
- [x] Добавить Циан (HH) (parsers/).
- [x] Добавить Звук (HH) (parsers/).
- [x] Семантическое ядро PM-заголовков, whitelist/blacklist/grey-zone (config.py, scripts/, docs/).
- [x] Единая трёхзонная фильтрация и рефакторинг main.py (main.py, config.py).
- [x] Определить индустрии (docs/, database/).
- [x] Привязать компании к индустриям и проверить распределение (database/).
- [x] SQL-миграция category в companies (database/).
- [x] Убрать шаг «компании» из онбординга (bot/handlers.py).
- [x] Пагинированный /settings со списком компаний и blocked-first (bot/handlers.py).
- [x] F8 title_confidence и сортировка выдачи (delivery/, database/).
- [x] Виртуальная эмпатия по формату выдачи проведена (docs/).
- [x] Кнопка «Показать вакансии» после unmute/unmute_all (`st:deliver`) (bot/handlers.py).
- [x] Определить список событий аналитики (bot/handlers.py, database/).
- [x] Выбрать хранилище user_events в Supabase (database/).
- [x] Zero-impact fire-and-forget логирование событий (database/supabase_client.py, bot/handlers.py).
- [x] Redirect `api/go` для vacancy_clicked + 302 (api/go, database/).
- [x] Добавить language_code/is_premium/first_name/last_name в users (database/).
- [x] Пагинация get_existing_vacancy_hashes() (database/supabase_client.py).
- [x] Пагинация get_active_users() (database/supabase_client.py).
- [x] Пагинация get_vacancy_stats() (database/supabase_client.py).
- [x] Пагинация deactivate_missing_vacancies() для больших наборов (database/supabase_client.py).
- [x] Пагинация Yandex-парсера (parsers/yandex.py).
- [x] Единое логирование парсеров и per-parser статистика в админ-отчёте (main.py).
- [x] Автообновление Chrome UA из CHROME_VERSION (config.py).
- [x] BUG-067 — не передавать ReplyKeyboardMarkup в editMessageText (bot/handlers.py, bot/telegram_api.py).
- [x] Уплотнить mute/unmute/unmute_all: каждый сценарий завершается одним сообщением (edit) с inline-кнопкой действия, без второго дублирующего send_message; делать совместно с BUG-067 (bot/handlers.py).
- [x] CJM-прогон — зафиксировать как выполненный этап (docs/backlog.md).
- [x] Парсер HH.ru по employer_id (parsers/hh.py).
- [x] Реализован HH-парсер employer_id=1455 (parsers/hh.py).
- [x] Решение — HH как источник для hh_* и валидатор для фирменных парсеров (docs/, parsers/hh.py).
- [x] Quick-path сводка: после ob:quick первая сводка явно сообщает «показываю весь рынок без фильтров» и предлагает /settings для настройки; strict_mode disclaimer не показывается quick-path пользователям (bot/handlers.py, bot/onboarding.py).
- [x] Сводка новых vs просмотренных: при любом входе в «Вакансии» (on-demand, after onboarding, after settings save) если есть и новые, и ранее announced вакансии — показывать «N новых + M ранее просмотренных» с кнопками «Показать все» / «Только новые» (bot/handlers.py, database/supabase_client.py).
- [x] Scheduled-intro без «по твоим фильтрам» для quick-path пользователей (bot/handlers.py).
- [x] On-demand витрина: первая пачка — топ по title_confidence, последующие — релевантностное ранжирование вместо хронологии; подбадривание показывается только после первого on-demand запроса пользователя (bot/handlers.py, delivery/telegram.py).
- [x] MTS enrich — description только если новое длиннее текущего (parsers/mts.py).
- [x] Вынести classify_title и title_confidence в delivery/ranking.py; вычислять on-the-fly вместо чтения из БД; убрать title_confidence из SELECT get_undelivered_vacancies (delivery/ranking.py, bot/handlers.py, main.py, database/supabase_client.py).
- [x] Обернуть _send_onboarding_batch в handle_main_keyboard_text в try/except; при ошибке — edit лоадера в сообщение об ошибке (bot/handlers.py).
- [x] Убрать прямой db.client.table из _count_delivered_before_request; использовать метод SupabaseService.count_delivered (bot/handlers.py, database/supabase_client.py).
