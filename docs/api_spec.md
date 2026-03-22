# Спецификация API карьерных сайтов

## Wildberries
- Метод: GET
- URL: https://career.rwb.ru/crm-api/api/v1/pub/vacancies
- Обязательные заголовки: Referer: https://career.rwb.ru/vacancies
- Путь к вакансиям: data.items
- Пагинация: data.range (count, limit, offset)
- Поля: id (int), name (str), direction_title (str), direction_role_title (str), experience_type_title (str), city_title (str), employment_types (array, брать title)
- Ссылка: https://career.rwb.ru/vacancies/{id}
- Описание: полное через API detail-эндпоинт (description + duties_arr + requirements_arr + conditions_arr)
- Справочные эндпоинты:
  - GET /crm-api/api/v1/pub/directions (27 направлений)
  - GET /crm-api/api/v1/pub/direction-roles (288 ролей, фильтр direction_ids[])

### API отдельной вакансии
- Метод: GET
- URL: https://career.rwb.ru/crm-api/api/v1/pub/vacancies/{id}
- Обязательные заголовки: Referer: https://career.rwb.ru/vacancies
- Поля для enrichment:
  - grade: data.skill_level_id (фактически почти всегда null, если null — не заполнять)
  - description: data.description + data.duties_arr + data.requirements_arr + data.conditions_arr (склеить, обрезать до 500 символов)

## Yandex
- Метод: GET
- URL: https://yandex.ru/jobs/api/publications
- Путь к вакансиям: results
- Пагинация: cursor-based (поле next)
- Поля списка: id (int), publication_slug_url (str), title (str), short_summary (str), vacancy.id (int, внутренний ID, может отличаться от id публикации), vacancy.skills (array), vacancy.cities (array, брать name), vacancy.work_modes (array, брать name), public_service.name (str)
- Параметры фильтрации: public_professions, cities, services, text, page_size, is_fast_track
- Ссылка: https://yandex.ru/jobs/vacancies/{publication_slug_url}
- Описание: полное через API detail-эндпоинт (description + duties + key_qualifications + additional_requirements + conditions)

### API отдельной вакансии
- Метод: GET
- URL: https://yandex.ru/jobs/api/publications/{id}
- Поля для enrichment:
  - published_at: published_at (YYYY-MM-DD)
  - grade: vacancy.pro_level_min_display / vacancy.pro_level_max_display (строить Junior/Middle/Senior или диапазон)
  - description: short_summary + duties + key_qualifications + additional_requirements + conditions (склеить, обрезать до 500 символов)
  - дополнительные поля: vacancy.employment_types, vacancy.profession, vacancy.public_professions, our_team, tech_stack, pro_level_min_display, additional_requirements, conditions

## Ozon
- Метод: GET
- URL: https://job-api.ozon.ru/v2/vacancy
- Путь к вакансиям: items
- Пагинация: meta (page, perPage, totalItems, totalPages), максимальный perPage = 50 — сервер обрезает большие значения
- Поля: hhId (int), internalUuid (str), title (str), department (str), employment (str), experience (str), workFormat (array[str]), city (str), professionalRoles (array[object], ID совпадают с hh.ru)
- Фильтр: vacancyType == "external_vacancy"
- Ссылка: https://career.ozon.ru/vacancy/{hhId}
- Описание: полное через API detail-эндпоинт (поле descr)

