# Контекст проекта ProductRadar

## Продуктовые решения

- `grade` берётся из API, через маппинг `experience -> grade`, либо из заголовка только для исключений Avito и T-Bank (`Lead+`). Универсальный `grade_guesser` удалён.
- Enrichment реализуется методом `enrich()` внутри конкретного парсера, а не отдельным слоем файлов.
- Онбординг строится как сценарий `/start` → welcome → выбор `grade` → `city` → `work_format` → `company` → `confirm` → disclaimer (`strict_mode`) → выдача вакансий.
- Для returning user команда `/start` показывает хаб с тремя вариантами: получить вакансии, открыть настройки, начать заново. `/start` снимает паузу рассылки.
- В фильтрах пустой список означает «всё». `strict_mode=true` отсекает вакансии с пустыми полями, `strict_mode=false` пропускает их.
- В онбординге используются два города — Москва и Санкт-Петербург — плюс вариант «Любой город». Это осознанное решение после анализа данных.
- Текст отписки должен быть честным: при `/stop` фильтры сохраняются.
- `published_at` приходит из источника только у части компаний: Сбер (`publicationDate`), Альфа-Банк (`createdAt`), Ozon (`publishedAt` через enrichment API), Yandex (`published_at` через enrichment API). Для остальных используется fallback на `created_at` в базе.
- `salary` извлекается из API Альфа-Банка (`minSalary`/`maxSalary`) и Сбера (`salary_min`/`salary_max`), если эти поля заполнены. У остальных компаний зарплата в API сейчас не публикуется.

## Результаты code review

### Принято к исполнению (PR cleanup)

- Удалить мёртвый код: `deliver_vacancies()` и `send_telegram_message()` в `delivery/telegram.py`, `mark_vacancies_notified()` и `get_unnotified_vacancies()` в `database/supabase_client.py`, `FINAL_TEXT` в `bot/handlers.py`.
- Убрать дублирование: переписать `edit_message()` в `bot/telegram_api.py` через `_post()`, убрать `_normalize_general_city()` из `main.py` и использовать `normalize_city()` из `parsers/utils.py`, унифицировать логику доставки в webhook и cron.
- Исправить баг в `bot/handlers.py`: `_send_vacancies_chunk()` должен проверять результат `send_message()` до добавления вакансии в `sent_ids`.
- Пересмотреть стратегию ошибок в `api/webhook.py`: сейчас при исключениях нужен выбор между `500` для transient-ошибок и `200` для бизнес-ошибок.
- Заменить `insert` на `upsert` с `on_conflict="id"` и убрать загрузку всех ID вакансий в память.
- Зафиксировать контракт `enrich()`: метод мутирует `dict` in-place, а `main.py` должен опираться на это поведение явно и безопасно.

### Принято к исполнению (масштабирование)

- Добавить пагинацию для `get_existing_vacancy_ids()` и `get_active_users()`: у Supabase лимит 1000 строк на запрос.
- Перенести `get_undelivered_vacancies()` в SQL (`LEFT JOIN`) вместо клиентского `NOT IN`.
- Добавить пагинацию в парсеры: сейчас они читают только одну страницу.

### Отложено до AI-фазы

- Разбить монолиты `main.py`, `bot/handlers.py` и `SupabaseService` на более мелкие модули.
- Добавить provenance-поля для отслеживания источника данных: `processing_stage`, `ai_model`, `field_sources`.
- Переработать `/stats`: разнести метрики «всего на рынке», «под фильтры», «просмотрено» и «новых».
- Поддержать два формата выдачи: карточки и дайджест.
- Добавить кнопки на карточках: сохранить, скрыть, похожие.

## Experience-to-grade маппинг

| Нормализованный опыт | Грейд |
| --- | --- |
| без опыта | Junior |
| до 1 года | Junior |
| 1-3 года | Middle |
| 3-5 лет | Middle+ |
| 5+ лет | Senior |
| lead/head/руководитель/директор/cpo в заголовке | Lead+ |
| не указан | null |

Дополнительно используется regex-fallback: если в строке опыта найдено число `N`, то `N < 1 → Junior`, `1 ≤ N < 3 → Middle`, `3 ≤ N < 5 → Middle+`, `N ≥ 5 → Senior`.

## API исследования

| Компания | published_at | Источник |
| --- | --- | --- |
| Wildberries | нет | fallback на `created_at` |
| Yandex | да | `published_at` из enrichment API |
| Ozon | да | `publishedAt` из enrichment API |
| T-Bank | нет | fallback на `created_at` |
| VK | нет | fallback на `created_at` |
| Avito | нет | fallback на `created_at` |
| Sber | да | `publicationDate` |
| Alfa-Bank | да | `createdAt` |

Остальные результаты исследования внешних API хранятся в `docs/api_spec.md` и здесь не дублируются.
