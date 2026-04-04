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

## HeadHunter
- Метод: GET
- URL: https://api.hh.ru/vacancies
- Обязательные заголовки: HH-User-Agent: VacancyBot/1.0 (mois.pave@gmail.com)
- Путь к вакансиям: items
- Пагинация: page (с 0) / per_page (макс 100), ответ содержит found, pages, page, per_page
- Фильтр: employer_id=1455; двухуровневая фильтрация в main.py через is_product_role (professional_roles содержит id=73) + HH_TITLE_WHITELIST
- Поля: id (int), name (str), area.name (str), work_format (array, брать name), experience.name (str), published_at (str ISO-8601), alternate_url (str), professional_roles (array, id + name)
- Ссылка: alternate_url (https://hh.ru/vacancy/{id})
- Описание: НЕТ в списке, полное через API карточки

### API отдельной вакансии
- Метод: GET
- URL: https://api.hh.ru/vacancies/{id}
- Поля для enrichment: description (HTML, очистить теги)
- Дополнительные поля: key_skills (array)


## Касперский (через HeadHunter)
- Источник: HH API (api.hh.ru), employer_id=1057
- Детали по API и enrichment: см. секцию [HeadHunter](#headhunter)
- API: https://api.hh.ru/vacancies
- Важно: у этого работодателя professional_role id "96" используется для разработчиков, поэтому в main.py фильтрация выполняется только через KASPERSKY_TITLE_WHITELIST
- is_product_role: technical flag по professional_roles содержит id "96"
- Префикс id: hh_kaspersky_

## Циан (HH)
- Источник: HH API (api.hh.ru), employer_id=1429999
- Детали по API и enrichment: см. секцию [HeadHunter](#headhunter)
- is_product_role: professional_roles содержит id "73"
- Префикс id: hh_cian_

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

## Sber
- Метод: GET
- URL: https://rabota.sber.ru/public/app-candidate-public-api-gateway/api/v1/publications
- Путь к вакансиям: data.vacancies
- Пагинация: data.total, управление через skip/take
- Поля: requisitionId (str, UUID), internalId (number), publicationId (UUID), title (str), company (str), companyShortName (str), city (str), publicationDate (str, ISO-8601), salary_min, salary_max, workScheduleId, experienceId (UUID), specializationId (UUID), introduction (str), duties (str), requirements (str), conditions (str)
- Текстовые блоки содержат Markdown-разметку
- Фильтрация в парсере: без keyword-фильтра; дальше применяется общий TITLE_STOP_PATTERNS и SBER_TITLE_WHITELIST в main.py
- Ссылка: https://rabota.sber.ru/search/{internalId} (работает, редирект на slug-версию)
- Описание: ЕСТЬ В API (introduction + duties + requirements + conditions)
- Справочные эндпоинты:
  - GET /api/v1/profAreas (44 записи)
  - GET /api/v1/experiences (4 уровня)


## СберЗдоровье
- Метод получения buildId: Playwright открывает https://vacancy.sberhealth.ru/vacancies, из HTML тега script id="__NEXT_DATA__" извлекается buildId regex-ом
- BuildId меняется при каждом деплое фронтенда, требуется браузерный этап (parsers/browser.py)
- Эндпоинт списка: GET https://vacancy.sberhealth.ru/_next/data/{buildId}/index.json
- Путь к вакансиям: pageProps.vacancies
- Пагинация: отсутствует, все вакансии в одном ответе
- Поля: id (int), position (str), locationName (str), divisionName (str), createdAt (ISO 8601), locationId (int), divisionId (int), isPriority (bool), isPublic (bool)
- Эндпоинт карточки: GET https://vacancy.sberhealth.ru/_next/data/{buildId}/vacancies/{id}.json
- Путь к карточке: pageProps.vacancy
- Поля для enrichment: teamDescription (HTML), body (HTML), requirements (HTML), conditions (HTML)
- Справочники: отсутствуют
- Отсутствующие поля: grade, experience (извлекается regex из requirements), work_format (извлекается из conditions)

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

## Aviasales
- Метод: GET
- URL: https://vacancies-app.aviasales.ru/api/vacancies?specializations=Product+managment&language=ru
- Обязательные заголовки: нет (стандартные)
- Путь к вакансиям: корень (JSON-массив)
- Пагинация: отсутствует, все вакансии в одном ответе
- Фильтр: specializations=Product+managment (серверный)
- Поля: id (int), position (str), tags (array str), team.name (str), workPlace (null у всех, заглушка remote)
- Ссылка: https://aviasales.ru/about/vacancies/{id}
- Описание: НЕТ в списке, полное через HTML-карточку (SSR)
- Мониторинг: при каждом прогоне проверять новые ключи в объекте и workPlace != null
- Отсутствующие поля: grade, experience, published_at, work_format (заглушка remote при workPlace=null)

### Enrichment (HTML-карточка)
- Метод: GET
- URL: https://aviasales.ru/about/vacancies/{id}
- JS-рендеринг: НЕ требуется (SSR, данные в inline-скрипте)
- Данные: window._ROUTER_DATA -> loaderData -> about/vacancies/(id)/page -> vacancy
- Поля для enrichment: description + todo + requirements + conditions (HTML, очистить теги)

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


## Dodo
- Метод: GET
- URL списка: https://career-api.dodoteam.ru/api/v1/vacancies
- Путь к вакансиям: data[*].items (массив групп, у каждой поле items)
- Пагинация: отсутствует, все вакансии в одном ответе
- Поля списка: id (int), position (str), vacancy_location (str), work_format (array str), subspeciality (str), brand (str)
- Фильтр: subspeciality содержит "product" (клиентская фильтрация)
- Ссылка: https://dodoteam.ru/vacancy/{id}
- URL detail: https://career-api.dodoteam.ru/api/v1/pages/vacancy/{id}
- Enrichment: grade из data.page.content[type=vacancy_main].data.grade; description из склейки data.text блоков vacancy_text, vacancy_expectation, vacancy_you_will, vacancy_benefits (HTML, очистка через BS4)
- Ловушки: массив вакансий не плоский (двойной цикл); vacancy_location часто пустая строка; work_format может быть пустым массивом; grade отсутствует в списке, только в detail

## Точка Банк
- Метод: GET
- URL: https://hr.tochka.com/api/v2/hr/vacancies/
- Обязательные заголовки: нет (стандартные)
- Путь к вакансиям: items
- Пагинация: page-based (параметр page, с 1), фиксированный размер 20, meta.total для условия остановки
- Фильтр: category=it&specializations[]=product-management
- Поля: slug (str, роль id), title (str), city.name (str или null), workExperience (str-enum: up_to_three_years, up_to_five_years, over_five_years), workFormat (str-enum: remotely, hybrid, trips), type (str или null, "lead" у руководящих), salary (int или null, нижняя граница)
- Ссылка: https://hr.tochka.com/vacancies/catalog/{slug}/
- Описание: только через HTML-страницу
- Грейд: НЕТ В API, определяется через grade_from_experience. Если type == "lead" -> Lead+

### Enrichment (HTML)
- Метод: GET
- URL: https://hr.tochka.com/vacancies/catalog/{slug}/
- JS-рендеринг: желателен (без JS кириллица в заголовках может ломаться, тексты секций сохраняются)
- Секции описания: h2-заголовки "Что делать", "Ты подойдёшь, если", "Что ждёт тебя в Точка Банк" -- текст из sibling-элементов после каждого h2
- published_at: присутствует на странице (DD.MM.YYYY), но НЕ ИСПОЛЬЗУЕТСЯ -- вакансии могут висеть годами без обновления даты
- Справочный эндпоинт: https://hr.tochka.com/data/v2/hr/categories.json (категории и специализации)


## Циан
- Метод: POST
- URL: https://api.cian.ru/job-vacancies-backend/v2/get-vacancies/
- Тело запроса: {"filters": {"specializations": ["58"]}}
- Обязательные заголовки: Origin: https://www.cian.ru, Referer: https://www.cian.ru/, sec-fetch-dest: empty, sec-fetch-mode: cors, sec-fetch-site: same-site
- Cookie: из browser_secrets["cian_cookies"] (Playwright, parsers/browser.py). Обязательна _yasc (JS Яндекс-метрики) + минимум одна дополнительная cookie.
- Путь к вакансиям: groups[].vacancies[] (вложенная структура, нужен двойной цикл)
- Пагинация: не обнаружена; контроль обрезки по group.count vs len(group.vacancies)
- Поля: id (int), name (str), labels (array str, нетипизированный)
- Разбор labels: зарплата отсекается; "Удалённо/Удаленно" -> work_format; остальные элементы -> city (через join)
- Фильтр: specializations: ["58"]
- Enrichment: CSR (client-side rendered). initialState отсутствует в сыром HTML, появляется после JS. WAF блокирует по TLS fingerprint (waf-verdict: challenge). Решение: curl_cffi с impersonate, cookies не нужны.
- Отсутствующие поля в API списка: grade, experience, published_at


## Контур
- Метод: GET
- URL: https://kontur.ru/career/vacancies?direction=product-management
- Обязательные заголовки: стандартные
- Путь к вакансиям: HTML-страница, парсить элементы списка вакансий
- Пагинация: отсутствует, все вакансии на одной странице
- Фильтр: direction=product-management (серверный, query-параметр)
- Поля: id (int, из href /career/vacancies/{id}), title (str, содержит грейд-суффикс после последней запятой), city (str, может содержать "и ещё N городов"), work_format (str, человекочитаемая строка)
- Грейд: из суффикса title после последней запятой (junior, middle, middle+, senior, lead, middle/middle+, middle+/senior); слеш заменяется на дефис
- Ловушки:   в title повсеместно, &#x2B; вместо "+" в грейдах, hidden-элементы в списке (data-vacancy-hidden) — парсить все
- Ссылка: https://kontur.ru/career/vacancies/{id}
- Описание: через enrichment (JSON-LD JobPosting)

### Enrichment (карточка вакансии)
- Метод: GET
- URL: https://kontur.ru/career/vacancies/{id}
- JS-рендеринг: НЕ требуется (SSR)
- JSON-LD: schema.org/JobPosting присутствует на каждой карточке
- Поля для enrichment:
  - description: JSON-LD JobPosting.description (HTML entities, очистить strip_tags)
  - published_at: JSON-LD JobPosting.datePosted (YYYY-MM-DD)
  - city (полный): JSON-LD JobPosting.jobLocation[].address.addressLocality (объект или массив)
  - experience: HTML-страница, regex "Опыт от N лет/года" (НЕТ в JSON-LD)
- Fallback description: CSS-селектор div.vacancy-rubric__body (весь текст блока)


## Lamoda
- Метод: GET
- URL: https://job.lamoda.ru/api/hr/vacancies/compact
- Обязательные заголовки: нет (стандартные)
- Путь к вакансиям: data
- Пагинация: offset/limit (pagination[start], pagination[limit]), meta.start/meta.limit/meta.total, максимальный limit = 100
- Фильтр: dir[0]=upravlenie-proektami-i-produktami
- Поля: id (int), name (str), slug (str, содержит слэш — не кодировать), location.name (str, город), externalPublicationDate (str, ISO 8601), shortInfo (str|null, у продуктовых всегда null), department.name (str), direction.name (str)
- Ссылка: https://job.lamoda.ru/vacancies/{slug}
- Описание: НЕТ в списке (shortInfo=null для продуктовых), полное через API detail

### API отдельной вакансии
- Метод: GET
- URL: https://job.lamoda.ru/api/hr/vacancies/{id}
- Путь к данным: data.attributes
- Поля для enrichment:
  - description: duties (HTML) + requirements (HTML) + conditions (HTML|null) — склеить, очистить HTML
  - experience: minExperience (number|null, у всех проверенных = null)
- Отсутствующие поля: grade, experience, work_format — нет ни в списке, ни в detail
- Ловушки: HTML содержит &amp;nbsp;, пустые <br>, <p><br></p>; slug содержит слэш; вакансия "Технолог процессов ПВЗ" попадает в направление продуктов, но не является PM-ролью

## ДомКлик
- Метод: GET
- URL: https://rabota-bff.domclick.ru/api/v1/vacancies
- Обязательные заголовки: Referer: https://career.domclick.ru/
- Путь к вакансиям: data
- Пагинация: отсутствует, все вакансии в одном ответе
- Фильтр: без серверного фильтра; клиентская фильтрация через DOMCLICK_TITLE_WHITELIST в main.py
- Поля: id (str, HH ID), name (str), area.name (str, город), schedule.name (str, формат работы), experience.name (str, читаемая строка), slug (str, компонент URL)
- Ссылка: https://career.domclick.ru/vacancy/{slug}
- Описание: только сниппеты в списке, полное через detail endpoint
- Ловушки: keywords работает только по латинице и ищет по всему тексту; параметры пагинации/фильтрации игнорируются сервером; HTTP 404 при пустом результате (не JSON); хештеги в конце description — отрезать; два разных ID (id — HH ID, vacancyId — внутренний)

### API отдельной вакансии
- Метод: GET
- URL: https://rabota-bff.domclick.ru/api/v1/vacancies/{id}
- Путь к данным: data
- Поля для enrichment: description (HTML, очистить strip_tags, отрезать хештеги)
- Отсутствующие поля: grade, published_at


## Купер
- Метод: GET
- URL: https://vacancies-api.sbermarket.ru/api/vacancy_pagination/
- Обязательные заголовки: нет (стандартные)
- Путь к вакансиям: result (массив категорий, искать по category === "vacancies", данные в .data)
- Пагинация: page-based (параметр page, с 1), фиксированный размер 10, условие остановки: result[category=pagination].data.pages
- Фильтр: group=186247de-f72e-469e-9da3-db468f9b6197 (Product & Project Management)
- Поля: id (str, UUID), title (str), city (str, человекочитаемая), grade (array[str], может быть []), wf (array[str], может быть []), workExperience (int|null, число лет), description (str, HTML preview), friendlyUrl (str, ключ для detail и URL), group (str), division (str), idForUrl (int, не используется)
- Ссылка: https://team.kuper.ru/vacancies/{friendlyUrl}
- Описание: PREVIEW в списке (укороченное), полное через API detail

### API отдельной вакансии
- Метод: GET
- URL: https://vacancies-api.sbermarket.ru/api/vacancy/{friendlyUrl}
- Формат: JSON, каждое поле обёрнуто в {value, displayName, order}, данные в .value
- Поля для enrichment:
  - description: descriptionVacancy.value + responsibilities.value + requirements.value + terms.value (HTML, склеить, очистить)
- Отсутствующие поля: published_at — нет ни в списке, ни в detail
- Ловушки: detail принимает только friendlyUrl, не UUID и не idForUrl; структура result в списке — массив категорий, не обращаться по индексу; grade и wf — массивы, могут быть пустыми []; workExperience — int, не строка; домен API (sbermarket.ru) отличается от домена сайта (kuper.ru)

## МТС
- Метод: POST
- URL: https://api.job.mts.ru/v1/vacancies/filtered/career
- Обязательные заголовки: x-api-key (JWT Ed25519, автообновление из HTML https://job.mts.ru/)
- Путь к вакансиям: data.vacancies
- Пагинация: offset/limit, max limit 200, условие остановки offset >= data.pageInfo.total
- Поля: id (str), name (str), info.city (str), info.experience (str), info.worktype (str), info.date (str, русская дата), info.brand (str, маппинг в company), info.category (str, используется для фильтрации)
- Фильтр: клиентский вариант C — PM-категория целиком + строгий whitelist для остальных категорий
- Ссылка: https://job.mts.ru/vacancy/{id}
- Описание: через API detail (4 текстовых блока, plain text)
- Экосистема: один API, 5 компаний (МТС, МТС Банк, MWS.AI, KION, Юрент), маппинг по info.brand

### API отдельной вакансии
- Метод: GET
- URL: https://api.job.mts.ru/v1/vacancy/{id}
- Поля для enrichment: detailText.descriptionOfProject + detailText.description + detailText.requirements + detailText.conditions (plain text)



## МТС Линк
- Метод: GET
- URL: https://mts-link.ru/api/huntflow/vacancies?categoryId=221722
- Обязательные заголовки: Authorization: Bearer (статический), Origin: https://job.mts-link.ru, Referer: https://job.mts-link.ru/
- Путь к вакансиям: корень (JSON-массив)
- Пагинация: отсутствует (API отдаёт все вакансии одним массивом)
- Фильтр: categoryId=221722 (направление «Продукт»)
- Поля: id (int), position (str), workExperience (str-enum), workFormat (str), accountDivision (str), created (object), hidden (bool), money (str)
- Ссылка: https://job.mts-link.ru/vacancy/?id={id}
- Описание: через API detail (body + requirements + conditions, HTML)
- Отсутствующие поля: grade, city

### API отдельной вакансии
- Метод: GET
- URL: https://mts-link.ru/api/huntflow/vacancy/{id}
- Поля для enrichment: body (HTML) + requirements (HTML) + conditions (HTML)

## X5 Group
- Метод: GET
- URL: https://rabota.x5.ru/public/api/vacancies/vacancies/
- Обязательные заголовки: нет (стандартные)
- Путь к вакансиям: items
- Пагинация: page-based (page с 1, page_size, по умолчанию 10). Условие остановки: next_page is None
- Фильтр: vacancy_categories=18858 (категория "Управление продуктом")
- Поля: id (str, hex), name (str), city (str или null), work_format (str enum: office/hybrid/remote или null), data.experience (str или отсутствует), data.main_responsibilities (str или отсутствует), data.professional_skills (str или отсутствует), business_units (array objects с id и title), category.negotiation_type (str)
- Ссылка: https://rabota.x5.ru/vacancies/{id}
- Описание: ЕСТЬ В API (data.main_responsibilities + data.professional_skills)
- Экосистема: один API, 7 компаний (X5 Tech, Пятёрочка, Перекрёсток, Чижик, X5 Media, X5 Импорт, Много лосося), маппинг по business_units[0].title
- Справочный эндпоинт: GET https://rabota.x5.ru/public/api/vacancies/filters/ (категории, BU, форматы, города)
- Отсутствующие поля: grade, published_at

### API отдельной вакансии
- Метод: GET
- URL: https://rabota.x5.ru/public/api/vacancies/vacancies/{id}/
- Статус: Возвращает те же данные, что и список. Enrichment не требуется.

## 2ГИС
- Метод: GET
- URL: https://job.2gis.ru/project/
- Обязательные заголовки: стандартные (config.REQUEST_HEADERS)
- Путь к вакансиям: HTML-страница, ссылки с href /project/{id}/
- Пагинация: отсутствует, все вакансии на одной странице
- Фильтр: директория /project/ (продуктовые + проектные вакансии, проектные отсекаются TITLE_STOP_PATTERNS в main.py)
- Поля: id (int, из href), title (str, текст ссылки), work_format (str, из текста карточки — "Удалённая работа" или "Не указан")
- Ссылка: https://job.2gis.ru/project/{id}/
- Описание: через enrichment (HTML h2-секции + JSON-LD fallback)
- Отсутствующие поля в списке: grade, city, experience, published_at, description

### Enrichment (карточка вакансии)
- Метод: GET
- URL: https://job.2gis.ru/project/{id}/
- JS-рендеринг: НЕ требуется (SSR)
- JSON-LD: schema.org/JobPosting может присутствовать (datePosted, jobLocation)
- Секции описания: h2-заголовки "Что предстоит делать", "Что будет входить в задачи", "Вам точно предстоит", "Ключевые задачи", "Что мы ожидаем", "Кого мы ищем", "Что предлагаем", "Что мы предлагаем"
- Поля для enrichment:
  - description: текст из целевых h2-секций (склеить через \n\n)
  - experience: regex "Опыт от N лет/года" из полного текста страницы
  - published_at: JSON-LD JobPosting.datePosted (если присутствует)
  - city: JSON-LD JobPosting.jobLocation[].address.addressLocality (если присутствует)

## Сводка: где есть описание

| Компания | Описание в API | Нужен HTML-парсинг |
|---|---|---|
| 2ГИС | Нет (HTML h2-секции + JSON-LD) | Да |
| Wildberries | Полное (структурированное) | Нет |
| Yandex | Полное | Нет |
| Ozon | Полное | Нет |
| T-Bank | Полное (HTML-парсинг h2-секций) | Да |
| VK | Полное (HTML-парсинг h3-секций + грейд из h4) | Да |
| Sber | Полное | Нет |
| СберЗдоровье | Полное (API detail, HTML очистка) | Нет |
| Alfa-Bank | Полное | Нет |
| Aviasales | Нет (HTML-карточка: SSR window._ROUTER_DATA) | Да |
| Avito | Полное (JSON-LD schema.org/JobPosting + HTML fallback) | Да |
| Dodo | Полное (API detail) | Нет |
| Купер | Полное (API detail) | Нет |
| Точка | Нет (HTML-парсинг h2-секций) | Да |
| Циан | Нет (CSR HTML, initialState после JS) | Да (curl_cffi, TLS impersonate) |
| Контур | Нет (JSON-LD enrichment) | Да |
| Lamoda | Нет (API detail: duties + requirements) | Нет |
| ДомКлик | Полное (API detail) | Нет |
| HeadHunter | Полное (API detail) | Нет |
| Касперский | Полное (API detail) | Нет |
| Циан (HH) | Полное (API detail) | Нет |
| МТС | Полное (API detail, plain text) | Нет |
| МТС Линк | Полное (API detail) | Нет |
| X5 Group | Полное (API список) | Нет |
