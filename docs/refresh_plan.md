# Новая разрешённая фаза — project/bizdev и простой test флоу, 2 октября 2026 (Москва)

Пользователь поручил заменить test срез на project management + business
development, эмпирически стремясь к ≥95% полноте доступного пула. Сначала
изучить native groups и product whitelist/blacklist, сохранить широкий пул для
повторной офлайн-фильтрации; проверять recall на размеченной выборке, не
выдавать полноту локального классификатора за покрытие заблокированных сайтов.
Последнее уточнение пользователя: названия de facto ролей заранее неизвестны.
Близкие названия проверять по полным обязанностям, подтверждённые добавлять
как company aliases с регрессами. Цель — 95% подтверждённых подходящих
вакансий внутри нативных подборок компаний, не от всего каталога.
Отраслевых, skill или архетипных ограничений пока нет. Project — tier1, bizdev — tier2, монетизация не требуется
и не повышает ранжирование. Архетипы появятся после оценки пула относительно
реальных навыков конкретного соискателя; не выдумывать профиль навыков.
Новое поручение разрешает простой UI: /start сразу выдаёт вакансии, настройки
грейда и mute сохраняются. Сценарий — девушка project manager с последним
опытом в монетизации и интересом к проектной деятельности. Данные/обоснования
отбора сохраняются для будущей аналитики; сама AI-аналитика пока не запускается.
Production/исходный бот не изменяются; работать в текущей ветке/PR129.
До четырёх логических подходов на проблемный источник, сохранённый пул
позволяет итерировать без повторных сетевых прогонов. Ниже — история предыдущей
фазы; её запреты нового UI/project/bizdev отменены текущим поручением.

## Проверенное состояние test, 2 октября 2026 (Москва)

