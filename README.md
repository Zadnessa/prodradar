# ProductRadar

Telegram-бот, который мониторит вакансии Product Manager в крупнейших российских IT-компаниях и присылает новые позиции подписчикам.

## Что делает

- Собирает вакансии из скрытых API 8 компаний дважды в день (10:00 и 19:00 МСК)
- Дедублицирует и доставляет per-user через `user_vacancy_delivery`
- Применяет пользовательские фильтры из `users.filters`
- Отправляет подписчикам в Telegram с указанием компании, позиции, города, опыта, грейда и формата работы
- Ссылка ведёт на оригинальную страницу вакансии

## Архитектура доставки

- Модель доставки: per-user, статус доставки хранится в `user_vacancy_delivery` (вместо глобального `notified_at`)
- Пользовательские фильтры: JSON в `users.filters` (`grades`, `cities`, `work_formats`, `companies`)
- Telegram Bot API вызывается только через централизованный helper `bot/telegram_api.py`

## Компании-источники

| Компания | Категория |
|---|---|
| Wildberries | E-commerce |
| Yandex | IT |
| Ozon | E-commerce |
| T-Bank | Финтех |
| VK | IT |
| Avito | Классифайды |
| Sber | Финтех |
| Alfa-Bank | Финтех |

## Команды бота

- `/start` — подписка на рассылку
- `/stop` — отписка от рассылки
- `/settings`, `/stats`, `/pause`, `/resume` — появятся в следующем PR

## Структура проекта

```text
prodradar/
├── config.py              — конфигурация и флаги
├── main.py                — точка входа для сбора вакансий и рассылки
├── parsers/               — по одному файлу на компанию
│   ├── __init__.py        — реестр парсеров
│   ├── base.py            — базовый интерфейс
│   ├── utils.py           — нормализация городов
│   └── ...                — wildberries.py, yandex.py и т.д.
├── enrichment/            — обогащение данных (грейд, AI-саммари)
├── database/
│   └── supabase_client.py — доступ к Supabase и delivery-методы
├── delivery/
│   ├── telegram.py        — форматирование сообщений и legacy-совместимость
│   └── filters.py         — фильтрация вакансий по user.filters
├── bot/
│   ├── handlers.py        — обработка команд
│   └── telegram_api.py    — единый Telegram API helper
├── api/
│   └── webhook.py         — serverless webhook (message + callback_query)
├── .github/workflows/     — автозапуск по расписанию
├── docs/                  — документация и спецификации API
├── vercel.json
├── requirements.txt
└── README.md
```

## Планы развития

- Онбординг с выбором грейда, города и компаний при подписке
- Дайджест: один message со списком вместо потока отдельных сообщений
- AI-саммари вакансий
- Аналитика рынка PM-вакансий

## Статус

MVP. Сбор из 8 источников работает.
