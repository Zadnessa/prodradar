# Автосбор только для тестового ProdRadar

Пользователь разрешил регулярный свежий сбор со следующего дня: первый
scheduled запуск3 октября2026 в10:00 Москва, затем ежедневно10:00/19:00.
GitHub UTC cron:07:00/16:00. Файл schedule_test.yml живёт в default main;
код сборщика берётся из codex/restore-test-bot, environment только prodradar-test.
PR129 и исходный product бот не объединяются и не включаются этим workflow.
GitHub может поставить запуск в очередь; время — начало прогона, а карточки
приходят после проверки и сбора. До3 октября07:00 UTC scheduled сбор пропускается.

Каждый прогон заново получает каталоги API/HTML, обновляет source_pool и core
project_bizdev, затем доставляет непросмотренное после завершения онбординга.
Грейд, mute, пауза и delivered history сохраняются. Это не cached повтор старого
пула. Ошибка отдельного источника отражается в отчёте; остальные источники
обрабатываются. Купер403 может оставить весь workflow failure, несмотря на
успешное обновление остальных источников и доставку. Старый product workflow
collect.yml остаётся disabled_inactivity. Vercel cron не используется.

Ручной запуск schedule_test.yml с collect_test=false — диагностика без
изменения вакансий и без доставки; true — явный сбор сейчас. Scheduled запускает
сбор автоматически. Используются TEST_* и identity guards, без исходного token.
Concurrency совпадает с ручным test collector, одновременные записи исключены.
Раннеры GitHub работают независимо от компьютера пользователя и среды Codex.

Публичные GitHub cron отключаются после60 дней отсутствия активности репозитория.
Отдельный keepalive job раз в30 дней без main-коммитов обновляет только
.github/test-schedule-heartbeat. Только у него contents:write, у сборщика — read,
у keepalive нет test secrets. Изменения только .github/docs/README/AGENTS
пропускаются Ignored Build Step исходного Vercel проекта, не собирают runtime
и не увеличивают Function Storage. Изменения runtime продолжают собираться.

Не удалять codex/restore-test-bot, пока расписание использует эту ветку. После
объединения полноценного test кода в main поменять checkout ref отдельно.
Отключение: GitHub Actions → Scheduled Test Vacancies → Disable workflow.
