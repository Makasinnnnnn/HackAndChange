# Альфа-Маршрут 1.2.4 — полная инструкция для жюри

Hack&Change 2026, Альфа-Банк, трек 1. Рекомендации образовательных материалов для предпринимателей. Конкурсный прототип, не официальный сервис банка.

Код: <https://github.com/Makasinnnnnn/HackAndChange>. Проверенный runtime-релиз: `v1.2.4`, коммит `b0d9e1ec73c3483ec4b512dc4189632ab9644e20`. Комплект `alfa-route-1.2.4-jury.zip` содержит тот же код и дополнительную документацию для запуска; опубликованный тег не заменяется. Презентация: [PDF](output/presentation/alfa-route-1.2.pdf), [редактируемый PPTX](output/presentation/alfa-route-1.2.pptx). Внутри презентации указана версия 1.2.4, имя файла содержит minor-версию.

## 1. Какой вариант запускать

| Вариант | Данные | Поиск | AI-кнопка | Что подготовить |
|---|---|---|---|---|
| Быстрая проверка | DEMO, 36 авторских примеров | Локальные TF-IDF и правила | Выключена | Docker Desktop |
| DEMO + E5 + Qwen | Те же авторские примеры | TF-IDF + локальная E5 | Локальный Qwen | Docker, веса E5, Qwen и llama.cpp |
| FULL | Каталог организаторов, 1476 материалов в проверенном импорте | TF-IDF, опционально E5 | Опционально Qwen | Собственный доступ к дампу и локальный импорт |
| FULL + E5 + Qwen | Каталог организаторов | TF-IDF + E5 | Локальный Qwen | Все шаги ниже |

Для начала достаточно раздела 3. Затем включите E5 по разделу 4 и Qwen по разделу 5. Если у вас есть выданная организаторами выгрузка, выполните раздел 6 и запустите полный режим из раздела 7.

**E5 и Qwen выполняют разные задачи.** E5 добавляет нейросетевой сигнал в поиск. Qwen отдельно предлагает формулировку и уточняющий вопрос; пользователь подтверждает применение. Материалы выбирает каталоговый алгоритм, не генеративная модель. Основной сценарий работает без внешнего AI API и ключей.

## 2. Требования и подготовка

Основной проверенный вариант: Windows x64, Docker Desktop с Linux containers, Compose v2+, PowerShell. Обычный Docker-сценарий также проверен в Linux CI. Native-запуск Qwen ниже рассчитан на Windows x64; GPU не требуется.

Для Docker-запуска приложения, загрузки E5 и Windows-варианта Qwen отдельные Python/Node на хосте не нужны. **Python 3.13 нужен только для FULL-импорта и native-тестов. Node.js 24 — только для native-проверок frontend.**

Сеть нужна для первой сборки из Docker/npm/PyPI, загрузки публичных моделей с Hugging Face и llama.cpp с GitHub. Qwen GGUF занимает 1 117 320 736 байт, runtime ZIP — около 16 МБ; E5 и Docker-образы требуют дополнительного места. Оставьте несколько ГБ свободного диска и запас RAM для Docker и модели. Время первой сборки зависит от сети и CPU, обещания фиксированных «30 секунд» нет.

1. Распакуйте ZIP в обычную локальную папку. В её корне должны находиться `compose.yaml`, `README.md`, `backend/`, `frontend/` и этот файл.
2. Откройте PowerShell в этой папке. Все команды ниже выполняются из корня, без перехода в `backend` или `frontend`.
3. Запустите Docker Desktop, дождитесь готовности Linux engine.

```powershell
docker version
docker compose version
docker info --format '{{.OSType}}'
```

Последняя команда должна вывести `linux`. Если сервер Docker недоступен, сначала запустите Docker Desktop. Глобально изменять ExecutionPolicy или настройки TLS не требуется.

Для отдельного экземпляра жюри в этом окне PowerShell задайте имя проекта:

```powershell
$env:COMPOSE_PROJECT_NAME='alfa-jury'
```