Runtime SHA969e5d12aebd557dd377a9b63fceb1f88ddb99ee, classifier
project-bizdev-2026-10-02.5, 50 company aliases с подтверждёнными обязанностями.
22 доступных source snapshots содержат12270 объявлений. Core collect
[37004468351](https://github.com/Zadnessa/prodradar/actions/runs/37004468351)
сохранил374 active project_bizdev:248 project и132 bizdev,6 относятся к обеим
семьям. У всех374 есть описание;0 битых/деактивированных. Последний прогон
отправил10 карточек. Workflow failure отражает только unavailable Купер403;
остальные источники, запись и доставка завершены. Dodo остаётся на прежней
test паузе; новых подтверждённых career5xx нет. Не повторять исчерпанные
подходы Купера и не считать его пустым успешным источником.

Новый slim TEST production опубликован: dpl_3SqDHaVNywS8oXH2mfi2A5GwcQgy,
READY, stable https://prodradar-test.vercel.app/api/webhook.
TEST project prj_3WEWtX8vujb0llpvmuA1Umovf623,
team team_OIdVeiXMtcQdNxXpseWNqQtV. Authenticated live /start и /settings
вернули200; /start отправил8 карточек, delivered91→99. Все8 IDs из test
project_bizdev с family project. Webhook pending0, last_error отсутствует.
Не очищали delivery history. Исходный bot/token/production не использовали.
Simple flow: /start сразу8 project, bizdev отдельным fallback, grade/mute/pause,
sm:seen:family:offset явно возвращает просмотренное без сброса истории.
88 локальных тестов прошли; Actions запустил88, optional PyNaCl skipped1.

Отчёт [test_role_slice.md](test_role_slice.md) содержит размеры7 полностью
размеченных native категорий (164 членства с пересечениями), доли отбора,
FN/FP, проверку обязанностей и абляцию. МТС29 дочитаны: version.4 пропускала
1 из10 project — пресейл полного цикла. Version.5 получает10/10 без FP;
исходная оценка сохранена в mts_native_before_alias.json. После фикса это
calibration; 100% этих регрессов не доказывают независимые95% всех компаний.
34 выбранных названия широкого пула пока вне title gold; полный native audit
остальных компаний и независимая новая контрольная выборка ещё нужны.
Снимок metrics/ошибок: test_role_slice_metrics.json. Не считать долю взятых
объявлений из группы полнотой относительно подтверждённых target.

Рабочая машина временно теряла связь (connectivity=offline); бот и GitHub
оставались доступны. Среда восстановлена, код синхронизирован, сбор и
публикация выше выполнены. Offline не означает отключение бота/токенов.

После публикации удалены ещё2 устаревших непривязанных test deployments:
8pv3wo8BQGN6aCBWmKu9mESdgtoz и4DSVaw86DX684mdEHXxDTfbL3ReN.
Current/aliases и здоровый rollback8MRFgWvvZ2FSwrRTfqsA9iRwres9 сохранены.
Original production не тронут, billed Function Storage GB API не показывает.
Не включать cron, не merge, не подменять blocked sites HH.


# Рефреш ProductRadar: контекст и фазы

Этот документ определяет границы работы для продолжения в другом чате.
Выполнять только явно порученную фазу. Незавершённые проверки не считать
успешными и не переходить автоматически к переделке продукта.

## Актуальное поручение и передача первого прохода

Пользователь разрешил автономный проход **1–4**: сохранить исходный продукт и
данные, подготовить изолированное окружение @ProdRadar_bot, восстановить
**фирменные API** и проверить прежний флоу. HH использовать для сверки полноты,
не заменять им восстанавливаемые фирменные источники. Прежние HH-адаптеры,
включая Циан, сохранены. DevTools-диагностика разрешена для поиска контракта API;
browser runtime
служит только доступу через антибот/cookies/токены, не выгружает вакансии.
Обычный HTTP HTML-enrichment допустим, если API не даёт полный текст.
Необходимые browser secrets подключать через
общий `parsers/browser.py`. Project-профиль и новый интерфейс пока не разрешены.
Пользователь считает прежнего бота архивным после длительного простоя.

Продолжать в `/workspace/prodradar`, ветке `codex/restore-test-bot` и
[PR #129](https://github.com/Zadnessa/prodradar/pull/129). Новые PR ради
документации не создавать. Не сливать ветку и не разворачивать её как production
в исходном Vercel-проекте. Пользователь попросил завершить доступное в текущем
экземпляре и сохранить точную передачу для нового чата с обновлённым токеном.

### Приоритет следующей сессии

**Работы возобновлены, 1 октября 2026 (UTC).** Пользователь поручил надёжный сбор
по текущим компаниям: обычная браузерная загрузка для метаданных/доступа, затем
API или HTTP HTML-enrichment. До четырёх разных логических подходов на
проблемный источник; транспортные повторы одного запроса — отдельный bounded
retry, не новый поиск. При подтверждённом 5xx самого карьерного сайта источник
временно паузится только в test, с сохранением причины. Ошибка локального proxy
не доказывает origin 5xx. Production и cron по-прежнему не включаются.

Итоговый collector [36935834198](https://github.com/Zadnessa/prodradar/actions/runs/36935834198)
(SHA 3e89cdb): 22 источника собраны, Купер — единственный blocked/403;
811 raw →224 product, 25 новых Т-Банка, 199 без изменений, 0 снятых/битых.
25/25 Т-Банк имеют все четыре html_sections в test БД. Collector отправил
10 карточек, delivered 32→42; отдельная контрольная карточка Т-Банка успешно
отправлена через bot/telegram_api.py и отмечена delivered, итого43.
Тестовая БД:225 total/224 active/224 active descriptions, 21 компания с
подходящими вакансиями. Webhook ProdRadar_bot: pending=0, ошибок нет.
Workflow failure честно отражает Купер 403; остальные источники/сохранение/
доставка завершены. Новых origin 5xx не найдено, новых пауз не добавлено;
Dodo сохраняет прежнюю test паузу. 51 локальный тест проходит; collector
Actions запускал50, один optional PyNaCl test skipped, остальные прошли.

История baseline перед исправлениями:
Baseline [36933860419](https://github.com/Zadnessa/prodradar/actions/runs/36933860419):
22 парсера успешны, один tbank ServerDisconnectedError. 577 raw /199 product,
65 новых, 134 неизменных, 1 снята, 0 битых; 10 карточек отправлены одному
активному test пользователю с пустыми filters и paused=false. МТС 32 и VK 24 raw
успешны в Actions; локальные блокировки их API не требуют переделки контракта.
Купер: Actions 36935380788 подтвердил 403 карьерного сайта в HTTP, Chrome
TLS и Chromium. Старый API/group и общий каталог проверены; нового публичного
контракта получить не удалось. Лимит подходов исчерпан без слепого перебора.
Он остаётся enabled и reported blocked, а не empty success/5xx pause.
Т-Банк: до двух повторов того же запроса после transient disconnect; MTS/VK:
проверка полной пагинации, VK enrichment больше не сокращает описания/grade.
50 локальных регрессий проходят; финальный collector проверяет live поведение.
Dodo пока сохранён в прежнем отключённом состоянии по отдельному решению.

**Vercel очищен и облегчён (1 октября 2026 UTC).** Пользователь поручил
остаться на бесплатной квоте после предупреждения 75% Function Storage/10GB.
Инвентарь: 32 из 52 deployments созданы 1 октября, 28 относятся к ветке
восстановления; автоматические previews от push увеличили расход.
Удалены 28 старых deployments (26 original preview +2 test), затем созданы две
компактные test сборки: осталось 26 вместо 52 (23 original +3 test).
Все 28 alias bindings сохранены, повторный dry-run candidates=[].
Исходный production dpl_83b2b6GGhrwLU3nDU5PCJq1v2yhJ сохранён;
новый test production dpl_8MRFgWvvZ2FSwrRTfqsA9iRwres9, здоровый rollback
dpl_4DSVaw86DX684mdEHXxDTfbL3ReN, current preview
dpl_8pv3wo8BQGN6aCBWmKu9mESdgtoz. Проверки стабильного test домена:
unauth webhook 403, auth unknown user 200, redirect без цели 400;
identity ProdRadar_bot. Original live не переразмещался.
requirements.txt теперь только webhook; Playwright/curl_cffi/bs4 отделены
в requirements-collector.txt, collector исключён .vercelignore. Локальный
размер dependencies 223→39MB. Git previews этой ветки отключены; последующий
push действительно не создал original preview. Инвентарь/план/результат
приватно в /tmp/prodradar-vercel-*.json. API не возвращает billed storage GB,
поэтому текущий процент квоты не подтверждён этими измерениями.

**GitHub настроен, проверено агентом 2 октября 2026.** Пользователь добавил
bootstrap environment secret PRODRADAR_GITHUB_TOKEN и явно поручил агенту
проверку. Автоматическая команда configure-github завершена полностью:
- export-key: [36932808570](https://github.com/Zadnessa/prodradar/actions/runs/36932808570), success;
- apply: [36932843737](https://github.com/Zadnessa/prodradar/actions/runs/36932843737), success;
- read-only check: [36932886519](https://github.com/Zadnessa/prodradar/actions/runs/36932886519), success.

Обновлены только variables SUPABASE_URL, ADMIN_CHAT_ID и secrets SUPABASE_KEY,
TELEGRAM_BOT_TOKEN в prodradar-test; HH_ACCESS_TOKEN сохранён. PAT доступен
новому Actions job независимо от snapshot Codex. Проверки companies,
city_mappings, users, user_vacancy_delivery проходят; vacancies=135,
descriptions=135; getMe=ProdRadar_bot, webhook зарегистрирован, pending=0,
ошибок нет; admin chat ready; HH HTTP 200. VERCEL_TOKEN в Actions не переносился
и является optional. Реальные test значения получены в память через Management
и test Vercel; перенесены sealed box, plaintext не сохранялся.

**История проверки GitHub до возобновления парсеров:**
В тех setup/check запусках collector и diagnose skipped, сообщения не
отправлялись. После возобновления выполнен baseline и исправлены парсеры,
как описано выше. Исходный TELEGRAM_BOT_TOKEN не использовался, repo Secrets
и production не изменены.
Ниже сохранена история первоначального блокера и подготовки автоматизации;
требование вручную добавить bootstrap secret уже выполнено.

**Проверка bootstrap автоматизации:** Actions 36932011864 запущен
из bdb8307, setup job дошёл до экспорта public key и вернул точное сообщение
«Добавьте environment secret PRODRADAR_GITHUB_TOKEN в prodradar-test».
Данных не записано, collector пропущен. Live подготовка реальных test
реквизитов через Management/test Vercel, identity/ref и шифрование проверены
без записи plaintext. Публичный ключ передаётся через annotation GitHub API;
artifact оставлен для просмотра. Это устраняет зависимость автоматизации от
недоступного в текущем proxy временного blob host логов/artifacts.

**История ограничения и автоматизации GitHub (2 октября 2026).**
Пользователь приостановил парсеры/сбор/доставку и попросил сначала разобраться с
GitHub, автоматизируя всё доступное. Аудиты 36930639922 и 36930607479 отменены.
Контролируемые запросы /user с явным PAT, без Authorization и с заведомо
невалидным Authorization все дают HTTP 200 / Zadnessa. Заголовок сохраняется
локальным requests, но GitHub видит один OAuth client Iv23liVemv8A9if9v0F2.
У chatgpt-codex-connector есть Actions/Contents write, но нет Environments.
Настройки PAT пользователя проверены по скриншоту и соответствуют задаче;
повторно просить расширить их не нужно. Операции environment выполняет
отдельный Actions job с PAT из environment secret, вне proxy Codex.

Подготовлена `scripts/run_profile.py --profile test configure-github`: Actions
экспортирует только public key в annotation/artifact, Codex получает реальные test реквизиты через
Supabase Management/test Vercel, проверяет identity/ref, шифрует в памяти и
отправляет ciphertext второму setup job. Job обновляет только SUPABASE_URL,
ADMIN_CHAT_ID, SUPABASE_KEY и TELEGRAM_BOT_TOKEN в prodradar-test, проверяет
наличие HH_ACCESS_TOKEN. Затем отдельный read-only check, без collector.
Единственный начальный ручной шаг — добавить **environment secret**
PRODRADAR_GITHUB_TOKEN в **prodradar-test** через GitHub UI. Пользователь уже
имеет соответствующий PAT; интеграция Codex не может создать этот секрет сама.
Тесты проверяют sealed-box roundtrip и отказ до записи при чужом environment,
исходной БД, смене key_id, лишних/незашифрованных секретах. Первоначально результат полного переноса не был подтверждён; теперь его
подтверждают три успешных Actions run, указанных выше.

**Продолжение 2 октября 2026, текущая сессия.** TEST_* проходят реальные
read-only проверки: test ref, @ProdRadar_bot, webhook pending=0, admin chat,
135 вакансий / 135 описаний и HH HTTP 200. Реализованы явные профили в
runtime_profiles.py и scripts/run_profile.py; без fallback, с проверкой ref,
identity и redirect до команды. PROD_* отсутствуют и не используются.
PRODRADAR_GITHUB_TOKEN проверен через /user (Zadnessa) и Actions (200), но
variables/secrets/public-key environment всё ещё отвечают 403 с требованием
`environments=read`. Пользователь подтвердил, что Environments read/write
выдано; несоответствие ещё не разрешено. Общий TELEGRAM_BOT_TOKEN не вызывался.
Пока environment нельзя обновить, подготовлен отдельный ручной read-only
`audit_sources=true` в зарегистрированном Check Test Environment: input содержит
только справочники test БД, job не получает DB/Telegram credentials. Это аудит,
не успешный collector. Результаты и доставка будут дописаны после проверки.

**Передача после настройки секретов (2 октября 2026).** Пользователь переходит
в новую сессию: текущая не используется для проверки добавленных env. Продолжить
в `codex/restore-test-bot`, PR #129, без новых проектов/PR и без слияния в main.
Песочница уже работает; повторный provision схемы не нужен.

**Что добавить в настройках облачного окружения Codex:** существующие общие
переменные/секреты сохранить, вместо их перезаписи добавить отдельные test-имена.

| Имя | Тип | Откуда взять значение | Домены секрета |
| --- | --- | --- | --- |
| `TEST_SUPABASE_URL` | Переменная | `https://jmsdxgylyjxwdwmdrmxw.supabase.co` | — |
| `TEST_SUPABASE_KEY` | Секрет | Supabase → проект ProdRadar-test → Settings → API Keys → Legacy anon/service_role → service_role → Reveal | `jmsdxgylyjxwdwmdrmxw.supabase.co`, `api.vercel.com` |
| `TEST_TELEGRAM_BOT_TOKEN` | Секрет | @BotFather → /mybots → @ProdRadar_bot → API Token; копировать существующий token | `api.telegram.org`, `api.vercel.com` |
| `PRODRADAR_GITHUB_TOKEN` | Секрет | GitHub Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token | `api.github.com` |

Для GitHub token: Resource owner **Zadnessa**, Only select repositories →
**prodradar**, Repository permissions → **Environments: Read and write**,
**Actions: Read and write**, **Contents: Read-only**; Metadata read-only
добавляется автоматически. SUPABASE_ACCESS_TOKEN, VERCEL_TOKEN, HH_ACCESS_TOKEN,
ADMIN_CHAT_ID и остальные существующие настройки сохранить. В Vercel ничего
дополнительно копировать не требуется: test env уже установлен.

**Первые действия нового чата:** проверить readiness и реальные API с новыми
именами; использовать PRODRADAR_GITHUB_TOKEN для GitHub-команд. Добавить в репозиторий
явный выбор профиля `test`/`prod`: test-имена отображаются на стандартные
SUPABASE_URL/KEY и TELEGRAM_BOT_TOKEN **до импорта config** только в выбранном
процессе. Тестовый профиль проверяет project ref и @ProdRadar_bot, без fallback
на общие переменные при отсутствии test-ключа. Для будущего production использовать
отдельные PROD_SUPABASE_URL/KEY и PROD_TELEGRAM_BOT_TOKEN после сверки identity
@findproductjob_bot и исходной БД; глобальные настройки не переключать скрыто.
Эта поддержка профилей пока запланирована, текущий код ещё не читает TEST_*.

Затем обновить **только GitHub environment prodradar-test**: variables
SUPABASE_URL (test URL), ADMIN_CHAT_ID; secrets SUPABASE_KEY (test service_role),
TELEGRAM_BOT_TOKEN (@ProdRadar_bot), проверить существующий HH_ACCESS_TOKEN.
Для шифрования GitHub secrets брать реальные значения через Management API/Vercel
в память, не шифровать proxy placeholders Codex. Repo Secrets исходного collector
не менять, production и cron не включать. Сначала read-only check, затем ручной
Check Test Environment, ID 372368844, ref codex/restore-test-bot,
input collect_test=true. Последний push без флага уже проверен в Actions
36927628877: check success, collect skipped.

**Что довести по парсерам и доставке:**

- Альфа, Т-Банк, Точка: повторить сбор в Actions, где доступна официальная CA-цепочка; проверить все страницы и полные product-описания, сохранить результат в тестовую БД. Локальный proxy TLS 503 не лечить отключением проверки сертификатов.
- МТС, VK: проверить текущие фирменные list/detail в Actions; если ошибка повторяется там, исправить endpoint, transport или пагинацию по фактическому контракту. Локальные upstream 503 МТС и CONNECT 403 VK сами по себе не доказывают баг парсера; HH fallback не добавлять.
- СберЗдоровье: установить Chromium подходящей версии Playwright в новой среде/Actions, проверить buildId до collector. Источник уже повторно успешен: 46 raw / 6 product, описание всех шести сохранено.
- Купер: отдельно сверить общий фирменный каталог с карьерным сайтом, установить охват API и пагинацию; не считать пустой product-group доказательством полной выдачи. При необходимости исправить фирменный контракт, HH использовать только для сверки.
- Dodo оставить отключённым только в тестовой БД, отложен пользователем; не включать в ближайший прогон и не исследовать без нового поручения.
- После исправлений выполнить один защищённый collector: отсутствие ошибок по остальным включённым источникам, данные/полные описания сохранены, нет пропущенных битых вакансий. Проверить активность/paused и фильтры тестового пользователя, нажать «Вакансии» и сверить новые delivered с фактическими карточками. Бот сохраняет отбор product manager: все карточки означают все подходящие вакансии, не весь сырой каталог компаний.

**Текущий запуск: песочница и прежний флоу подтверждены, продолжаем парсеры.**
2 октября 2026 пользователь сообщил: «Все прекрасно работает» и поручил
продолжить восстановление парсеров. Проверка новой БД: один пользователь,
22 delivered, потерянных ссылок на vacancy нет; есть события обоих путей
онбординга, выдачи, настроек, блокировки, паузы и отписки. T-052 завершена;
полный успешный сбор источников всё ещё не подтверждён.

Для следующего шага предпочтителен collector в GitHub Actions, где банки ранее
проверены без ограничений proxy этой среды. Нужен доступ с правами Environments
read/write и Actions read/write к `Zadnessa/prodradar` (например, отдельный
сетевой secret `PRODRADAR_GITHUB_TOKEN` для api.github.com). Текущая интеграция
получает 403 на environment `prodradar-test`. После предоставления доступа
обновить только его test URL/KEY, сверить bot token как @ProdRadar_bot,
ADMIN_CHAT_ID и HH_ACCESS_TOKEN; repo Secrets исходного collector не менять.
Текущие runtime SUPABASE_URL/KEY в Codex всё ещё привязаны к исходному проекту:
новое поручение сохраняет их и добавляет отдельные TEST_* из таблицы выше.
Для обычных команд сначала реализовать явный выбор профиля. Сейчас локальные
операции получают нужный test key через Management API в память.

`collect_test.yml` отсутствует в списке зарегистрированных workflows (GET — 404).
Подготовлен ручной запуск через уже зарегистрированный `Check Test Environment`
(ID 372368844), input `collect_test=true`, ref `codex/restore-test-bot`.
Job сборщика запускается только при workflow_dispatch с явным true и после
успешного read-only check. Push и запуск без флага не собирают вакансии.
До обновления environment ручной collector не запускать. Dodo остаётся отложен,
полнота Купера — отдельная проверка; HH не заменяет фирменные источники.

Повторные сетевые пробы текущей среды подтвердили: VK CONNECT denied/403,
МТС proxy upstream connection termination/503, Альфа proxy upstream
CERTIFICATE_VERIFY_FAILED/503. Unrestricted HTTP policy enforced и ready secrets
не устраняют upstream TLS или отказ proxy. Новые API-токены банков/VK/МТС
не требуются по этой диагностике. Для локального полного сбора нужна настройка
самого proxy/допуска этих hosts; изменение CA только внутри Python этого не решает.

Новый Management token успешно читает оба проекта, ключи и SQL. Уже существующая
БД `jmsdxgylyjxwdwmdrmxw` была пустой; в одной транзакции загружены 6 таблиц,
35 компаний и 53 city mappings. Пользователи, вакансии и история до сборщика
оставались пустыми. Колонки, constraints, индексы, RLS policies и ACL сверены
с исходной схемой; массив `pg_policies.roles` нормализован при сравнении.
`supabase_admin` default privileges уже совпадали: облачная роль `postgres`
не имеет права повторять их ALTER. Provision теперь проверяет точное совпадение
платформенных ACL до записи и сохраняет их; различие останавливает загрузку.
Первый отказ откатил транзакцию целиком. Dodo отключён только в новой БД.

В существующий Vercel `prodradar-test` подключён настоящий service_role новой БД.
Deployment на `https://prodradar-test.vercel.app` готов. Vercel SSO protection
отключена только у тестового проекта: Telegram нужен публичный HTTP endpoint;
webhook по-прежнему защищён `TELEGRAM_WEBHOOK_SECRET`. Live POST без секрета —
403, аутентифицированный POST с неизвестным пользователем — 200/`ok=true`
после чтения тестовой БД. Vercel proxy передаёт тело с `Transfer-Encoding: chunked`
без Content-Length; исправлено чтение chunks в `api/webhook.py`, иначе прежний
код отвечал 200/`ok=false` из-за пустого JSON. Диагностические варианты размещения
заменены обычным кодом. Только webhook **@ProdRadar_bot** переведён на
`https://prodradar-test.vercel.app/api/webhook`, pending updates=0.
Исходный **@findproductjob_bot** сохраняет
`https://prodradar.vercel.app/api/webhook`; его БД, env и размещение не менялись.
Исходный workflow `collect.yml` остаётся `disabled_inactivity`, cron не включался.

**Сбор успешен частично, полный прогон не подтверждён.** Защищённый локальный
collector получил 445 сырых вакансий и сохранил 129 product-вакансий с полными
описаниями, затем завершился ошибкой из-за шести источников. Перед ним не был
проверен установленный Chromium; СберЗдоровье упало на отсутствующем executable.
Установлен Chromium текущей версии Playwright, проверен локальный browser smoke,
повторён только СберЗдоровье: buildId получен, 46 raw / 6 product, все описания,
ошибок 0. Итого **135 вакансий и 135 непустых описаний** в новой БД.
Остаются пять ошибок среды: Альфа/Т-Банк/Точка — proxy upstream TLS 503,
МТС — proxy upstream connection termination 503, VK — отказ CONNECT самого
proxy с 403. Это не успешный полный сбор и не доказательство ошибки API VK.
Ранее успешные Actions банков сохраняют силу для своего окружения, но не
подменяют успешный тестовый collector в текущей среде. Dodo не запускался;
полнота Купера не объявляется подтверждённой. HH fallback не добавлялся.

GitHub GET variables/secrets environment `prodradar-test` возвращает 403;
обновление URL/KEY там не выполнено. Repo Secrets исходного collector не менялись.
Для полного тестового collector в Actions нужен доступ к этому environment,
затем обновление только его URL/KEY. Локальный прогон не исправляет его настройку.

Приватный архив прошлого экземпляра отсутствовал, поэтому повторены REST и SQL
backup: 638 vacancies, 65 users, 15323 delivery, **140406 events**, 35 companies,
53 mappings. В PostgreSQL 17 проверены все значения каждой строки, количества,
каталог и RLS. Новая копия:
`/workspace/prodradar-backups/prodradar-original-verified-2026-10-01-session2.tar.gz`,
SHA-256 `21c6f71ae7c82074d2c130d40b16e22fd2e08e57a101a7d7e2907e57c8c0cf06`.
REST/SQL и отчёты `restore-check.json`, `webhook-check.json`,
`test-environment-check.json`, `test-collector.json`, `test-sberhealth.json`
находятся вне Git в `/workspace/prodradar-backups`. Скрипты текущих операций
в `/workspace/prodradar-cloud` получают секреты из API в память. Эти файлы
также не переносятся автоматически в другой экземпляр.

28 регрессий проходят. Пользователю отправлен чеклист настоящих нажатий:
полный онбординг и быстрый старт, выдача/Ещё/Хватит/Все, настройки, mute/unmute,
returning /start, просмотренные, pause/resume/stop. Пользователь подтвердил
работоспособность флоу, delivery сверён; полный проход 1–4 остаётся открытым
по сбору источников. Записи ниже описывают
состояние перед текущим запуском, когда облачная схема и deployment ещё отсутствовали.

Последнее решение пользователя: **продолжить с Supabase и запустить тестовый
@ProdRadar_bot на прежнем флоу**. Пользователь сообщил, что карьерный сайт
Dodo недоступен, предположил ремонт и отложил повторную проверку. Не исследовать
Dodo перед запуском и не считать его доступность условием тестового запуска.
После подключения новой БД временно отключить `parser_name=dodo` через
`companies.is_enabled` **только в тестовой БД**, чтобы ручной сбор не повторял
известную внешнюю ошибку. Исходную БД и код парсера не менять; вернуть источник
после успешной повторной API-проверки. Проверка наличия любых вакансий Купера
выполнена; его неподтверждённая полнота остаётся отдельной задачей.

### Подтверждённое состояние на 1 октября 2026

**Резервирование прикладного продукта завершено и проверено локальным
восстановлением.** В этом экземпляре повторно сохранены все шесть таблиц:
638 вакансий, 65 пользователей, 15 323 доставки, 140 329 событий, 35 компаний,
53 city mappings. REST-снимок ограничен верхним первичным ключом и сверяет
число строк; это не транзакционный dump изменяющейся БД.

`scripts/backup_schema.py` через Management API сохраняет согласованный снимок
каталога `public` и воспроизводимый SQL: 6 таблиц, 55 колонок, 3 sequences,
12 constraints, 14 индексов (9 обеспечиваются constraints), 7 RLS policies,
права и default privileges. Пользовательских функций и триггеров нет.
Это схема приложения; внутренние схемы Supabase `auth`/`storage` и платформенные
роли не входят в копию. Неподдерживаемые объекты останавливают генерацию.
Bigint-параметры sequences возвращаются строками, чтобы Management API не
округлял их через JavaScript number.

В Docker PostgreSQL 17 восстановлены схема и **все данные**: количества и
канонические SHA-256 каждого значения во всех строках совпали; каталог колонок,
constraints, индексов, policies, ACL и default privileges совпал.
Проверены RLS: `anon` видит 0 пользователей/доставок/событий и 638 вакансий,
`service_role` видит 65 пользователей. Второй локальный тест проверил
`scripts/provision_test_database.py`: только 35 companies и 53 city mappings,
а vacancies/users/delivery/events остаются пустыми. Это локальная проверка,
**не восстановление в новой облачной БД**.

Файлы вне публичного Git:
`/workspace/prodradar-backups/rest`, `sql-verified`, `restore-check.json`,
`reference-check.json`, `prodradar-history.bundle`. Bundle содержит полную
исходную историю `main` (`00b3162…`) и прежний HEAD PR (`97bd333…`).
Архив для переноса: `/workspace/prodradar-backups/prodradar-original-verified-2026-10-01.tar.gz`.
**SHA-256 архива:** `db31cce7804a7eb8566a913eb4178490b34b57c8aa9ee0b6c8473192170b20ce`.
**Файлы не переносятся автоматически в другой экземпляр.** При отсутствии
архива повторить выгрузку, не считать старую копию доступной. Пользовательские
данные и ключи не помещать в Git; архив содержит пользовательскую историю.

**Supabase Management API работает для исходного проекта.** Текущий
`SUPABASE_ACCESS_TOKEN` есть; GET `/v1/projects` и SQL к
`ykbtejjedefibdgyfgov` успешны. GET `/v1/organizations` возвращает пустой список,
GET известной организации и создание проекта — 403; создание ветки — 402,
требуется Pro. Эти операции больше не повторять: пользователь уже предоставил
отдельную БД **`https://jmsdxgylyjxwdwmdrmxw.supabase.co`**.
Но GET её проекта, ключей и SQL возвращают **403**. После обновления среды до
revision 3 доступ снова проверен: 403 сохраняется. Нужен токен аккаунта с
доступом именно к новому проекту; пользователь готовит его для следующего чата.
[Страница токенов Supabase](https://supabase.com/dashboard/account/tokens).

**Отдельный Vercel-проект создан**: `prodradar-test`, ID
`prj_3WEWtX8vujb0llpvmuA1Umovf623`, team
`team_OIdVeiXMtcQdNxXpseWNqQtV`. Создание проекта и запись env проверены реальными
POST. Сохранены `SUPABASE_URL` (новая БД), `TELEGRAM_BOT_TOKEN`, `ADMIN_CHAT_ID`,
`TELEGRAM_WEBHOOK_SECRET`, `REDIRECT_BASE_URL=prodradar-test.vercel.app` для
production/preview/development. Токен из сохранённого Vercel env повторно
проверен через `getMe`: **@ProdRadar_bot**. `SUPABASE_KEY` ещё отсутствует.
Deployments нет, Git integration не настроена; webhook не перенесён.
Webhook secret можно получить через Vercel GET отдельного env в память либо
сгенерировать заново и синхронно установить в Vercel и Telegram.
Исходный проект `prodradar`, его env, БД и webhook не изменены.

**Ручной тестовый сбор подготовлен**, `.github/workflows/collect_test.yml`
имеет только `workflow_dispatch`, без cron. `scripts/collect_test.py` до вызова
pipeline отвергает исходную БД, несоответствие ожидаемого URL, другого Telegram
бота и пользователей кроме ADMIN_CHAT_ID. На нынешних env остановился до записи
и сообщений: runtime/GitHub test environment ещё указывают на исходную БД.
Оригинальный `Collect Vacancies` не включался.

### Источники и браузерная диагностика

Работа идёт через **фирменные API**, HH не подменяет их. Прежние исправления
2ГИС (98/2, полная пагинация), Lamoda (10/5) и Контура (6/6) сохранены.
HH OAuth/captcha, неверные items, повторяющиеся id и неполный found дают ошибку.

- Aviasales: **30 raw / 2 product**, оба полных описания проверены.
  Удалён устаревший specializations-фильтр, теперь читается общий фирменный список.
- МТС Линк: **11 raw / 0 product**, публичные list/detail подтверждены HTTP и
  Chromium без Bearer. categoryId удалён, дата created учитывает реальный offset.
  `MTSLINK_BEARER_TOKEN` не нужен.
- ДомКлик: **31 raw / 8 product**, все восемь описаний проверены. Через Chromium
  найдены `/api/v1/vacancy/` (limit/offset) и `/api/v1/vacancy/detail/{slug}/`
  на career.domclick.ru. Поля title/vacancycontent.work_format/description;
  API достаточно Referer/Sec-Fetch, cookies не нужны в проверенных средах.
  HTML получает qrator_ssid2. Старый rabota-bff endpoint даёт 404.
- Альфа: **30 raw / 23 product**, все 23 описания проверены в Actions 36912345431.
- Точка: **1 raw / 1 product**, полное описание проверено в том же Actions.
- Т-Банк: Actions **36919821912** подтвердил **385/385 строк фирменного API**,
  234 после объединения городов, **25 product со всеми полными описаниями**.
  Во всех 25 карточках присутствуют Описание/Обязанности/Требования/Мы предлагаем.
  Семь 429 восстановлены bounded retry, 65 успешных HTTP запросов, issues=[];
  весь bank audit занял 627,8 секунды. Старый фильтр
  tcareer_it_profession=product-management и вложенная pagination.it устарели:
  API возвращал OK с пустым списком. DevTools выявил текущий POST getVacancies
  с filters.generatedGraphQL и плоской pagination. Runtime собирает IT/back-office
  без ограничения Москвой, проверяет уникальность/offset/totalCount; endpoint
  берётся из публичного environment.VACANCIES_PUBLIC_API. Для списка browser
  cookies или token не понадобились; все строки получены обычным HTTP POST.
  Полные описания, как и в прежнем main, читаются HTTP GET из HTML. Это допустимое
  дополнение API, не браузерная выгрузка. Только один job собирает Т-Банк;
  пауза HTML GET — 5 секунд, повторы 429 — 30/60 секунд с Retry-After.
  Audit enrichment timeout 150 секунд допускает эти повторы; parse — 360 секунд.

**Причина TLS банков подтверждена**, Actions
[36911140341](https://github.com/Zadnessa/prodradar/actions/runs/36911140341):
системные CA не проходят, официальная Russian Trusted Root/Sub CA проходит
для job.alfabank.ru/www.tbank.ru/hr.tochka.com с проверкой hostname.
`parsers/tls.py` расширяет доверие только запросов этих sources;
CERT_REQUIRED сохраняется. Происхождение/fingerprints/сроки —
`parsers/certificates/README.md`. В этой облачной среде upstream proxy сам
отвергает цепочку и даёт 503; локальный ответ не отменяет успешный Actions.

Dodo: текущий Nuxt config и JavaScript указывают backend
**https://job-site-backend.dodo-ai-platform.io** вместо старого career-api.dodoteam.ru.
Подтверждены GET `/api/v1/vacancies` (optional filter query),
`/api/v1/pages/vacancy/{id}` и `/api/v1/pages/vacancies`. В store этих запросов
Authorization не задаётся. Новый backend отвечает **503 nginx** в runtime и
Actions, включая служебный `/api/v1/available-pages`; запросы самого сайта в
Chromium тоже не проходят. Referer/Origin/Accept/Sec-Fetch не помогли. Старый
backend в runtime: upstream connection timeout. Это сбой доступа/сервера до
JSON-парсинга, а не доказательство необходимости токена; причина 503 не установлена.
Нельзя считать Dodo восстановленным после одной замены URL. Пользователь
сообщил о недоступности карьерного сайта и решил вернуться к источнику позже;
перед тестовым запуском повторять диагностику не требуется.

Купер: **наличие вакансий подтверждено, полнота фирменного API — нет**.
Общий старый API без group возвращает totalCount=1/pages=1: «Специалист
контактного центра в Купер (г. Орёл)»; detail возвращает полный текст,
status=PB/«Опубликована», archivedAt=null. Product group возвращает 0.
Для сверки HH employer **1272486** (site_url=www.kuper.ru) имеет **1308 вакансий**,
включая курьеров/водителей с публикацией 2026-10-01. Это другой охват найма,
не ожидаемое число вакансий офисного API. HH не подключён вместо фирменного API.
team.kuper.ru отвечает **403 с просьбой отключить VPN** в Chromium и Actions;
актуальный список/contract сайта в допускаемой сети пока не проверен.

`scripts/inspect_source_browser.py` сохраняет пути, имена query/header/cookies,
статусы, JSON-структуру и публичные filters/pagination каталога; значения
токенов/cookies не записываются. Для явно разрешённой пользователем диагностики
с явным `--probe-tbank-pagination` можно нажать последнюю «Показать ещё»
Т-Банка (первая раскрывает фильтры), чтобы снять один публичный POST. Обычный
workflow этого клика не делает. Формы отклика не используются. `--source-ca`
импортирует официальный root в NSS одноразового Actions runner и удаляет после
Chromium; вне Actions запрещён. Runtime browser stage остаётся общим в
`parsers/browser.py`, только для антибот-доступа.

Read-only Actions имеет independent `bank_contracts` без Chromium: только он
собирает Т-Банк. Общий audit исключает его через `--exclude-sources tbank`;
concurrency отменяет предыдущий audit ветки. Job `original` остаётся **без**
environment prodradar-test, чтобы не затенять repo Secrets исходного collector.
Локально **23 регрессии успешны**. Общий audit
[36919821912](https://github.com/Zadnessa/prodradar/actions/runs/36919821912)
(SHA 3888b4d) завершился: 21 ready, Dodo failed/503, Купер empty, но его полнота
не подтверждена. Банковский job **успешен**: Альфа/Точка/Т-Банк ready, все 23/1/25
product-описания проверены. Итого 22 уникальных ready, Dodo failed и Купер empty
с неподтверждённой полнотой. Общий workflow остаётся красным из-за Dodo. Запуск 36918527238 отменён при уточнении пользователя;
его отмена не означает ни успех, ни регрессию API.

Прямой gh download ZIP даёт 403, но GitHub connector
`github_download_workflow_artifact` + `download_file` успешно получает отчёты.
Приватный каталог `/workspace/prodradar-backups/diagnostics` содержит только
диагностику прямых firm sources; прежние эксперименты с HH fallback исключены.

### Точные следующие действия

1. В новом экземпляре первым делом проверить runtime status и реальные GET
   `/v1/projects`, `/v1/projects/jmsdxgylyjxwdwmdrmxw`, `/api-keys`, затем SQL
   `SELECT tablename FROM pg_tables WHERE schemaname='public'`, не печатая ключи.
   Один URL не подтверждает доступ или пустоту новой БД. Новых проектов не создавать.
2. Проверить наличие и SHA-256 архива; при отсутствии повторить REST/SQL backup
   исходного проекта. Использовать service_role (Management `/api-keys` либо
   память после Vercel GET исходного SUPABASE_KEY), не anon текущей среды.
3. В **пустом** новом проекте выполнить
   `python scripts/provision_test_database.py --project-ref jmsdxgylyjxwdwmdrmxw --schema-directory /workspace/prodradar-backups/sql-verified --data-directory /workspace/prodradar-backups/rest`.
   Проверить схему и 35/53 справочника, 0 пользователей/доставок/событий/вакансий.
   Скрипт проверяет hashes, identity и пустоту, выполняет одну SQL-транзакцию;
   существующий public он не перезаписывает. Облачное выполнение ещё не проверено.
4. Получить service_role новой БД, записать в отдельный Vercel `SUPABASE_KEY`.
   Обновить только GitHub environment `prodradar-test` URL/KEY; repo Secrets
   исходного collector не трогать. Если GitHub write снова даёт 403, выполнить
   ручной тестовый сбор локально с проверкой target и зафиксировать ограничение.
5. Только в новой тестовой БД временно отключить Dodo через companies.is_enabled
   (выбор по parser_name=dodo) и проверить отключение. Dodo отложен пользователем;
   наличие вакансий Купера подтверждено, полноту проверить позже. Т-Банк уже
   подтвердил все страницы и 25 описаний; массовые запросы перед запуском
   не повторять без необходимости. HH не подключать вместо фирменных источников.
6. Разместить код только в `prodradar-test`; проверить 403 без webhook secret,
   работоспособность новой БД и identity @ProdRadar_bot. Затем перенести только
   его webhook и redirect. Запустить защищённый ручной collector; cron не включать.
7. Пройти прежний флоу на реальном боте и сверить delivery: /start, полный
   онбординг и quick-path, настройки, выдача/«Ещё»/«Все»/«Хватит», mute/unmute,
   returning /start, просмотренные, pause/stop. Отправить пользователю короткий
   ручной чеклист. Этот реальный тест пока не выполнялся.

Первый проход **1–4 ещё не завершён**: облачная тестовая схема, размещение,
webhook и пользовательский флоу остаются. Подготовка позволяет продолжить
тестовый запуск после доступа к новой БД; Dodo отложен пользователем, полнота
Купера остаётся отдельной проверкой и не считается подтверждённой.

## Цель пользователя

- Сохранить существующий продукт, код, данные и возможность дальнейшего развития.
- Восстановить источники вакансий после длительного простоя, изучив историю PR,
  багов и решений в репозитории.
- Запустить тестового бота **@ProdRadar_bot** сначала на текущем флоу подбора.
- На той же технической базе сделать отдельного бота для **одного человека**,
  с подбором для **project manager**, сохранив бот для **product manager**.
- Для нового режима убрать онбординг, оставить действительно минимальные настройки
  и переходить к карточкам вакансий сразу после старта.
- Сохранить полные тексты вакансий для будущего рыночного ресерча.
- В новом боте сохранить блокировку компаний через `/mute`. Остальные функции
  разобрать по отдельности до изменения интерфейса.

Последнее уточнение пользователя заменяет прежний план на двух пользователей.
Основная роль нового бота — project manager. Bizdev упоминался ранее;
его включение в новую выдачу пока не решено, не добавлять его автоматически.

Существующий продукт работал на **другом боте**. В прежней задаче T-052 указан
`@ProductRadar_bot`, но актуальную принадлежность токенов и размещений ещё нужно
проверить; запись в бэклоге не подтверждает действующую конфигурацию.
Нельзя считать @ProdRadar_bot действующим продуктовым ботом или переносить на него
продуктовую конфигурацию без инвентаризации.

## Состояние подготовки на 1 октября 2026, до инвентаризации фазы 1

Это исторический снимок PR #127. Уточнения и исправления выводов находятся
в следующем разделе; особенно это касается нулевых счётчиков пользователей.

- Репозиторий: `Zadnessa/prodradar`, публичный. Исходный `main` на момент подготовки:
  `00b31624e696a7dca45bf381dd8e1d23697ab6f1` (последний прежний PR — #126).
- Рабочая ветка подготовки: `codex/prodradar-refresh`.
- [PR #127](https://github.com/Zadnessa/prodradar/pull/127) открыт как draft и
  не слит. Он содержит диагностику доступов и документацию; ремонт источников,
  новая фильтрация и новый интерфейс ещё не реализованы.
- Прежняя архитектура: webhook на Vercel, данные в Supabase, сборщик в
  GitHub Actions, интерфейс через Telegram Bot API.
- В текущем коде фильтруются продуктовые роли. В частности, project/bizdev
  встречаются в исключениях. Простая глобальная замена этих правил нарушит
  существующий продукт.
- Создано GitHub environment `prodradar-test`. В нём `SUPABASE_URL` и
  `ADMIN_CHAT_ID` размещены в Variables, ключи и токены — в Secrets.
  Диагностический workflow читает именно такое разделение. Дубли URL/ID в
  Secrets не используются и пока не удалялись.
- [GitHub-проверка](https://github.com/Zadnessa/prodradar/actions/runs/36895196282)
  прошла: SELECT таблиц Supabase, доступ к текстам, правильный Telegram-бот,
  админский чат и один запрос списка вакансий HH с HTTP 200.
- Доступная через настроенные реквизиты Supabase база содержит 638 вакансий,
  635 с непустым `description`, 0 пользователей и 0 записей доставки на момент
  проверок. Её адрес: `https://ykbtejjedefibdgyfgov.supabase.co`.
  Принадлежность этой базы существующему или будущему тестовому размещению
  ещё необходимо установить. Данные при диагностике не менялись.
- Токен, переданный в тестовую диагностику, принадлежит **@ProdRadar_bot**.
  Telegram сообщает зарегистрированный URL
  `https://prodradar.vercel.app/api/webhook`. Публичный обработчик отвечает 403
  на запрос без секрета. Это не подтверждает соответствие токена, обработчика
  и БД друг другу и не является проверкой пользовательского флоу.
- Старый workflow `Collect Vacancies` отключён GitHub из-за неактивности
  (`disabled_inactivity`). Диагностический запуск не включал его расписание.
- Текущее GitHub-подключение позволило отправить ветку, создать PR и прочитать
  Actions-логи. Перечисление Secrets/Variables через API возвращало 403;
  работоспособность значений проверили самим workflow.
- Пользователь сообщил о публикации `VERCEL_TOKEN` и `HH_ACCESS_TOKEN` в среде
  Codex. Последняя проверка прежнего запущенного экземпляра всё ещё показывала
  только исходные два секрета и два параметра. В следующем запуске проверить
  фактическую конфигурацию и API, не запрашивая новые токены заранее.
- Управление Vercel **не проверено**. Второе тестовое размещение не создано,
  webhook не перенастроен, текущий флоу на @ProdRadar_bot не запускался.

## Результат фазы 1: карта инфраструктуры

Проверено 1 октября 2026 около 20:25–20:30 по Москве. Инвентаризация доступных
связей выполнена; непроверенная конфигурация старого сборщика и недоступные
операции перечислены ниже. Изменялась только документация: webhook, расписания,
данные и конфигурация размещений не менялись, сообщения не отправлялись.
Фазы 2–7 не выполнялись.

### Подтверждённые связи

| Компонент | Существующее размещение | Подготовка теста |
| --- | --- | --- |
| Telegram | Токен из настроек Vercel принадлежит **@findproductjob_bot**, bot ID `8596074486` (`getMe`). Это установленная identity настроенного продуктового бота; принадлежность @ProductRadar_bot из T-052 не подтверждена. | Токен текущей среды принадлежит **@ProdRadar_bot**, bot ID `8634485730`. Identity также подтверждена логом диагностического Actions-запуска. |
| Webhook | `getWebhookInfo` у @findproductjob_bot возвращает `https://prodradar.vercel.app/api/webhook`. | **Тот же URL зарегистрирован у @ProdRadar_bot**. Это конфликт адресов, а не отдельное тестовое размещение. У обоих 0 pending updates, нет last_error_date на момент чтения. |
| Vercel | Проект `prodradar`, ID `prj_PxYCE2N7xbM3xOq2XPqX8KYCPvY0`, scope `zadnessas-projects`, account ID `team_OIdVeiXMtcQdNxXpseWNqQtV`. Git integration: `Zadnessa/prodradar`, production branch `main`. | Второй проект не найден: доступный список проектов содержит один элемент, следующей страницы нет. Это результат для доступного scope, не всех возможных аккаунтов. |
| Production deployment | `dpl_83b2b6GGhrwLU3nDU5PCJq1v2yhJ`, `READY`, SHA `00b31624e696a7dca45bf381dd8e1d23697ab6f1`, создан 25 апреля 2026; alias `prodradar.vercel.app`. | PR #127 имеет `READY` preview `dpl_Co8tUBou89yGV9dJ4Twna9Dyy3Ew`, SHA `91f7c29d8159409a4fb44f34a00a6299bde10153`. Preview принадлежит **тому же проекту**. |
| Vercel env | `TELEGRAM_BOT_TOKEN`, `SUPABASE_URL`, `SUPABASE_KEY`, `TELEGRAM_WEBHOOK_SECRET`, `REDIRECT_BASE_URL` заданы сразу для production, preview и development, без branch override. Изменения этих настроек предшествуют последнему production deployment; список env deployment содержит эти имена. | Preview наследует продуктовые настройки. Отдельных тестовых токена, ключа БД и webhook secret в Vercel не обнаружено. GitHub environment не переопределяет Vercel env. |
| Supabase | Vercel настроен на `https://ykbtejjedefibdgyfgov.supabase.co`; ключ из Vercel позволяет читать продуктовых пользователей и историю. | Текущая среда использует **тот же адрес БД**. Отдельной тестовой БД нет в обнаруженной конфигурации. Текущий ключ показывает другую видимость строк. |
| Redirect | `REDIRECT_BASE_URL=prodradar.vercel.app`; ссылки `/api/go` обращаются к БД Vercel и пишут `user_events`. | Наследование этого домена привело бы тестовые клики в продуктовую аналитику. Отдельный redirect-домен ещё не настроен. |
| Сборщик | `Collect Vacancies`, workflow ID `245897389`, `.github/workflows/collect.yml`, **disabled_inactivity**. Последний запуск: [28118534487](https://github.com/Zadnessa/prodradar/actions/runs/28118534487), 24 июня 2026, `main`, исходный SHA, `success`. | `Check Test Environment`, ID `372368844`, active; использует environment `prodradar-test`, только диагностика. [Запуск 36895196282](https://github.com/Zadnessa/prodradar/actions/runs/36895196282) выполнен из `codex/prodradar-refresh`, SHA `e324fa19337f9907fade3fad2bfd63f5d43a8187`. Тестовый сборщик не создан. |

Регистрация одинакового URL не подтверждает, что тестовый бот успешно доставляет
updates в обработчик: соответствие его webhook secret не проверялось. Запрос
`POST {}` без secret вернул 403. Аутентифицированные updates и пользовательский
флоу не запускались. В коде обработчик выбирает исходящий токен из окружения,
а не из identity входящего бота; при принятии тестового update на существующем
размещении он использовал бы продуктовые токен и БД.

### Проверки доступов и видимость данных

`scripts/check_environment.py --require-hh --require-vercel` выполнен без изменений
из точного SHA PR #127 `91f7c29…` в текущей облачной среде, exit code **0**.
Подтверждены SELECT таблиц Supabase и описаний, Telegram `getMe`,
`getWebhookInfo`, доступ к админскому чату через `getChat`, список вакансий HH
(HTTP 200) и чтение Vercel-проекта (HTTP 200). Токены не выводились и не сохранялись
в отчётах. Получение/обновление HH-токена и полный прогон HH-парсеров не проверялись.

Runtime status текущего экземпляра перечисляет пять секретов (`SUPABASE_KEY`,
`TELEGRAM_BOT_TOKEN`, `VERCEL_TOKEN`, `HH_ACCESS_TOKEN`, `HH_CLIENT_SECRET`) и три
параметра (`SUPABASE_URL`, `ADMIN_CHAT_ID`, `HH_CLIENT_ID`). Состояния readiness
имеют значение `unknown`; работоспособность использованных интеграций установлена
реальными API-запросами, а не этим флагом. Сетевая политика файла — unrestricted,
VPN не настроен; использовались штатные proxy и TLS-проверка.

**Нулевые SELECT не означали пустую БД.** Два ключа для одного адреса дают такую
видимость; точная роль ключей и причина ограничения (включая RLS) не установлены:

| Таблица / выборка | Ключ текущей среды | Ключ из Vercel |
| --- | ---: | ---: |
| `vacancies` | 638 | 638 |
| Непустые `description` | 635 | 635 |
| `users` | 0 | **65** |
| `user_vacancy_delivery` | 0 | **15 323** |
| `user_events` | 0 | **140 305** |
| `companies` | 35 | 35 |
| `city_mappings` | 53 | 53 |

С ключом Vercel также видны 257 активных вакансий и 34 включённые строки компаний
(это не число уникальных парсеров). PostgREST schema endpoint отвечает 200 и
перечисляет шесть таблиц выше. Это подтверждение доступа к данным через REST,
**не резервная копия** схемы PostgreSQL, RLS, индексов, триггеров или всей БД.
Экспорт данных в этой фазе не выполнялся.

Vercel API разрешил GET проекта, списка проектов, доменов, deployments,
metadata env и отдельных значений env. Список env возвращает зашифрованные
значения; identities и адреса сопоставлены через отдельные GET env, значения
секретов использовались только в памяти. Права создания проектов, записи env,
deploy/promote/rollback **не проверены**: успешный GET не доказывает право записи.

### История и ограничения текущего кода

Изучены `AGENTS.md`, README, context, bugs, backlog, материалы PR #127,
история merge-коммитов и существенные PR; выводы сверены с текущим кодом:

- [#87](https://github.com/Zadnessa/prodradar/pull/87), #90, #92, #107: mute/unmute,
  идентификаторы `slug`, статусы announced/delivered и сохранение истории при reset.
- [#97](https://github.com/Zadnessa/prodradar/pull/97), #100, #104: аналитика через
  redirect, стратегия ошибок webhook, upsert и устойчивость pipeline.
- [#124](https://github.com/Zadnessa/prodradar/pull/124),
  [#125](https://github.com/Zadnessa/prodradar/pull/125),
  [#126](https://github.com/Zadnessa/prodradar/pull/126): OAuth HH, исключение
  незавершённого онбординга из scheduled delivery, остановка доставки при 403/429
  и формат admin report.

`config.BOTS` содержит только `main`; `/start` сохраняет `bot_id="main"`,
сборщик выбирает пользователей `main`. Название `TEST_MODE` не создаёт изоляцию
токенов или БД. Product-фильтрация общая (`config.py`, `delivery/ranking.py`,
`main.py`); точные whitelist-совпадения проходят до blacklist. Поэтому будущий
project-профиль нельзя реализовать только заменой одного blacklist.
`main.py` одновременно сохраняет вакансии, деактивирует снятые и отправляет
рассылку/admin report — его не запускали для диагностики. Полные описания
сохраняются, `source_json` исключён из пользовательских SELECT.

### Что остаётся недоступным или непроверенным

1. **Фактические identities старого сборщика.** `collect.yml` читает Secrets
   репозитория, без `environment: prodradar-test`; тестовый workflow читает свой
   environment. Перечисление Secrets/Variables репозитория и `prodradar-test`
   через текущую GitHub integration возвращает **403 Resource not accessible by
   integration**. Значения GitHub Secrets не возвращаются API даже при праве
   перечисления. Логи последнего старого сборщика возвращают **HTTP 410**;
   его `success` не доказывает соответствие реквизитов Vercel и Codex.
   Недостающая проверка — отдельный read-only Actions job с Secrets репозитория,
   выводящий только `getMe`, webhook URL, адрес Supabase и безопасные счётчики;
   не запускать для этого `main.py` и не включать расписание.
2. **Сохранение и создание Supabase.** Management API token / подключение
   PostgreSQL и права управления проектами не предоставлены в текущей
   конфигурации. REST-чтение продуктовых данных возможно с ключом Vercel;
   создание отдельного проекта и полный экспорт схемы/RLS/индексов/триггеров
   требуют доступа к Supabase management/dashboard либо PostgreSQL. Не считать
   ограниченный ключ Codex достаточным для резервирования пользователей.
3. **Создание и конфигурация тестового Vercel.** Чтение подтверждено, запись и
   пределы Vercel-токена ещё неизвестны. Проверить конкретные операции создания
   второго проекта и записи его env при выполнении фазы 2.
4. **Пользовательский флоу и восстановление источников.** Не проверены
   аутентифицированный webhook, реальные команды/callbacks, доставка и все
   парсеры; это работы фаз 2–4, не результат этой инвентаризации.

### Конкретный план изоляции для фазы 2

1. Зафиксировать исходный SHA `00b31624…` и текущий production deployment
   `dpl_83b2b6GGhrwLU3nDU5PCJq1v2yhJ`; подготовить инструкции восстановления
   исходных настроек и размещения. Сохранить исходные токены/secret в защищённом
   хранилище, не в Git или текстовом отчёте.
2. До любых записей выгрузить все шесть доступных таблиц с ключом, который
   действительно видит 65 пользователей и 15 323 delivery-записи; сохранить
   тексты вакансий. Отдельно получить схему, RLS, индексы и триггеры; проверить
   восстановление в отдельной БД. Счётчики выше — ориентиры снимка, не ожидаемые
   вечные значения.
3. Создать отдельный Supabase-проект для теста. Перенести схему, справочники и
   при необходимости копию вакансий; `users`, delivery и events теста начать
   отдельно. Общий project и ограничение видимости ключом не считать изоляцией.
4. Создать второй Vercel-проект, например `prodradar-test`, на тот же репозиторий
   и исходный флоу. Задать только тестовые `TELEGRAM_BOT_TOKEN` (@ProdRadar_bot),
   `SUPABASE_URL/KEY`, новый `TELEGRAM_WEBHOOK_SECRET` и собственный
   `REDIRECT_BASE_URL`. Preview этого проекта также должен использовать тестовые
   реквизиты. Настройки существующего `prodradar` сохранить.
5. Обновить `prodradar-test` в GitHub на отдельную тестовую БД, сохранив разделение
   Variables/Secrets. Для тестового сбора создать отдельный ручной workflow с
   этим environment; старый collector оставить отключённым, repo Secrets не
   заменять тестовыми. До запуска проверить identity каждого набора реквизитов.
6. Только после подтверждения раздельных доменов, токенов, БД и запусков
   перенести webhook **@ProdRadar_bot** на новый домен с новым secret, проверить
   аутентифицированный пустой запрос и повторно прочитать webhook обоих ботов.
   @findproductjob_bot должен сохранить прежний webhook; реальные карточки и
   пользовательские сценарии проверить в фазе 4.

## Предварительные наблюдения об источниках

До появления рабочего HH-токена провели read-only проверку 24 включённых
парсеров в прежней облачной среде. Это предварительная диагностика, не перечень
починенных API:

- Данные вернули Яндекс, Ozon, Сбер, Wildberries, Avito, Контур, Lamoda и X5.
- Пустые результаты вернули Авиасейлс, ДомКлик, Купер, МТС Линк и четыре
  HH-парсера. После настройки HH отдельный запрос HeadHunter прошёл в Actions;
  полный прогон всех четырёх HH-парсеров с токеном ещё не выполнен.
- Старая страница 2ГИС `/project/` дала 404; главная страница доступна и ссылается
  на `/vacancies`. Новый контракт пока не исследован.
- У Т-Банка, Альфы и Точки прокси вернул ошибки проверки TLS-сертификата;
  у VK — ошибку прокси; у МТС и Dodo — ошибки upstream. Не считать это
  доказательством поломки API. Проверять транспорт и целевое окружение отдельно,
  не отключая TLS-проверку и не обходя ограничения сети.
- Для СберЗдоровья не получен актуальный buildId, в том числе при отдельной
  браузерной проверке. Установка Chromium и локальный браузерный smoke прошли,
  но получение данных защищённого сайта не подтверждено.
- У Lamoda обнаружено служебное `_raw_id` в результатах `parse()`, у Контура
  заголовки включали дополнительный текст карточки. Это кандидаты на проверку
  контрактов, а не выполненные исправления.

Локальные временные отчёты прежней среды не являются переносимым источником
контекста. Повторять нужные проверки в предназначенном для сборщика окружении.

## Фазы и условия перехода

| Фаза | Работа | Когда завершена |
| --- | --- | --- |
| 1. Доступы, история и карта инфраструктуры | Изучить AGENTS, docs, существенные PR и текущий код. Проверить реквизиты нового запуска. Установить, какой бот, Vercel-проект, БД и workflow обслуживают существующий продукт, а какие относятся к тесту. | Зафиксирована карта существующего и тестового окружений с подтверждёнными связями; Vercel, Supabase, Telegram и HH проверены; оставшиеся недоступные операции перечислены явно. |
| 2. Сохранение и тестовое окружение | Зафиксировать исходную версию, подготовить доступные резервные выгрузки и восстановление, создать изолированное размещение для @ProdRadar_bot на исходном флоу. Настроить его реквизиты и webhook. | Есть подтверждённая изоляция токена, данных и запусков; задокументировано восстановление; обработчик принимает аутентифицированный запрос. |
| 3. Восстановление текущих API | Проверить все включённые источники, пагинацию, enrichment и контракты. Исправить воспроизводимые ошибки, сохраняя прежнюю продуктовую фильтрацию. | Есть отчёт по каждому источнику и проверенные исправления. Блокирующие ошибки не скрыты за пустой выдачей или успешным статусом всего workflow. |
| 4. Тест текущего флоу на @ProdRadar_bot | Выполнить сбор и пройти существующий сценарий: /start, текущий онбординг, настройки, карточки, следующая пачка, история доставки и уведомления. | Реальные карточки получены в тестовом боте, callbacks работают, данные и история записываются в тестовую БД; пользователь проверил результат. |
| 5. Разбор функций нового бота | Составить полный перечень реализованных функций и зависимостей. Для каждой согласовать: оставить, упростить или скрыть в новом боте. `/mute` остаётся; онбординг убирается; необходимость остальных элементов проверяется отдельно. | Пользователь рассмотрел таблицу решений; зафиксирован короткий сценарий нового бота и перечень нужных настроек. Существующий бот сохраняет все свои функции. |
| 6. Подбор для project manager | Исследовать реальные категории каждого API, добавить отдельный профиль сбора и систему исключений по образцу существующей. Сохранить исходный продуктовый профиль. | Есть выборка реальных вакансий и проверенные включения и исключения; новый профиль работает в тестовом окружении, исходная продуктовая выдача сохраняется. |
| 7. Минимальный интерфейс для одного человека | Подключить согласованного пользователя и реализовать решения фазы 5: старт без онбординга, сразу карточки, `/mute` и необходимые действия. | Пользователь прошёл новый сценарий; mute и возврат компании в выдачу, доставка и нужные настройки проверены; исходный продуктовый флоу работает без изменений поведения. |

Инвентаризация **фазы 1** выполнена в пределах доступных API; карта и точные
ограничения приведены выше. Реквизиты старого collector ещё не сопоставлены,
поэтому вся цепочка сборщик → БД → бот не считается полностью подтверждённой.
Диагностика не разрешает считать готовыми следующие фазы.
Изменения фильтрации и интерфейса начинаются после фактического теста в фазе 4.

## Сохранение исходного флоу

Общий репозиторий и техническая база не означают общий пользовательский сценарий.
Новый профиль роли и новый интерфейс выбираются конфигурацией отдельного
размещения; конкретный механизм определить после инвентаризации архитектуры.
Не заменять глобальные правила продуктового отбора проектными и не удалять
старые обработчики онбординга и настроек ради минимального интерфейса нового бота.
Данные и история доставки ботов должны быть изолированы. Общие исправления API
проверять на сохранение исходных контрактов и продуктового подбора.
После изменений нового бота повторить проверку исходного сценария.

## Начальная таблица функций для фазы 5

Это исходные требования и предложения для ревизии, не разрешение удалить код.
Все решения ниже относятся только к новому боту.

| Функция | Решение сейчас |
| --- | --- |
| Карточки и ссылки на вакансии | Оставить, показывать сразу после старта. |
| `/mute` / существующие `/mute_{slug}` | Оставить блокировку компаний; формат команды определить по текущей реализации. |
| Разблокировка компаний | Предусмотреть простой способ отменить mute; конкретный интерфейс решить при ревизии. |
| Онбординг | Убрать из нового сценария. |
| Большие меню пользовательских фильтров | Кандидат на скрытие; необходимые предпочтения одного пользователя можно задать конфигурацией. |
| Отбор по роли и исключения нерелевантных вакансий | Оставить внутри системы: отсутствие меню фильтров не означает выдачу всех ролей. |
| Пагинация и остановка текущей выдачи | Разобрать необходимость и минимальные действия на реальных карточках. |
| Рассылка, пауза, `/stop` | Решить отдельно: ручная выдача, уведомления и их остановка. |
| Returning-user hub, клавиатура, `/settings`, `/blocked`, статистика | Проверить по коду и решить для каждой функции, что оставить, упростить или скрыть. |
| История доставки, защита webhook, диагностика ошибок, тексты вакансий | Сохранить технические механизмы; изменения видимых экранов не должны их ломать. |

Полный перечень собрать из обработчиков, callback-префиксов, рассылки и истории
PR; эта таблица не заменяет аудит функций.

## Исходное поручение на фазу 1 (выполненные проверки см. выше)

1. Прочитать этот документ, `AGENTS.md`, `docs/context.md`, `docs/bugs.md`,
   `docs/backlog.md`, `README.md` и материалы PR #127. Учесть, что PR — подготовка,
   а существующий продукт работал на другом боте.
2. Проверить конфигурацию именно текущей облачной среды инструментом
   environment status; соблюдать runtime skill, сетевую политику и привязки
   секретов. Значения секретов не выводить.
3. Запустить `scripts/check_environment.py --require-hh --require-vercel`
   из ветки PR #127 с реквизитами среды. Проверка выполняет только чтение.
4. Изучить конфигурацию существующих Vercel-размещений, веток, ботов, Supabase
   и GitHub workflows. Сопоставить реальные identities и адреса, а не только
   имена переменных. Не выдавать архивную запись webhook за работающий тест.
5. Дополнить этот документ картой инфраструктуры, подтверждёнными доступами,
   неизвестными вещами и конкретным планом изоляции для фазы 2. Если возможности
   API или привязки секретов недостаточны, назвать точную недостающую операцию.

В этой фазе не перенастраивать webhook, не включать рассылку или cron,
не менять пользовательские данные, роли и интерфейс. Не создавать новый бот
или новую БД до понимания существующих связей. Не переходить к следующим фазам
без отдельного поручения пользователя.

## Что пока неизвестно

- Фактические identities Secrets старого GitHub collector; Vercel, настроенный
  @findproductjob_bot и продуктовая Supabase сопоставлены, collector — ещё нет.
- Права записи Vercel-токена; доступы чтения подтверждены в текущем запуске.
- Причина различной видимости строк у ключей Supabase и доступ к полной схеме
  PostgreSQL/управлению проектами для резервирования и создания тестовой БД.
- Полный статус источников на актуальных реквизитах и в целевом runtime.
- Telegram ID единственного пользователя нового бота и его предпочтения.
- Включать ли bizdev, ранее названный пользователем, в профиль project manager.
- Конкретные исключения project manager, перечень функций и минимальные
  настройки. Решения принимать на фазах 5–7 по данным и тесту.
