# Инструкции для AI-агентов

## Правила работы с репозиторием

- Всегда создавай новую ветку от актуального main
- Не трогай файлы, которые не указаны в задаче
- После изменений создавай PR
- Язык комментариев в коде и коммитов: русский

## Архитектурные принципы

- Список компаний, эмодзи и категории берутся из таблицы companies в Supabase, не хардкодить
- Города нормализуются через таблицу city_mappings в Supabase, не хардкодить
- Один парсер = один файл в parsers/
- Новый парсер обязательно добавляется в PARSER_REGISTRY в parsers/__init__.py
- Парсеры импортируются только через PARSER_REGISTRY, не через importlib
- Ошибка одного парсера не должна останавливать остальные
- Telegram-сообщения используют parse_mode="HTML", не Markdown
- Пустые поля (None, "", "Не указан") не отображаются в сообщениях пользователю
- Названия вакансий обрезать через .strip() перед сохранением
- Спецификация API находится в docs/api_spec.md — сверяйся с ней при работе с парсерами
- Парсеры могут переопределить enrich() для обогащения из API отдельной вакансии
- enrich() вызывается только для новых вакансий, перед normalizer
- enrich() не перезаписывает заполненные поля
- Ошибка enrichment не останавливает процесс
- Grade может быть диапазоном через тире: "Middle–Senior". Левая часть = минимальный грейд для фильтрации.
- При добавлении новой компании проверять: может ли API возвращать массив грейдов или диапазон min/max. Из 8 текущих компаний это встречается у Yandex (pro_level_min/max) и T-Bank (tags массив). Остальные отдают одиночные значения.
- Нерелевантные вакансии фильтруются по TITLE_STOP_PATTERNS в config.py (подстроковый поиск, регистронезависимый). Фильтрация в main.py до enrichment и сохранения.
- Lead+ не определяется автоматически из заголовка. Будет реализовано через AI-анализ description.
- В нормализованных строках experience и grade-диапазонах используется дефис (-), не тире (–).
- Доставка вакансий per-user через таблицу user_vacancy_delivery. Глобальный notified_at устарел.
- Telegram API вызовы только через bot/telegram_api.py. Не использовать requests.post к Telegram напрямую.
- Webhook валидирует X-Telegram-Bot-Api-Secret-Token если задана переменная TELEGRAM_WEBHOOK_SECRET.
- Webhook обрабатывает message и callback_query.
- Фильтрация по пользовательским настройкам в delivery/filters.py. Пустой filters = всё.
- paused=true — пользователь не получает рассылку, остаётся в базе.
- Вакансии старше VACANCY_TTL_DAYS не учитываются в статистике.
- Онбординг реализован как state machine в bot/onboarding.py. onboarding.py — чистая логика, не импортирует telegram_api или database. Состояние хранится в users.onboarding_step. Фильтры копятся в users.filters инкрементально при переходах между шагами. Промежуточное состояние toggle-кнопок живёт в reply_markup сообщения, не в БД.
- callback_data для онбординга имеет префикс "ob:" и формат ob:action или ob:action:value. Примеры: ob:quick, ob:g:Junior, ob:co:yandex, ob:next, ob:done.
- Все кнопки онбординга обновляют текущее сообщение через edit_message (не send_message). На шагах с запросами к БД сообщение сначала обновляется на лоадер (⏳), затем на результат.
- Avito: грейд определяется по префиксу заголовка в парсере (Ведущий → Senior, Руководитель/CPO/Head of → Lead+). Это исключение из правила BUG-009 — применяется только к Avito, где API не содержит данных о грейде.
- Т-Банк: tags Head и CPO маппятся в Lead+.
- work_format нормализуется через normalize_work_format в enrichment/normalizer.py. Стандартные значения: Офис, Удалёнка, Гибрид, Не указан. Множественные через запятую допустимы.
- grade нормализуется через normalize_grade: title case, запятая → дефис, Lead/Head/CPO → Lead+.
- Фильтрация (delivery/filters.py) устойчива к множественным значениям через запятую в city, work_format, grade.

## Исправленные баги (не повторять)

### BUG-001: importlib вместо PARSER_REGISTRY
Файл: main.py
Было: динамический импорт через importlib находил BaseParser и падал
Стало: from parsers import PARSER_REGISTRY

### BUG-002: Markdown вместо HTML в Telegram
Файл: delivery/telegram.py
Было: parse_mode="Markdown", обратные слэши в тексте
Стало: parse_mode="HTML", _escape_html, теги <b> и <a href>

### BUG-003: пустые заголовки в Avito
Файл: parsers/avito.py
Было: card.find("a") находил пустую ссылку-оверлей, title сохранялся пустым
Стало: используется селектор a.vacancies-section__item-name, заголовки извлекаются корректно

### BUG-004: отсутствующие грейд и опыт в Yandex
Файл: parsers/yandex.py
Было: грейд и опыт не определялись, т.к. pro_levels нет в объекте вакансии
Стало: грейд и опыт определяются из заголовка через guess_grade_from_title