Оно применяется ко всем последующим командам Compose в этом окне. В новом окне задайте его снова либо добавьте `COMPOSE_PROJECT_NAME=alfa-jury` в свой `.env`. Это имя задаёт отдельный том прогресса. Не запускайте разные копии с одним именем проекта одновременно.

## 3. Быстрая проверка без моделей и дампа

```powershell
docker compose up -d --build --wait --wait-timeout 240
docker compose ps
Invoke-RestMethod http://127.0.0.1:3080/api/health
Invoke-RestMethod http://127.0.0.1:3080/api/ready
```

Открыть **<http://127.0.0.1:3080>**. API-документация: <http://127.0.0.1:3080/api/docs>.

Ожидается: все три сервиса `db`, `api`, `web` healthy; health `version=1.2.4`; ready `status=ready`, `catalog_mode=demo`, `materials=36`. Хеш каталога выводится фактически, вручную его вводить не нужно.

DEMO — авторские синтетические примеры для воспроизводимого запуска. У них нет выдуманных внешних страниц. Кнопка «Открыть пример» показывает авторскую карточку внутри приложения. Это не замена каталога организаторов для проверки качества на реальных данных.

По умолчанию модель E5 не подключена: `/api/bootstrap` возвращает `semantic_model=null`, `semantic_fallback=true`; без `compose.llm.yaml` — `llm_enabled=false`. Это штатный лексический режим.

Если порт 3080 занят, перед запуском установите свободный порт и используйте его во всех адресах инструкции:

```powershell
$env:WEB_PORT='3090'
docker compose up -d --build --wait --wait-timeout 240
```

Тогда открыть <http://127.0.0.1:3090>. Переменная окружения PowerShell имеет приоритет над `.env`.

## 4. Включение локальной E5

Из корня, один раз при доступной сети:

```powershell
New-Item -ItemType Directory -Force .private/models/e5 | Out-Null
docker compose -f compose.yaml -f compose.semantic.yaml --profile models run --rm model-download
```

Дождитесь кода завершения 0. Скрипт скачивает `Xenova/multilingual-e5-small` на закреплённой ревизии `761b726dd34fb83930e26aab4e9ac3899aa1fa78`. В `.private/models/e5/` должны появиться:

```text
config.json
tokenizer.json
tokenizer_config.json
onnx/model_quantized.onnx
manifest.json
```

Manifest содержит ревизию и SHA-256 файлов. Модель не входит в архив; это отдельная загрузка публичных весов, каталог организаторов никуда не отправляется.

Запустить DEMO с E5:

```powershell
docker compose -f compose.yaml -f compose.semantic.yaml up -d --build --wait --wait-timeout 600
Invoke-RestMethod http://127.0.0.1:3080/api/bootstrap | Select-Object catalog_mode,catalog_count,semantic_model,semantic_fallback,llm_enabled
```

Ожидается `semantic_model=Xenova/multilingual-e5-small`, `semantic_fallback=false`. Первый старт семантического API может потребовать прогрева. Одна папка без файлов модели не подтверждает готовность.

Если загрузка не завершилась, сначала восстановите её либо вернитесь к базовой команде из раздела 3. При отсутствии папки bind mount может не дать контейнеру запуститься; при недоступном энкодере приложение может перейти в lexical fallback. Факт включения проверяйте через bootstrap, а не по названию Compose-файла.

## 5. Локальный Qwen на Windows — проверенный вариант

Используется Qwen2.5-1.5B-Instruct GGUF Q4_K_M, llama.cpp b7200, CPU. Модель работает отдельным процессом Windows на `127.0.0.1:18080`; Docker API обращается к нему через `host.docker.internal`. API-ключ не нужен.

### 5.1. Скачать точные файлы

Создать каталоги:

```powershell
New-Item -ItemType Directory -Force .private/models/qwen,.private/tools | Out-Null
```

**Модель, публичная закреплённая ревизия:**

```powershell
curl.exe --fail --location --retry 3 --connect-timeout 20 --max-time 1800 --output .private/models/qwen/qwen2.5-1.5b-instruct-q4_k_m.gguf 'https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/91cad51170dc346986eccefdc2dd33a9da36ead9/qwen2.5-1.5b-instruct-q4_k_m.gguf?download=true'
if ($LASTEXITCODE -ne 0) { throw 'Qwen download failed; do not start a partial model' }
```

