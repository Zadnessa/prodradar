# Контекст проекта ProductRadar

Файл для восстановления контекста в длинных диалогах. Только добавление, не редактирование.

---

## 2026-03-14: API отдельной вакансии — результаты исследования

Все 6 endpoint-ов работают из Google Colab (и GitHub Actions). Ozon НЕ блокирует облачные IP (ранее предполагали что блокирует — опровергнуто).

| Компания | Endpoint | Grade | Description |
|---|---|---|---|
| Yandex | /api/publications/{id} | vacancy.pro_level_max_display → "publications.pro_level.senior" | duties, key_qualifications |
| Wildberries | /crm-api/api/v1/pub/vacancies/{id} (+ Referer) | data.skill_level_id (был null в тесте) | data.description, duties_arr, requirements_arr |
| Ozon | /vacancy/{hhId} | нет | descr (HTML) |
| T-Bank | hrsites-api-vacancies.tbank.ru/.../getVacancy?urlSlug={slug} | experiences[0].name → "Senior" | tasks, requirements (HTML) |
| Sber | .../publications?requisitionId={id} | нет | уже есть в списке |
| Alfa-Bank | /api/vacancies/{id} | нет | уже есть в списке |
| VK | нет API отдельной вакансии | — | — |
| Avito | нет API отдельной вакансии | — | — |

---

## 2026-03-14: Маппинг experience → grade (normalizer)

| Нормализованный опыт | Grade |
|---|---|
| без опыта | Junior |
| до 1 года | Junior |
| 1–3 года | Middle |
| 3–5 лет | Middle+ |
| 5+ лет | Senior |
| lead/head/руководитель/директор/cpo в заголовке | Lead+ |
| не указан | null |

Regex-fallback: извлечь число N из строки, N<1→Junior, 1≤N<3→Middle, 3≤N<5→Middle+, N≥5→Senior.

---

## 2026-03-14: PR-план

- PR 1 — Normalizer + Yandex fix + Telegram output ✅ смержен
- PR 1.1 — Bugfix normalizer edge cases ✅ смержен
- PR 2 — Enrichment API (Yandex, WB, Ozon, T-Bank) ⏳ в работе
- PR 3 — HTML-enrichment (VK, Avito) — только description
- PR 4 — Стоп-слова (фильтрация нерелевантных вакансий)
- PR 5 — Онбординг + фильтры
- PR 6+ — Дайджест, UX, AI-функции

---

## 2026-03-14: Ключевые решения

- grade_guesser удалён, заменён на normalizer — НЕ угадываем grade из заголовка (кроме Lead+)
- grade берётся: 1) из API (прямое поле), 2) Lead+ из заголовка, 3) маппинг experience → grade
- Enrichment = метод enrich() в каждом парсере, не отдельный слой файлов
- Одна компания = один файл парсера (parse + enrich)
- VK и Avito — только HTML, API отдельной вакансии нет (проверено агентом с браузером)
- SHOW_DESCRIPTION = False (описания пока не выводятся в Telegram)
- TEST_MODE = True, TEST_LIMIT = 3 (24 вакансии в базе)

---

## 2026-03-14: Известные особенности данных

- Yandex: pro_levels в API списка — фильтр кандидата, НЕ грейд вакансии. Одна вакансия возвращается на всех уровнях.
- Yandex: experience и grade отсутствуют в API списка. Grade только через enrichment (pro_level_max_display).

---

## 2026-03-14: Yandex pro_level — min, не max

vacancy.pro_level_min_display = минимальный уровень кандидата = грейд позиции.
vacancy.pro_level_max_display = максимальный допустимый уровень = бесполезен (почти всегда senior).
Примеры:
- "Младший менеджер": min=junior, max=senior → grade = Junior
- "Менеджер продукта в KIT": min=middle, max=senior → grade = Middle
Enricher должен брать min, не max.
- Yandex вакансия "Плюс AdTech": город = "Не указан" — это реальное отсутствие данных, не баг.
- WB: skill_level_id был null в тестовой вакансии — может быть заполнен у других.
- Avito: дефолт grade "Middle" убран, теперь null если нет совпадения (Lead/Senior/Junior из заголовка).
- Sber/Alfa experience маппинги через config.py (UUID → строка).

---

## 2026-03-14: PR 5a — per-user доставка, фильтры, Telegram API helper

