# Vacancy Radar

## Описание проекта
Vacancy Radar — это Telegram-бот для людей, которые ищут вакансии Product Manager в крупных российских IT-компаниях. Проект автоматически собирает вакансии из API компаний, сохраняет их в Supabase (PostgreSQL) для дедубликации и отправляет новые вакансии подписчикам в Telegram два раза в день.

## Архитектура
- **GitHub Actions** запускает `main.py` по расписанию (10:00 и 19:00 МСК).
- **Парсеры** собирают вакансии из API 8 компаний.
- **Supabase** хранит вакансии, пользователей, компании и маппинги городов.
- **Telegram Bot API** используется для рассылки и работы с командами.
- **Vercel Serverless Function** обрабатывает webhook `/api/webhook` для команд `/start` и `/stop`.

```text
GitHub Actions (cron)
  -> main.py
  -> parsers/*
  -> Supabase (vacancies/users/companies/city_mappings)
  -> Telegram рассылка пользователям
  -> отчёт в ADMIN_CHAT_ID

Telegram User
  -> Telegram webhook
  -> Vercel /api/webhook.py
  -> bot/handlers.py
  -> Supabase users
```

## Список компаний-источников
| Код | Компания | Категория |
|---|---|---|
| wb | Wildberries | E-commerce |
| ya | Yandex | IT |
| ozon | Ozon | E-commerce |
| tbank | T-Bank | Финтех |
| vk | VK | IT |
| avito | Avito | Классифайды |
| sber | Sber | Финтех |
| alfa | Alfa-Bank | Финтех |

## Структура проекта
```text
vacancy-radar/
├── config.py
├── main.py
├── parsers/
│   ├── __init__.py
│   ├── base.py
│   ├── utils.py
│   ├── wildberries.py
│   ├── yandex.py
│   ├── ozon.py
│   ├── tbank.py
│   ├── vk.py
│   ├── avito.py
│   ├── sber.py
│   └── alfa.py
├── enrichment/
│   ├── __init__.py
│   ├── grade_guesser.py
│   └── ai_summary.py
├── database/
│   ├── __init__.py
│   └── supabase_client.py
├── delivery/
│   ├── __init__.py
│   ├── telegram.py
│   └── filters.py
├── bot/
│   ├── __init__.py
│   └── handlers.py
├── api/
│   └── webhook.py
├── .github/workflows/
│   └── collect.yml
├── vercel.json
├── requirements.txt
└── README.md
```

## Переменные окружения
Хранятся в **GitHub Secrets** (для cron-скрипта) и в **Vercel Environment Variables** (для webhook).

| Переменная | Где используется | Описание |
|---|---|---|
| `SUPABASE_URL` | GitHub Actions, Vercel | URL Supabase проекта |
| `SUPABASE_KEY` | GitHub Actions, Vercel | Secret key Supabase (`sb_secret_...`) |
| `TELEGRAM_BOT_TOKEN` | GitHub Actions, Vercel | Токен основного Telegram-бота |
| `ADMIN_CHAT_ID` | GitHub Actions | chat_id администратора для отчётов |

## Инструкция по деплою
### 1) Подготовка Supabase
Таблицы уже существуют. Нужно применить только миграции для недостающих полей:

```sql
ALTER TABLE public.vacancies ADD COLUMN IF NOT EXISTS notified_at TIMESTAMPTZ;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS bot_id TEXT DEFAULT 'main';
```

### 2) GitHub Actions
1. Добавьте секреты репозитория: `SUPABASE_URL`, `SUPABASE_KEY`, `TELEGRAM_BOT_TOKEN`, `ADMIN_CHAT_ID`.
2. Убедитесь, что файл `.github/workflows/collect.yml` присутствует.
3. Запустите workflow вручную через **Actions -> Collect Vacancies -> Run workflow**.

### 3) Vercel
1. Подключите репозиторий к Vercel.
2. Убедитесь, что используется `vercel.json` с маршрутом `/api/webhook`.
3. Добавьте env-переменные: `SUPABASE_URL`, `SUPABASE_KEY`, `TELEGRAM_BOT_TOKEN`.
4. Настройте Telegram webhook на URL вида: `https://<your-project>.vercel.app/api/webhook`.

## Как добавить новую компанию
1. Добавьте новую запись в таблицу `companies` с `is_enabled=true` и `parser_name`.
2. Создайте файл `parsers/<parser_name>.py` и класс `<Name>Parser`, унаследованный от `BaseParser`.
3. Реализуйте `async parse(session, existing_ids, city_mappings) -> list[dict]`.
4. Добавьте парсер в `parsers/__init__.py` (реестр `PARSER_REGISTRY`).
5. Проверьте, что парсер возвращает вакансии в едином формате и заполняет `source_json` полным объектом API.
6. При необходимости добавьте маппинги в таблицу `city_mappings`, а не в код.

## Примечания по логике
- Эмодзи компании всегда берутся из таблицы `companies`.
- Город всегда нормализуется через `city_mappings`.
- Рассылка идёт всем активным пользователям из `users` (`is_active=true`).
- Дедубликация рассылки построена на `notified_at`.
- Ошибки отдельных парсеров не останавливают общий сбор.
