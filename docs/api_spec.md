# Спецификация API карьерных сайтов

## Wildberries
- Метод: GET
- URL: https://career.rwb.ru/crm-api/api/v1/pub/vacancies
- Обязательные заголовки: Referer: https://career.rwb.ru/vacancies
- Путь к вакансиям: data.items
- Пагинация: data.range (count, limit, offset)
- Поля: id (int), name (str), direction_title (str), direction_role_title (str), experience_type_title (str), city_title (str), employment_types (array, брать title)
- Ссылка: https://career.rwb.ru/vacancies/{id}
- Описание: только через HTML-страницу

### API отдельной вакансии
- Метод: GET
- URL: https://career.rwb.ru/crm-api/api/v1/pub/vacancies/{id}
- Обязательные заголовки: Referer: https://career.rwb.ru/vacancies
- Поля для enrichment:
  - grade: data.skill_level_id (если null — не заполнять)
  - description: data.description + data.duties_arr + data.requirements_arr (склеить, обрезать до 500 символов)

## Yandex
- Метод: GET
- URL: https://yandex.ru/jobs/api/publications
- Путь к вакансиям: results
- Пагинация: cursor-based (поле next)
- Поля: id (int), publication_slug_url (str), title (str), short_summary (str), vacancy.cities (array, брать name), vacancy.work_modes (array, брать name), public_service.name (str)
- Фильтр грейда через параметр pro_levels: intern, junior, middle, senior
- Маппинг pro_levels в опыт: intern = без опыта, junior = 1-3 лет, middle = 3-5 лет, senior = 5+ лет
- Ссылка: https://yandex.ru/jobs/vacancies/{publication_slug_url}
- Описание: short_summary из API (краткое), полное — через HTML

### API отдельной вакансии
- Метод: GET
- URL: https://yandex.ru/jobs/api/publications/{id}
- Поля для enrichment:
  - grade: vacancy.pro_level_max_display (берём последний сегмент: intern/junior → Junior, middle → Middle, senior → Senior)
  - description: short_summary + duties + key_qualifications (склеить, обрезать до 500 символов)

## Ozon
- Метод: GET
- URL: https://job-api.ozon.ru/v2/vacancy
- Путь к вакансиям: items
- Пагинация: meta (page, perPage, totalItems, totalPages)
- Поля: hhId (int), internalUuid (str), title (str), department (str), employment (str), experience (str), workFormat (array[str]), city (str)
- Фильтр: vacancyType == "external_vacancy"
- Ссылка: https://career.ozon.ru/vacancy/{hhId}
- Описание: только через HTML-страницу

### API отдельной вакансии
- Метод: GET
- URL: https://job-api.ozon.ru/vacancy/{hhId}
- Поля для enrichment:
  - description: descr (HTML, очистить и обрезать до 500 символов)
  - experience: exp (только если текущее значение пустое/не указано)
  - work_format: workFormat (только если текущее значение пустое)

## T-Bank
- Метод: POST
- URL: https://www.tbank.ru/pfpjobs/papi/getVacancies
- Content-Type: application/json
- Путь к вакансиям: payload.vacancies
- Пагинация: payload.nextPagination.it (offset, isFinished)
- Поля: urlSlug (str), title (str), shortDescription (str — содержит HTML-теги, очищать), cities (array[str]), tags (array[str] — грейд: Middle, Senior, Head), source (str), specialty (str)
- Ссылка: https://www.tbank.ru/career/{source}/{specialty}/{urlSlug}/
- Описание: shortDescription из API (краткое, нужна очистка HTML)

### API отдельной вакансии
- Метод: GET
- URL: https://hrsites-api-vacancies.tbank.ru/vacancies/public/api/platform/v2/getVacancy?urlSlug={slug}
- Поля для enrichment:
  - grade: experiences[0].name
  - description: tasks + requirements (HTML, очистить и обрезать до 500 символов)

## VK
- Метод: GET
- URL: https://team.vk.company/career/api/v2/vacancies/
- Путь к вакансиям: results
- Пагинация: limit/offset (поле next, count)
- Поля: id (int), title (str), group.name (str — проект), town.name (str), work_format (str), remote (bool), tags (array, брать name)
- Грейд: НЕ в API, извлекается из мета-тега HTML-страницы (meta name="description", паттерн "уровня middle, senior")
- Ссылка: https://team.vk.company/vacancy/{id}/
- Описание: только через HTML-страницу

## Avito
- Метод: GET
- URL: https://career.avito.com/vacancies/?action=filter&direction=upravlenie-produktom
- Обязательные заголовки: X-Requested-With: XMLHttpRequest
- Формат: JSON с полем html, внутри — HTML-разметка (Bitrix CMS)
- CSS-селектор карточки: div.vacancies-section__item
- Поля из data-атрибутов: data-vacancy-id, data-vacancy-geo, data-vacancy-team, data-vacancy-remote (Да/Нет), data-vacancy-intern (Да/Нет), data-vacancy-section
- Название: селектор a.vacancies-section__item-name (НЕ a.vacancies-section__item-link — та пустая)
- Формат работы: селектор span.vacancies-section__item-format ("офис и удаленно", "можно удаленно")
- Ссылка: https://career.avito.com{href}
- Дополнительный фильтр: &managers=Y для руководящих позиций (Lead+)
- Грейд из названия: Ведущий = Senior, Руководитель = Lead, Стажёр = Junior, без префикса = Middle
- Описание: только через HTML-страницу вакансии

## Sber
- Метод: GET
- URL: https://rabota.sber.ru/public/app-candidate-public-api-gateway/api/v1/publications
- Путь к вакансиям: data.vacancies
- Пагинация: data.total, управление через skip/take
- Поля: requisitionId (str, UUID), title (str), company (str), city (str), publicationDate (str, ISO-8601), introduction (str), duties (str), requirements (str), conditions (str)
- Текстовые блоки содержат Markdown-разметку
- Фильтрация по заголовку: product/продакт/продукт/cpo
- Ссылка: https://rabota.sber.ru/search/{requisitionId}
- Описание: ЕСТЬ В API (introduction + duties + requirements + conditions)

## Alfa-Bank
- Метод: GET
- URL: https://job.alfabank.ru/api/vacancies
- Путь к вакансиям: items
- Пагинация: total, управление через skip/take
- Поля: id (str), code (str), slug (str — город из первого сегмента), name (str), description (str — сырой HTML), descriptionText (str — очищенный текст, использовать его), createdAt (str, ISO-8601), expirationDate (str), isHot (bool), isReferral (bool)
- Ссылка: https://job.alfabank.ru/vacancies/{id}
- Описание: ЕСТЬ В API (descriptionText)

## Сводка: где есть описание

| Компания | Описание в API | Нужен HTML-парсинг |
|---|---|---|
| Wildberries | Нет | Да |
| Yandex | Краткое (short_summary) | Да, для полного |
| Ozon | Нет | Да |
| T-Bank | Краткое (shortDescription) | Да, для полного |
| VK | Нет | Да (+ грейд) |
| Avito | Нет | Да |
| Sber | Полное | Нет |
| Alfa-Bank | Полное | Нет |