### BUG-005: лишние пробелы в названиях вакансий
Файл: parsers/*.py
Было: title мог сохраняться с ведущими/замыкающими пробелами
Стало: title нормализуется через .strip() перед сохранением

### BUG-006: затирание short_description в main.py
Файл: main.py
Было: short_description всегда перезаписывался результатом generate_summary (None)
Стало: generate_summary вызывается только если short_description отсутствует

### BUG-007: грейды Yandex через фильтр pro_levels
Файл: parsers/yandex.py
Было: грейд/опыт определялись только из заголовка
Стало: данные собираются отдельными запросами по pro_levels с дедупликацией по приоритету грейда и fallback-запросом без pro_levels

### BUG-008: Yandex pro_levels не определяет грейд вакансии
Файл: parsers/yandex.py
Было: 4 запроса по pro_levels + дедупликация по приоритету грейда
Стало: один запрос без pro_levels, grade определяется через normalizer или enrichment API
Причина: pro_levels — фильтр допустимого уровня кандидата, а не грейд самой вакансии. API возвращает одну и ту же вакансию на всех уровнях.

### BUG-009: grade угадывался из заголовка вакансии
Файл: enrichment/grade_guesser.py (удалён)
Было: guess_grade_from_title определял Junior/Middle/Senior по ключевым словам в заголовке
Стало: grade определяется только из фактических данных — поле grade API, маппинг experience → grade, или Lead+ по ключевым словам руководящих позиций. Файл заменён на enrichment/normalizer.py.

### BUG-010: Normalizer не покрывает краевые случаи experience
Файл: enrichment/normalizer.py
Было: строки "от 3 лет", "более 6 лет" не нормализовались
Стало: добавлен regex-fallback для любых строк с числами

### BUG-011: Telegram потерял полужирные подзаголовки
Файл: delivery/telegram.py
Было: поля выводились без <b> тегов
Стало: названия полей снова в <b>, но с маленькой буквы

### BUG-012: Yandex enrichment брал max вместо min pro_level
Файл: parsers/yandex.py
Было: grade из pro_level_max_display (почти всегда senior)
Стало: grade из min и max, диапазон "Middle–Senior" если разные

### BUG-013: T-Bank терял второй грейд из tags
Файл: parsers/tbank.py
Было: grade = tags[0]
Стало: все грейд-теги, диапазон если несколько

### BUG-014: en-dash (–) → дефис (-) в experience и grade
Файл: enrichment/normalizer.py, parsers/yandex.py, parsers/tbank.py
Было: в нормализованных строках и диапазонах грейда использовался en-dash (–)
Стало: используется дефис (-), при этом входящие ключи experience с en-dash сохранены для совместимости

### BUG-015: удалено автоматическое определение Lead+ из заголовков
Файл: enrichment/normalizer.py, main.py, parsers/avito.py
Было: Lead+ и часть грейдов определялись эвристиками по заголовку
Стало: автоматическое определение Lead+ из заголовка удалено, грейд остаётся только из API enrichment и grade_from_experience

### BUG-016: Т-Банк теряет грейд Head из tags
Файл: parsers/tbank.py
Было: grade_priority содержал только Junior, Middle, Senior, Lead — тег Head не распознавался
Стало: добавлены Head и CPO с маппингом в Lead+

### BUG-017: Avito — все вакансии без грейда
Файл: parsers/avito.py
Было: grade всегда null, т.к. API Avito не возвращает грейд
Стало: грейд определяется по номенклатуре должностей Avito (Ведущий → Senior, Руководитель → Lead+)

### BUG-018: VK грейды в нижнем регистре и через запятую
Файл: enrichment/normalizer.py, main.py
Было: grade из VK записывался как есть (middle, senior, middle, senior)
Стало: normalize_grade приводит к title case, заменяет запятую на дефис, Lead → Lead+

### BUG-019: work_format — 14 вариантов вместо трёх
Файл: enrichment/normalizer.py, main.py
Было: парсеры записывали work_format как есть из API (гибкий, На месте работодателя, офис и удаленно...)
Стало: normalize_work_format маппит в стандартные значения Офис/Удалёнка/Гибрид

### BUG-020: фильтрация не работала для множественных городов и форматов
Файл: delivery/filters.py
Было: точное сравнение строк, «Москва, Санкт-Петербург» не матчилось ни с чем
Стало: разбивка по запятой, матч по любому фрагменту, «Любой город» пропускается

## Обновления PR 5c

- Callback prefix `st:` используется для settings (по аналогии с `ob:` для онбординга).
- `get_step_message`, `toggle_selection`, `parse_selections_from_markup` параметризованы по `prefix` (по умолчанию `"ob"`).
- `filters.companies` хранит `name` компании, а не `parser_name`.
- После онбординга отправляется порция до 5 вакансий без `sleep`.
- В `main.py` лимит отправки — максимум 10 вакансий на пользователя за запуск.
- Команды `/settings` и `/stats` блокируются во время онбординга (`onboarding_step != null`).

### BUG-021: filters.companies хранил parser_name вместо name
Файл: bot/onboarding.py, bot/handlers.py
Было: в `filters.companies` сохранялся `parser_name`, из-за чего фильтрация по компаниям не совпадала с вакансиями.
Стало: сохраняется `name` компании через маппинг `parser_name -> name`.