- PR 5a смержен: per-user доставка, фильтры, `telegram_api` helper.
- Модель доставки: `user_vacancy_delivery` вместо `notified_at`.
- Структура filters: `{"grades": [], "cities": [], "work_formats": [], "companies": []}`.
- Логика фильтрации: пустой список = всё, grade-диапазоны по левой части, `Middle+` = `Middle`, `null`/`Не указан` пропускается.

## PR 5b: Онбординг UI

- Создан `bot/onboarding.py` — state machine онбординга.
- CJM: /start → welcome → [Быстрый старт | Настроить] → grade → city → work_format → company → confirm.
- Toggle без БД: промежуточный выбор живёт в reply_markup, запись в Supabase только при ob:next, ob:done, ob:quick.
- Компании: по умолчанию все включены (🟢). Пустой companies=[] значит "все". В filters хранится список включённых parser_name.
- callback_data формат: ob:quick, ob:setup, ob:g:Junior, ob:c:СПб, ob:wf:remote, ob:co:yandex, ob:next, ob:done, ob:restart.
- Лоадеры через edit_message на шагах с запросами к БД.
- Fallback при невосстановимом состоянии: "Сессия настройки устарела..."
- Повторный /start сбрасывает filters и перезапускает онбординг.
- Добавлен метод get_user(chat_id) в SupabaseService.
- webhook.py: callback_query и message — взаимоисключающие пути.
- UX-доработка: тексты переписаны от лица бота, добавлен грейд Lead+, кнопка «Не важно →» (ob:skip) на каждом шаге, «Другой» переименован в «Другой / зарубежные», добавлены пояснения на каждом шаге.
- ob:skip — игнорирует выбор на текущем шаге, записывает пустой список в filters для шага, переходит к следующему шагу.

## Hotfix: русские названия компаний + грейды

- Парсеры sber, alfa, tbank, yandex: company переведён на русский (Сбер, Альфа-Банк, Т-Банк, Яндекс). Совпадает с таблицей companies.
- parsers/tbank.py: tags "Head" и "CPO" маппятся в Lead+.
- parsers/avito.py: грейд определяется по префиксу заголовка (специфика Avito, не универсальная эвристика). «Ведущий» → Senior, «Руководитель»/CPO/Head of → Lead+.
- Это не противоречит BUG-009 (запрет на универсальное угадывание грейда из заголовка). Маппинг применяется только к Avito, где API не содержит данных о грейде.

## Запланировано: предупреждение о строгих фильтрах (не реализовано)

На шаге confirm онбординга (или отдельным шагом перед ним) показать предупреждение, если строгие фильтры отсекают значительную часть вакансий из-за пустых полей (grade=null, city=null и т.д.). Пример: «По твоим фильтрам N вакансий. Ещё M вакансий не имеют указанного грейда — показывать их тоже?» с кнопками Да/Нет. Зависит от PR 5c (нужна функция подсчёта вакансий по фильтрам). Реализация — отдельный PR после 5c.


## Hotfix: нормализация work_format, grade, фильтрация городов

- normalize_work_format: маппинг произвольных форматов в Офис/Удалёнка/Гибрид. Множественные значения через запятую разбиваются и нормализуются отдельно.
- normalize_grade: title case, запятая → дефис, Lead/Head/CPO → Lead+.
- filters.py: фильтрация city, work_format, grade устойчива к множественным значениям через запятую. «Любой город» пропускается фильтром.
- Нормализация вызывается в main.py после enrichment, перед записью в БД.

## 2026-03-15: PR 5c — настройки, статистика, порционная выдача

- Порционная выдача: после завершения онбординга в webhook отправляются первые 5 подходящих вакансий, в cron (`main.py`) — максимум 10 вакансий на пользователя за запуск. Кнопка «Ещё» перенесена в PR 5d.
- Добавлен `/settings`: inline-меню с callback prefix `st:`, переиспользует onboarding UI через параметризованный `prefix` в `get_step_message`, `toggle_selection`, `parse_selections_from_markup`.
- В `/settings` доступны пауза/возобновление и отписка. Текстовых команд `/pause` и `/resume` нет.
- Добавлен `/stats`: текстовая статистика за `VACANCY_TTL_DAYS` + количество вакансий, подходящих под фильтры пользователя.
- Исправлен баг фильтра компаний: `filters.companies` хранит `name` компании (русское имя), а не `parser_name`.
- BotFather-меню: команды `/settings` и `/stats`.
