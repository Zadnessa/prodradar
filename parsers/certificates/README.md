# Цепочка TLS фирменных источников

`russian_trusted_ca.pem` содержит публичные сертификаты из официальных файлов:

- https://gu-st.ru/content/lending/russian_trusted_root_ca_pem.crt
- https://gu-st.ru/content/lending/russian_trusted_sub_ca_pem.crt

Получены 1 октября 2026 через HTTPS с системной проверкой сертификата.
SHA-256 DER fingerprint корневого сертификата:
`D26D2D0231B7C39F92CC738512BA54103519E4405D68B5BD703E9788CA8ECF31`;
промежуточного:
`BBBDE2103E790B999EC62BD03CF625A5A2E7C316E10AFE6A490EEDEAD8B3FD9B`.
Промежуточный подписан корневым (`openssl verify`), действует до 6 марта 2027;
корневой — до 27 февраля 2032. Обновление цепочки требует повторной проверки
официального происхождения, подписей и fingerprints.

`parsers/tls.py` добавляет эту цепочку к системным CA только для запросов
`job.alfabank.ru`, `www.tbank.ru`, `hr.tochka.com`. Проверки hostname и
`CERT_REQUIRED` сохраняются. Глобальное хранилище доверия не меняется.
Диагностический `scripts/check_source_tls.py` сравнивает системную и расширенную
цепочки в GitHub Actions; из облачного runtime с обязательным HTTP proxy его
не запускать. Actions 36911140341 подтвердил: системная цепочка не проходит,
расширенная проходит для всех трёх банков вместе с проверкой hostname.
Альфа/Точка получают API 200, Т-Банк получает 200 с пустым списком старого фильтра.

Для Chromium `inspect_source_browser.py --source-ca` временно импортирует root
в пользовательский NSS одноразового GitHub runner и удаляет его после браузера.
Опция запрещена вне Actions; системное хранилище и runtime browser не меняются.
`ignore_https_errors` и отключение TLS не используются.