Если нужный файл уже есть и его хеш совпадает со следующим разделом, повторная загрузка не требуется. Альтернатива при уже установленном современном `hf` CLI:

```powershell
hf download Qwen/Qwen2.5-1.5B-Instruct-GGUF qwen2.5-1.5b-instruct-q4_k_m.gguf --revision 91cad51170dc346986eccefdc2dd33a9da36ead9 --local-dir .private/models/qwen
```

Выберите один способ загрузки. Установка HF CLI не является обязательным условием Windows-запуска через `curl.exe`.

**Runtime для Windows x64 CPU:**

```powershell
curl.exe --fail --location --retry 3 --connect-timeout 20 --max-time 300 --output .private/tools/llama-b7200.zip 'https://github.com/ggml-org/llama.cpp/releases/download/b7200/llama-b7200-bin-win-cpu-x64.zip'
if ($LASTEXITCODE -ne 0) { throw 'llama.cpp download failed' }
```

ZIP пока не нужно распаковывать вручную: это делает `scripts/start_local_llm.ps1`. Имя `llama-b7200.zip` соответствует ожиданию скрипта; произвольное имя исходного архива он не ищет.

### 5.2. Проверить целостность

```powershell
$qwenFile='.private/models/qwen/qwen2.5-1.5b-instruct-q4_k_m.gguf'
$qwenHash=(Get-FileHash -LiteralPath $qwenFile -Algorithm SHA256).Hash.ToLowerInvariant()
if ($qwenHash -ne '6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e') { throw 'Qwen checksum mismatch' }
if ((Get-Item -LiteralPath $qwenFile).Length -ne 1117320736) { throw 'Qwen size mismatch' }
$runtimeHash=(Get-FileHash -LiteralPath .private/tools/llama-b7200.zip -Algorithm SHA256).Hash.ToLowerInvariant()
if ($runtimeHash -ne '4c69e78ab94b2d05326f9c066ecf89587420eb3de9809c444cf24cd67c238030') { throw 'llama.cpp checksum mismatch' }
```

Хеш runtime сверён с метаданными официального GitHub asset b7200. Хеш модели совпадает с проверенным локальным файлом и закреплён в стартовом скрипте. При ошибке не отключайте проверку: повторите загрузку соответствующего файла. Маленькая HTML-страница ошибки не является весами модели.

### 5.3. Запустить процесс модели

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_local_llm.ps1
Invoke-RestMethod http://127.0.0.1:18080/health
Invoke-RestMethod http://127.0.0.1:18080/v1/models
```

`ExecutionPolicy Bypass` здесь относится только к дочернему процессу этого локального скрипта, не меняет глобальную политику. Скрипт проверяет хеши, распаковывает runtime, запускает скрытый процесс, записывает PID в `.private/llama-server.pid`. Параметры: context 2048, 4 CPU threads, одна параллельная генерация, alias `qwen-local`, журнал текста запросов отключён.

Дождитесь HTTP 200 от `/health`; во время загрузки возможна временная неготовность. `/v1/models` должен содержать `qwen-local`. Если порт уже занят, скрипт остановится и сохранит существующий процесс. Сначала проверьте его `/health` и `/v1/models`; не запускайте вторую копию и не завершайте неизвестный процесс.

### 5.4. Настроить приложение

Если `.env` ещё нет:

```powershell
if (!(Test-Path -LiteralPath .env)) { Copy-Item -LiteralPath .env.example -Destination .env }
```

Откройте `.env` текстовым редактором. Для новой установки настройки:

```dotenv
COMPOSE_PROJECT_NAME=alfa-jury
WEB_PORT=3080
POSTGRES_PASSWORD=local-demo-only
LLM_MODE=local
LLM_BASE_URL=http://host.docker.internal:18080/v1
LLM_MODEL=qwen-local
LLM_API_KEY=
LLM_ALLOW_EXTERNAL=false
```

Если БД уже запускалась с другим `POSTGRES_PASSWORD`, сохраните прежнее значение: изменение env не меняет пароль в существующем PostgreSQL-томе. При занятом веб-порте используйте другой WEB_PORT. При ранее заданном `$env:WEB_PORT` действует значение текущего PowerShell; все проверочные URL должны ему соответствовать.

В Docker нельзя подставлять `127.0.0.1:18080` как адрес модели Windows: это loopback самого контейнера. Для этого сценария нужен именно `http://host.docker.internal:18080/v1`.