### API отдельной вакансии
- Метод: GET
- URL: https://job-api.ozon.ru/vacancy/{hhId}
- Поля для enrichment:
  - description: descr (HTML, очистить и обрезать до 500 символов)
  - experience: exp (только если текущее значение пустое/не указано)
  - work_format: workFormat (только если текущее значение пустое)
  - url slug: slug (для формирования канонического URL https://career.ozon.ru/vacancy/{slug}/)
  - даты: publishedAt / createdAt

## T-Bank
- Метод: POST
- URL: https://www.tbank.ru/pfpjobs/papi/getVacancies
- Content-Type: application/json
- Фильтр: {"filters": {"tcareer_it_profession": ["product-management"]}}
- Путь к вакансиям: payload.vacancies
- Пагинация: payload.nextPagination.it (offset, isFinished)
- Поля: urlSlug (str), title (str), shortDescription (str — содержит HTML-теги, очищать), regionId (str, FIAS UUID — источник города), seoSlug (str — компонент URL), category (str), backend (str), tags (array[str] — грейд: Middle, Senior, Head), source (str), specialty (str), cities (array[str], фактически всегда пустой массив и не используется как источник города)
- Ссылка: https://www.tbank.ru/career/it/vacancy/{city_slug}/{seoSlug}/{urlSlug}/
- Описание: shortDescription из API (краткое, нужна очистка HTML)
- Справочные эндпоинты:
  - POST getFiltersV3 (группы tcareer_it_profession, tcareer_it_specialization, tcareer_it_experience, tcareer_it_work_format, tcareer_adm_vacancies_cities)
  - POST getFiltersActivity

### API отдельной вакансии
- Метод: GET
- URL: https://hrsites-api-vacancies.tbank.ru/vacancies/public/api/platform/v2/getVacancy?urlSlug={slug}
- Статус: НЕ РАБОТАЕТ для source=publisher, возвращает пустые поля. Проверено 2026-03-22.

## VK
- Метод: GET
- URL: https://team.vk.company/career/api/v2/vacancies/
- Путь к вакансиям: results
- Пагинация: limit/offset (поле next, count), максимальный limit = 50 — сервер обрезает большие значения
- Поля: id (int), title (str), group.name (str — проект), specialty (object: id, name), prof_area (object: id, name), town.name (str), work_format (str), remote (bool), tags (array, брать name)
- Грейд: НЕ в API, извлекается из мета-тега HTML-страницы (meta name="description", паттерн "уровня middle, senior")
- Ссылка: https://team.vk.company/vacancy/{id}/
- Описание: только через HTML-страницу

## Avito
- Метод: GET
- URL: https://career.avito.com/vacancies/?action=filter&direction=upravlenie-produktom
- Обязательные заголовки: X-Requested-With: XMLHttpRequest
- Формат: JSON с полем html, внутри — HTML-разметка (Bitrix CMS)
- CSS-селектор карточки: div.vacancies-section__item
- Поля из data-атрибутов: data-vacancy-id, data-vacancy-geo, data-vacancy-team, data-vacancy-remote (Да/Нет), data-vacancy-intern (Да/Нет), data-vacancy-section (название направления кириллицей)
- Название: селектор a.vacancies-section__item-name (НЕ a.vacancies-section__item-link — та пустая)
- Формат работы: селектор span.vacancies-section__item-format ("офис и удаленно", "можно удаленно", "удаленно", "офис")
- Ссылка: https://career.avito.com{href}
- Дополнительный фильтр: &managers=Y для руководящих позиций (Lead+)
- Грейд из названия: Ведущий = Senior, Руководитель = Lead, Стажёр = Junior, без префикса = Middle
- Описание: только через HTML-страницу вакансии

## Sber
- Метод: GET
- URL: https://rabota.sber.ru/public/app-candidate-public-api-gateway/api/v1/publications
- Путь к вакансиям: data.vacancies
- Пагинация: data.total, управление через skip/take
- Поля: requisitionId (str, UUID), internalId (number), publicationId (UUID), title (str), company (str), companyShortName (str), city (str), publicationDate (str, ISO-8601), salary_min, salary_max, workScheduleId, experienceId (UUID), specializationId (UUID), introduction (str), duties (str), requirements (str), conditions (str)
- Текстовые блоки содержат Markdown-разметку
- Фильтрация по заголовку: product/продакт/продукт/cpo
- Ссылка: https://rabota.sber.ru/search/{internalId} (работает, редирект на slug-версию)
- Описание: ЕСТЬ В API (introduction + duties + requirements + conditions)
- Справочные эндпоинты:
  - GET /api/v1/profAreas (44 записи)
  - GET /api/v1/experiences (4 уровня)

## Alfa-Bank
- Метод: GET
- URL: https://job.alfabank.ru/api/vacancies
- Путь к вакансиям: items
- Пагинация: total, управление через skip/take
- Поля: id (str), code (str), slug (str — содержит ведущий слеш и город в первом сегменте), name (str), description (str — сырой HTML), descriptionText (str — очищенный текст, использовать его), createdAt (str, ISO-8601), expirationDate (str), isHot (bool), isReferral (bool), cityId, archetypeId (формат работы), experienceId, duties, requirements, conditions, minSalary, maxSalary, groupName, updatedAt
- Ссылка: https://job.alfabank.ru/vacancies{slug}
- Описание: ЕСТЬ В API (descriptionText)
- Справочные эндпоинты:
  - GET /api/optionLists (14 словарей)
  - GET /api/vacancies/options (фильтры с count)

## Сводка: где есть описание

| Компания | Описание в API | Нужен HTML-парсинг |
|---|---|---|
| Wildberries | Полное (структурированное) | Нет |
| Yandex | Полное | Нет |
| Ozon | Полное | Нет |
| T-Bank | Краткое (shortDescription) | Да, для полного |
| VK | Нет | Да (+ грейд) |
| Avito | Нет | Да |
| Sber | Полное | Нет |
| Alfa-Bank | Полное | Нет |
