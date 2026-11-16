# Переходы к материалам Альфа-Курса

Текущая объединённая версия и заново выполненные проверки: [STATUS](STATUS.md), [интеграция](integration-2026-11-16.md). Раздел с портом3082 и168 тестами ниже — протокол автора PR #3 в его окружении, а не перечень работающих контейнеров этого клона.

16.11.2026. Основной конкурсный сценарий — FULL с каталогом из выгрузки по ссылке на странице 14 ТЗ. DEMO содержит только авторские примеры и прямо обозначен в интерфейсе. Эксперимент PUBLIC удалён: внешние источники не заменяют материалы Альфа-Курса.

Кнопка «Открыть на Альфа-Курсе» — обычная HTTPS-ссылка в новой вкладке с noopener/noreferrer. «Подробнее» показывает краткое описание. Платные материалы и подписка обозначены до перехода; тела платных уроков не копируются. Неизвестный URL не заменяется главной страницей, поиском или придуманным адресом: показывается пояснение.

Сервер принимает у organizer только адреса kurs.alfabank.ru без учётных данных и нестандартных портов. Импорт использует абсолютную ссылку источника, локально извлечённую каноническую ссылку либо исходный slug в подтверждённом маршруте. NULL/undefined и неизвестные типы не превращаются в URL.

## Подтверждение маршрутов

Публичные страницы найдены в поисковом индексе 16.11.2026. Это подтверждение структуры адресов, а не успешного HTTP-открытия каждой строки выгрузки:

- articles: https://kurs.alfabank.ru/articles/kak-vyjti-iz-kassovogo-razryva-sovety-na-primere-biznesa-v-horeca/
- courses: https://kurs.alfabank.ru/courses/kak-upravlyat-finansami/
- documents: https://kurs.alfabank.ru/documents/reshenie-ob-odobrenii-krupnoj-sdelki/
- webinars: https://kurs.alfabank.ru/webinars/zakon-o-platformennoj-ehkonomike-novye-pravila-marketplejsov/
- podcasts: https://kurs.alfabank.ru/podcasts/kassovyj-razryv-ne-prigovor-kak-upravlyat-finansami-biznesa/
- vocabulary: https://kurs.alfabank.ru/vocabulary/chistaya-pribyl/
- calculators: https://kurs.alfabank.ru/calculators/zarplata/

На машине проверки HTTPS-запрос к платформе завершился UntrustedRoot. Проверку сертификатов не отключаем. Работоспособность приложения и доступность внешней платформы — отдельные проверки; авторизацию/покупку пользователь выполняет на платформе.

## Импорт

Из корня проекта, после восстановления базы по README:

```powershell
.venv/Scripts/python.exe scripts/import_catalog.py --container hac-audit-20261116-links
.venv/Scripts/python.exe scripts/extract_source_links.py --container hac-audit-20261116-links
.venv/Scripts/python.exe scripts/import_catalog.py --container hac-audit-20261116-links
$env:WEB_PORT='3082'
docker compose -p hac-public-materials -f compose.yaml -f compose.full.yaml up -d --build
```

Первый импорт определяет бесплатные статьи/документы по данным каталога; затем извлекаются только их канонические ссылки, без сохранения тел. IsPublic не используется как признак бесплатности. Выгрузка и производный каталог остаются в .private и исключены из образов/Git.

## Результат проверки 16.11.2026

- На http://127.0.0.1:3082 работает FULL, 1476 материалов, версия каталога e4dc26acca5e0e25. Исходный дамп получен по ссылке со страницы 14 ТЗ; хранится только в .private.
- 168 серверных тестов passed, 1 опциональная E5-проверка skipped; Ruff, TypeScript и production Docker build прошли.
- 46 desktop/mobile E2E passed на отдельном DEMO 3090. Новые frontend/tests/source-links.spec.ts проверяют семь форматов, новую вкладку, платный доступ, отсутствие URL и возврат фокуса. Внешние ответы в этих тестах подменены авторскими fixtures — это не HTTP-аудит платформы.
- 8 FULL smoke-проверок прошли; прогресс отдельной сессии сохранился после перезапуска PostgreSQL/API. Приватные файлы исключены из Git и Docker-контекста; check_public_files прошёл.
- Реальное открытие публичной страницы курса во встроенном браузере завершилось ERR_CERT_AUTHORITY_INVALID. Проверка сертификатов не отключалась. Нельзя утверждать, что все 1476 страниц доступны: подтверждены структура адресов и переходы приложения.
- Основные файлы: backend/app/models.py, scripts/import_catalog.py, scripts/extract_source_links.py, frontend/app/page.tsx, frontend/app/globals.css; документация docs/material-links.md. PUBLIC удалён. Публикация и изменение тегов не выполнялись.