### 5.5. Включить AI-кнопку

DEMO + Qwen, без E5:

```powershell
docker compose -f compose.yaml -f compose.llm.yaml up -d --build --wait --wait-timeout 240
```

DEMO + E5 + Qwen, после раздела 4:

```powershell
docker compose -f compose.yaml -f compose.semantic.yaml -f compose.llm.yaml up -d --build --wait --wait-timeout 600
```

Проверка доступности модели **из контейнера приложения**:

```powershell
docker compose -f compose.yaml -f compose.semantic.yaml -f compose.llm.yaml exec -T api python -c "import urllib.request; print(urllib.request.urlopen('http://host.docker.internal:18080/health', timeout=5).status)"
```

Ожидается `200`. Для варианта без E5 уберите `-f compose.semantic.yaml`. Добавление overlay к `exec` не включает отсутствующую модель в уже работающем контейнере: сначала выполните соответствующий `up`.

### 5.6. Проверить ответ Qwen через приложение

```powershell
$juryPayload=@{query='Хочу открыть кофейню и проверить спрос до аренды помещения.'} | ConvertTo-Json -Compress
$juryBody=[System.Text.Encoding]::UTF8.GetBytes($juryPayload)
Invoke-RestMethod -Uri 'http://127.0.0.1:3080/api/intent' -Method Post -ContentType 'application/json; charset=utf-8' -Body $juryBody -TimeoutSec 30
```

Нормальный ответ — `status=ready` с предложением; иногда валидатор возвращает `unchanged`, если полезного изменения нет. Точный текст не фиксирован. `llm_enabled=true` в bootstrap показывает настройку, но само по себе не доказывает доступность сервера модели — её проверяют команды выше.

В UI введите задачу → «Уточнить задачу с AI» → проверьте предложение → явно примените или сохраните исходную задачу. При наличии уточняющего вопроса ответьте на него. Основной маршрут можно построить и без обращения к Qwen. Таймаут/невалидный ответ AI не должен блокировать обычный подбор.

## 6. Импорт FULL — только если у жюри есть исходная выгрузка

Закрытый дамп, производный каталог, история и модели намеренно отсутствуют в публичном ZIP. Для этого шага используйте выгрузку, полученную от организаторов по разрешённому каналу; публичная ссылка на дамп здесь не размещается. Без неё используйте DEMO, а не искусственно заполненный «FULL».

Установите Python 3.13 для Windows с Python Launcher. Поместите исходный файл в `.private/alfa_course_hackathon.backup`. Из корня:

```powershell
py -3.13 -m venv .venv
.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\restore_private.ps1 -Backup .private/alfa_course_hackathon.backup -Container hac-audit-jury
.venv/Scripts/python.exe scripts/audit_database.py --container hac-audit-jury
.venv/Scripts/python.exe scripts/import_catalog.py --container hac-audit-jury
.venv/Scripts/python.exe scripts/extract_source_links.py --container hac-audit-jury
.venv/Scripts/python.exe scripts/import_catalog.py --container hac-audit-jury
```

Если окружение `.venv` уже подготовлено, не создавайте его повторно без необходимости. Проверяйте успешное завершение каждой команды перед следующей. Если восстановление сообщает `Container already exists`, скрипт ничего не удаляет: изучите существующий контейнер либо выберите новое имя `hac-audit-*` и используйте его во всех командах.

