# Инструкции для AI-агентов (Codex и других)

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

## Спецификация API (подтверждённые поля)

### Wildberries
- Метод: GET
- URL: https://career.rwb.ru/crm-api/api/v1/pub/vacancies
- Обязательные заголовки: Referer: https://career.rwb.ru/vacancies
- Путь к вакансиям: data.items
- Пагинация: data.range (count, limit, offset)
- Поля: id (int), name (str), direction_title (str), direction_role_title (str), experience_type_title (str), city_title (str), employment_types (array, брать title)
- Ссылка: https://career.rwb.ru/vacancies/{id}
- Описание: только через HTML-страницу

### Yandex
- Метод: GET
- URL: https://yandex.ru/jobs/api/publications
- Путь к вакансиям: results
- Пагинация: cursor-based (поле next)
- Поля: id (int), publication_slug_url (str), title (str), short_summary (str), vacancy.cities (array, брать name), vacancy.work_modes (array, брать name), public_service.name (str)
- Фильтр грейда через параметр pro_levels: intern, junior, middle, senior
- Маппинг pro_levels → опыт: intern = без опыта, junior = 1-3 лет, middle = 3-5 лет, senior = 5+ лет
- Ссылка: https://yandex.ru/jobs/vacancies/{publication_slug_url}
- Описание: short_summary из API (краткое), полное — через HTML-страницу

### Ozon
- Метод: GET
- URL: https://job-api.ozon.ru/v2/vacancy
- Путь к вакансиям: items
- Пагинация: meta (page, perPage, totalItems, totalPages)
- Поля: hhId (int), internalUuid (str), title (str), department (str), employment (str), experience (str), workFormat (array[str]), city (str)
- Фильтр: vacancyType == "external_vacancy"
- Ссылка: https://career.ozon.ru/vacancy/{hhId}
- Описание: только через HTML-страницу

### T-Bank
- Метод: POST
- URL: https://www.tbank.ru/pfpjobs/papi/getVacancies
- Content-Type: application/json
- Путь к вакансиям: payload.vacancies
- Пагинация: payload.nextPagination.it (offset, isFinished)
- Поля: urlSlug (str), title (str), shortDescription (str, содержит HTML-теги — очищать), cities (array[str]), tags (array[str] — грейд: Middle, Senior, Head), source (str), specialty (str)
- Ссылка: https://www.tbank.ru/career/{source}/{specialty}/{urlSlug}/
- Описание: shortDescription из API (краткое, нужна очистка HTML), полное — через HTML-страницу

### VK
- Метод: GET
- URL: https://team.vk.company/career/api/v2/vacancies/
- Путь к вакансиям: results
- Пагинация: limit/offset (поле next содержит URL, count — общее количество)
- Поля: id (int), title (str), group.name (str — проект), town.name (str), work_format (str), remote (bool), tags (array, брать name)
- Грейд: НЕ в API, извлекается из мета-тега HTML-страницы (meta name="description", паттерн "уровня middle, senior")
- Ссылка: https://team.vk.company/vacancy/{id}/
- Описание: только через HTML-страницу

### Avito
- Метод: GET
- URL: https://career.avito.com/vacancies/?action=filter&direction=upravlenie-produktom
- Обязательные заголовки: X-Requested-With: XMLHttpRequest
- Формат: JSON с полем html, внутри — HTML-разметка (Bitrix CMS)
- CSS-селектор карточки: div.vacancies-section__item
- Поля из data-атрибутов: data-vacancy-id, data-vacancy-geo, data-vacancy-team, data-vacancy-remote (Да/Нет), data-vacancy-intern (Да/Нет), data-vacancy-section
- Название: a.vacancies-section__item-name (НЕ a.vacancies-section__item-link — та пустая)
- Формат работы: span.vacancies-section__item-format ("офис и удаленно", "можно удаленно")
- Ссылка: https://career.avito.com{href}
- Дополнительный фильтр: &managers=Y для руководящих позиций (Lead+)
- Грейд: из названия (Ведущий = Senior, Руководитель = Lead, Стажёр = Junior, без префикса = Middle)
- Описание: только через HTML-страницу вакансии

### Sber
- Метод: GET
- URL: https://rabota.sber.ru/public/app-candidate-public-api-gateway/api/v1/publications
- Путь к вакансиям: data.vacancies
- Пагинация: data.total, управление через skip/take
- Поля: requisitionId (str, UUID), title (str), company (str), city (str), publicationDate (str, ISO-8601), introduction (str), duties (str), requirements (str), conditions (str)
- Текстовые блоки содержат Markdown-разметку
- Фильтрация по заголовку: product/продакт/продукт/cpo
- Ссылка: https://rabota.sber.ru/search/{requisitionId}
- Описание: ЕСТЬ В API (introduction + duties + requirements + conditions)

### Alfa-Bank
- Метод: GET
- URL: https://job.alfabank.ru/api/vacancies
- Путь к вакансиям: items
- Пагинация: total, управление через skip/take
- Поля: id (str), code (str), slug (str — город из первого сегмента), name (str), description (str, сырой HTML), descriptionText (str, очищенный текст — использовать его), createdAt (str, ISO-8601), expirationDate (str), isHot (bool), isReferral (bool)
- Ссылка: https://job.alfabank.ru/vacancies/{id}
- Описание: ЕСТЬ В API (descriptionText)

## Какие данные есть в API, но мы пока не используем

- Yandex: short_summary, public_service.name, pro_levels (грейд + опыт через маппинг)
- Ozon: department
- T-Bank: shortDescription (требует очистки HTML)
- VK: group.name (проект)
- Avito: data-vacancy-team (команда), span.vacancies-section__item-format (детальный формат), data-vacancy-intern
- Sber: introduction, duties, requirements, conditions, publicationDate
- Alfa-Bank: descriptionText, createdAt

## Для каких компаний нужен парсинг HTML (описание вакансии)

- Wildberries — описание только на HTML-странице
- Ozon — описание только на HTML-странице
- VK — описание и грейд только на HTML-странице
- Avito — описание только на HTML-странице вакансии

Не нужен парсинг HTML для описания:
- Sber — описание есть в API
- Alfa-Bank — описание есть в API
- T-Bank — краткое описание есть в API
- Yandex — краткое описание есть в API

## Исправленные баги (не повторять)

### BUG-001: importlib вместо PARSER_REGISTRY
Файл: main.py
Проблема: динамический импорт через importlib находил BaseParser и падал с "Can't instantiate abstract class"
Решение: from parsers import PARSER_REGISTRY, lookup через PARSER_REGISTRY.get(parser_name)

### BUG-002: Markdown вместо HTML в Telegram
Файл: delivery/telegram.py
Проблема: parse_mode="Markdown" давал обратные слэши в тексте
Решение: parse_mode="HTML", функция _escape_html, теги <b> и <a href>

## Известные баги (нужно исправить)

### BUG-003: Avito — пустые заголовки вакансий
Файл: parsers/avito.py
Проблема: card.find("a") находит первую ссылку (a.vacancies-section__item-link) — у неё пустой текст
Решение: искать a.vacancies-section__item-name — там лежит название

### BUG-004: Yandex — нет опыта и грейда
Файл: parsers/yandex.py
Проблема: API отдаёт pro_levels, но парсер его не использует
Решение: маппинг pro_levels → грейд и опыт (intern=Junior/без опыта, junior=Junior/1-3, middle=Middle/3-5, senior=Senior/5+)

### BUG-005: лишние пробелы в названиях вакансий
Файлы: все парсеры
Проблема: некоторые названия приходят с пробелами в начале/конце
Решение: .strip() на title перед сохранением