`restore_private.ps1` проверяет заголовок PGDMP и использует закреплённый PostgreSQL 18: pg_restore 16 не читает формат данного архива. Источник восстанавливается в отдельную БД с `network=none`, без опубликованных портов и с read-only mount исходного файла. **Это не БД прогресса приложения.** Аудиторская БД находится в tmpfs; завершите импорт до её остановки. Для последующего runtime исходная БД не требуется: приложение читает `.private/catalog.json`.

Импорт сохраняет только разрешённые короткие метаданные. Извлечение канонических ссылок читает опубликованные бесплатные блоки локально, тела не переносятся в каталог. Платные уроки и пользовательские записи не публикуются. Цена, подписка и доступ обрабатываются отдельно.

Ожидается непустой `.private/catalog.json`. На проверенной выгрузке: 1476 материалов, версия `e4dc26acca5e0e25`. При другой официальной версии данных сверяйте фактическую статистику, не подгоняйте файл под это число. Наличие адреса не означает успешную HTTP-проверку каждой страницы.

## 7. Команды полного режима

FULL без моделей:

```powershell
docker compose -f compose.yaml -f compose.full.yaml up -d --build --wait --wait-timeout 240
```

FULL + E5:

```powershell
docker compose -f compose.yaml -f compose.full.yaml -f compose.semantic.yaml up -d --build --wait --wait-timeout 600
```

**FULL + E5 + Qwen** — сначала импорт, веса E5, работающий Qwen и настройки `.env` из раздела 5:

```powershell
docker compose -f compose.yaml -f compose.full.yaml -f compose.semantic.yaml -f compose.llm.yaml up -d --build --wait --wait-timeout 600
Invoke-RestMethod http://127.0.0.1:3080/api/ready
Invoke-RestMethod http://127.0.0.1:3080/api/bootstrap | Select-Object catalog_mode,catalog_count,semantic_model,semantic_fallback,llm_enabled
```

Ожидается: `catalog_mode=full`, фактическое число материалов, E5 без fallback, `llm_enabled=true`. Отдельно повторите `/api/intent` из раздела 5.6: только реальный ответ подтверждает работоспособность модели.

В FULL кнопка «Открыть на Альфа-Курсе» ведёт на официальный источник в новой вкладке; «Подробнее» открывает короткое описание. Покупка/авторизация выполняются на исходной платформе. Платный доступ не обходится. При неизвестном URL показывается объяснение; подмены адреса главной страницей нет.

## 8. Альтернативный Qwen через установленный Ollama

Это альтернативная конфигурация совместимого API; закреплённый Windows-вариант llama.cpp выше проверялся отдельно. Сквозной запуск каждой версии Ollama/каждой ОС не заявляется. Выберите один сервер модели.

На машине с установленным [Ollama](https://ollama.com/download) загрузите публичную локальную модель:

```powershell
ollama pull qwen2.5:1.5b
ollama list
Invoke-RestMethod http://127.0.0.1:11434/api/tags
```

Запустите приложение Ollama/его локальный сервер, если он ещё не работает. Для Docker Desktop задайте в `.env`:

```dotenv
LLM_MODE=local
LLM_BASE_URL=http://host.docker.internal:11434/v1
LLM_MODEL=qwen2.5:1.5b
LLM_API_KEY=
LLM_ALLOW_EXTERNAL=false
```

Перезапустите нужный Compose-вариант с `compose.llm.yaml`, затем проверьте `/api/intent`. Модель выбирайте локальную, без суффикса `:cloud`. На Linux `host.docker.internal` через host-gateway не равен loopback хоста: требуется отдельно обеспечить доступ из контейнера к локальному серверу; схема запуска llama.cpp Windows не является инструкцией настройки Linux-сети. DEMO без модели и Docker API при этом продолжают работать.

Официальные сведения: [модель qwen2.5:1.5b](https://ollama.com/library/qwen2.5:1.5b), [совместимость API](https://docs.ollama.com/api/openai-compatibility). Данная интеграция использует `/v1/chat/completions`, не интерактивный `ollama run` в критическом пути.

## 9. Подключение собственного совместимого API

Для базовой проверки и локальных моделей этот раздел не нужен. Если оператор сознательно выбирает внешний сервис, в собственном `.env` задаются:

| Переменная | Значение |
|---|---|
| `LLM_MODE` | `api` |
| `LLM_BASE_URL` | HTTPS base URL выбранного провайдера, заканчивающийся на `/v1`, без `/chat/completions` |
| `LLM_MODEL` | Реальный ID модели у этого провайдера |
| `LLM_API_KEY` | Собственный ключ оператора, если нужен провайдеру |
| `LLM_ALLOW_EXTERNAL` | `true` только после явного разрешения отправки текста |

Нужен Chat Completions API с `response_format={"type":"json_object"}`; произвольный HTTP endpoint не является совместимым. Затем используется тот же `compose.llm.yaml`. Этот релиз не требует стороннего платного сервиса; конкретный внешний провайдер и его тарификация не проверялись и не включались.

Во внешний AI передаётся только введённый текст задачи, не каталог/профиль/история. Сам текст может содержать персональные сведения: не отправляйте закрытые данные и ПДн, ключ не вводится в UI и не включается в архив. До включения оператор решает вопросы разрешения и минимизации данных. При `LLM_ALLOW_EXTERNAL=false` внешний endpoint намеренно блокируется.

## 10. Сценарий проверки жюри за 5–7 минут

1. Откройте главную, проверьте маркировку DEMO/FULL. Введите «Хочу привлечь клиентов в кофейню», профиль оставьте пустым. Постройте маршрут.
2. Проверьте объяснение и следующий шаг; откройте пример DEMO либо официальный источник FULL. Для отраслево общего результата должно быть пояснение, число карточек может быть меньше трёх.
3. Отметьте материал «Изучено», перестройте маршрут: он исключён. Откройте «Мой прогресс», перезагрузите страницу: отметка сохраняется в этой браузерной сессии.
4. Измените задачу или профиль: предыдущая выдача отмечается устаревшей до нового построения. Ответ старого запроса не должен заменять новый.
5. Перейдите «Для жюри» → выберите предпринимателя → «Сравнить алгоритмы». Это два расчёта на одном каталоге. Baseline не использует личный профиль, историю или E5; численные score систем не являются сопоставимыми метриками качества.
6. Введите «Помогите с бизнесом» или задачу вне каталога: система уточняет, а не заполняет маршрут случайными карточками. Неполное покрытие явно обозначается.
7. Если включён Qwen, проверьте отдельную AI-кнопку, осмысленное предложение и явное принятие. Отказ от предложения сохраняет исходную задачу. Без Qwen обычный подбор доступен.
8. Перезапустите `db` и `api` с теми же Compose-файлами, дождитесь healthy и обновите страницу прогресса. Не удаляйте cookie браузера или том БД при этой проверке.

Независимых человеческих меток пока нет; превосходство над baseline и рост покупок не доказаны. Разбор 150 запросов и повтор 120 — использованная в настройке регрессия, не независимый test. Основной файл оценки: [docs/evaluation.md](docs/evaluation.md). Нагрузка, полная WCAG-проверка и полный HTTP-аудит платформы не заявляются выполненными.

## 11. Проверки кода — дополнительно, если нужны

Это отдельный путь для проверки исходников, а не условие запуска Docker. Из корня, Python 3.13 и Node.js 24:

```powershell
py -3.13 -m venv .venv
.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
.venv/Scripts/python.exe scripts/check_version.py
.venv/Scripts/python.exe scripts/check_public_files.py
.venv/Scripts/python.exe -m ruff check backend scripts audit
.venv/Scripts/python.exe -m pytest -q
npm --prefix frontend ci
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

Для опционального теста E5 до pytest, при наличии скачанных весов:

```powershell
.venv/Scripts/python.exe -m pip install -r backend/requirements-semantic.txt
$env:TEST_SEMANTIC_MODEL_DIR=(Resolve-Path .private/models/e5).Path
.venv/Scripts/python.exe -m pytest -q
```

В проверенной 1.2.4 прошло 182 теста с реальной E5; без весов соответствующая опциональная проверка пропускается. Браузерные проверки: 46 сценариев desktop/mobile, выполняются на отдельном DEMO, поскольку создают feedback. Инструкция изоляции — [docs/TEAM.md](docs/TEAM.md). Не запускайте E2E против пользовательского FULL.

Если Python-окружение уже есть, не повторяйте создание venv. Дополнительный live-smoke из корня, подставив свой порт:

```powershell
.venv/Scripts/python.exe scripts/smoke.py --base http://127.0.0.1:3080
```

Smoke создаёт собственную тестовую сессию и отметку, не подменяет пользователя исходной платформы.

## 12. Диагностика

| Симптом | Проверка и действие |
|---|---|
| `Cannot connect to Docker daemon` | Запустить Docker Desktop, проверить Linux engine и `docker version`. |
| Порт 3080 занят | Выбрать WEB_PORT, например3090; использовать этот порт во всех URL. Не останавливать неизвестный сервис. |
| E5 mount/model missing | Выполнить загрузку раздела4; проверить все файлы, затем bootstrap. Для быстрой проверки убрать semantic overlay. |
| `llm_enabled=false`, AI-кнопки нет | Запустить нужный вариант с `compose.llm.yaml`; переменные в `.env` сами по себе не подключают overlay. |
| AI `model_missing` | Указать LLM_MODEL и пересоздать API через соответствующий `up`. Для llama.cpp имя `qwen-local`, для Ollama — установленный тег. |
| AI `unavailable` | Проверить host `/health`, затем из Docker; сопоставить порт18080/11434 и base URL. Дождаться загрузки модели. |
| AI `invalid_response`/`unchanged` | Провайдер/модель могут не дать подходящую схему или новую формулировку. Основной маршрут доступен; не выдавать старую фразу за новое улучшение. |
| AI `configuration_blocked` | Локальный режим допускает только разрешённые локальные имена HTTP; внешний режим требует HTTPS и явного `LLM_ALLOW_EXTERNAL=true`. |
| FULL не стартует | Проверить `.private/catalog.json` и правильный overlay. Дамп `.backup` нельзя монтировать как готовый JSON. |
| `Container already exists` при restore | Старый аудит не удаляется автоматически; новое уникальное имя hac-audit-* передать всем командам импорта. |
| БД отвергает пароль | Не менять пароль существующего тома простым редактированием env; восстановить прежнюю настройку. Не удалять пользовательский том ради обхода ошибки. |
| Внешний Альфа-Курс выдаёт TLS/сеть/вход | Это отдельная доступность платформы. Сертификаты не отключать, отсутствие доступа не выдавать за успешную HTTP-проверку. |
| У FULL мало подходящих карточек | Полнота кратких метаданных и каталога ограничена; проверьте задачу/формат/исключённые материалы. Заполнение случайными материалами не является корректным результатом. |
| Docker build не скачивает npm/PyPI | Проверить доступ Docker Desktop к публичным реестрам и его сетевые настройки. В локальной проверке использовался отдельный build.network=host override; он не требуется стандартным Linux CI и не включён в этот архив. Не отключать TLS. |

Состояние и логи полного варианта:

```powershell
docker compose -f compose.yaml -f compose.full.yaml -f compose.semantic.yaml -f compose.llm.yaml ps
docker compose -f compose.yaml -f compose.full.yaml -f compose.semantic.yaml -f compose.llm.yaml logs --tail 80 api web
```

Для DEMO уберите full overlay, для вариантов без моделей — соответствующие overlay. Ошибки запуска сначала сопоставляйте с режимом, не меняйте все настройки одновременно. Полный `docker compose config` может раскрывать локальные секреты: не прикладывайте его без редактирования.

## 13. Остановка, повторный запуск и работа после подготовки

Остановить полный стек **с сохранением прогресса**:

```powershell
docker compose -f compose.yaml -f compose.full.yaml -f compose.semantic.yaml -f compose.llm.yaml down
```

Для DEMO используйте соответствующий набор файлов. **Не добавляйте `-v` / `--volumes`: это удаляет прогресс выбранного проекта.** Прогресс хранится в отдельном PostgreSQL-томе и связан с cookie браузера; удаление cookie теряет доступ к прежней сессии, полноценной авторизации здесь нет.

После успешной сборки и скачивания файлов можно запускать готовые образы без новой сборки:

```powershell
docker compose -f compose.yaml -f compose.full.yaml -f compose.semantic.yaml -f compose.llm.yaml up -d --no-build --wait --wait-timeout 600
```

Для этого уже должны существовать локальные образы, FULL-файл и веса; Qwen Windows запускается отдельно после перезагрузки компьютера. E5 в overlay использует offline-режим. Открытие внешних источников всё равно требует сети; это не проверка сборки при полностью отключённом сетевом адаптере.

Native Qwen не останавливается командой Compose. Для остановки именно процесса, запущенного комплектным скриптом, сначала сверяется сохранённый PID и путь executable:

```powershell
if (Test-Path -LiteralPath .private/llama-server.pid) {
    $juryLlmProcessId=[int](Get-Content -LiteralPath .private/llama-server.pid)
    $juryLlmProcess=Get-CimInstance Win32_Process -Filter "ProcessId = $juryLlmProcessId"
    $juryLlmExecutable=(Resolve-Path -LiteralPath .private/tools/llama/llama-server.exe).Path
    if ($null -ne $juryLlmProcess) {
        if ($juryLlmProcess.ExecutablePath -ne $juryLlmExecutable -or $juryLlmProcess.CommandLine -notlike '*--alias qwen-local*') { throw 'PID does not identify the expected local Qwen process' }
        Stop-Process -Id $juryLlmProcessId
    }
}
```

Команда не завершает другие `llama-server`/Python/Docker-процессы. Для Ollama управление выполняется самим Ollama.

## 14. Порты, файлы и происхождение моделей

| Компонент | Адрес/путь |
|---|---|
| UI, API proxy, Swagger | `127.0.0.1:3080`, `/api/docs`; порт меняется WEB_PORT |
| FastAPI/PostgreSQL | Только внутри сети Compose; порты8000/5432 на хост не публикуются |
| Windows Qwen llama.cpp | `127.0.0.1:18080`; в контейнере host.docker.internal:18080 |
| Альтернативный Ollama | Обычно127.0.0.1:11434; base URL для адаптера заканчивается на `/v1` |
| Приватный каталог | `.private/catalog.json`, read-only mount FULL |
| Веса E5/Qwen, runtime | `.private/models/e5`, `.private/models/qwen`, `.private/tools` |
| Персональные настройки | `.env`, отсутствует в архиве; шаблон `.env.example` включён |

Источники публичных компонентов:

- [Qwen GGUF, закреплённая ревизия](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/tree/91cad51170dc346986eccefdc2dd33a9da36ead9), Apache-2.0.
- [llama.cpp b7200](https://github.com/ggml-org/llama.cpp/releases/tag/b7200), закреплённый Windows CPU asset.
- [ONNX E5](https://huggingface.co/Xenova/multilingual-e5-small), [оригинальная multilingual E5](https://huggingface.co/intfloat/multilingual-e5-small), MIT-лицензия базовой модели.
- [Официальная документация HF CLI](https://huggingface.co/docs/huggingface_hub/guides/cli).

## 15. Что включено в чистый комплект

Все публичные файлы текущего Git-дерева: код backend/frontend, Dockerfiles/Compose, фиксированные зависимости, тесты, DEMO, общие AGENTS, документация и PDF/PPTX. Исторические аудиты сохранены как документация; их старые числа не являются результатами нового прогона. Текущие проверки версии1.2.4 — [docs/STATUS.md](docs/STATUS.md), [разбор интеграции](docs/integration-2026-11-16.md).

Архив не содержит `.git`, `.env`, `.private`, дамп/реальный каталог/историю, веса, node_modules, venv, сборочные кэши и тестовые логи. Его SHA-256 находится в соседнем файле `.zip.sha256`; проверить можно `Get-FileHash -Algorithm SHA256 -LiteralPath <путь-к-архиву>`. Публикация кода или наличие этого ZIP не является фактической отправкой организаторам.
