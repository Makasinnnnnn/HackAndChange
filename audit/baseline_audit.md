Ниже — аудит без изменения файлов проекта. Все эксперименты выполнялись во /tmp/opencode и через runtime monkeypatch; ссылки на строки — по текущему состоянию репозитория.
Короткий вывод. Жалоба «эмбеддинги плохо работают» в текущем виде не подтверждается. В default-демо эмбеддинги вообще выключены (compose.yaml, target base, нет SEMANTIC_MODEL_DIR), а когда E5 включается, она находит осмысленных соседей. Основная причина «RAG отвечает шлаково» — жёсткие pre-retrieval фильтры, которые отсекают кандидатов до E5, и отсутствие гибридного поиска. Замена модели эмбеддингов сама по себе не исправит 12/16 запросов.
1. Карта проекта
Слой	Файл	Что делает	Вывод
API	backend/app/main.py	/api/recommendations, /api/recommendations/baseline, /api/intent, /api/demo/compare, /api/evaluation/results, /api/bootstrap	Контракт аккуратный; /api/recommendations не вызывает LLM
Оркестрация	backend/app/engine.py	parse_intent → exclusion_reason → SearchIndex.search → scoring → task_shortlist/floor → select → recommendation	Основной пайплайн детерминированный, 255 строк
Интент	backend/app/recommendation/intent.py	Правила, словари TOPICS, PLATFORMS, TAX_SUBJECTS, parse_intent, clarification	Много ручных правил; clarification срабатывает до retrieval
Операции	backend/app/recommendation/tasks.py	TASKS (60+ задач), query_tasks, material_tasks, task_evidence, task_shortlist	Хорошая база, но нет семейств/синонимов задач
Жёсткие фильтры	backend/app/recommendation/eligibility.py	exclusion_reason: sector, format, entity, no_informative_anchor, unsupported_task и др.	Главный источник отсева
Индекс	backend/app/recommendation/index.py	TF-IDF word + char; optional E5; поля title + title + description + topics + tags	Нет BM25/RRF; не индексируются industries/stage/difficulty/access/duration/related_ids
Ранжирование	backend/app/recommendation/ranking.py	profile_score, select, diversity penalty	Персональные бонусы bounded, baseline независим
Объяснения	backend/app/recommendation/explanation.py	task_reasons, constraint_evidence, recommendation, next_action	Причины берутся из реальных сигналов — это правильно
LLM	backend/app/llm.py	Только interpret: goal + clarification, JSON + Pydantic Intent	LLM не ранжирует и не объясняет; формат why/next_step/confidence не реализован
Семантика	backend/app/semantic.py	ONNX INT8 Xenova/multilingual-e5-small, 384 dim, manifest/checksum	Опциональна; при отсутствии — semantic_fallback=true
Каталог	backend/app/catalog.py	Загрузка demo.json/full, provenance, дедупликация	DEMO 36 материалов, описания 69–100 символов
Хранение	backend/app/storage.py	PostgreSQL, профиль, feedback, progress	Feedback используется только как исключение
Оценка	backend/app/evaluation.py, scripts/evaluate.py	P@5, pooled Recall@5, NDCG@5, MRR@5; 32 профиля / 51 пара / 0 human labels	Метрик @10, LLM-Judge и таблицы «baseline vs решение» нет
Фронт	frontend/app/page.tsx	Вызов /intent, затем /recommendations; карточки, сравнение, диагностика	route.clarification рисуется отдельным empty-state
Инфра	compose.yaml, compose.semantic.yaml, backend/Dockerfile	db + api + web; semantic — отдельный profile	Default demo без E5
Поток /recommendations:
POST /api/recommendations
  → Engine.recommend
    → parse_intent (правила)
    → exclusion_reason (жёсткие фильтры)
    → SearchIndex.search (TF-IDF ± E5)
    → candidate scoring + profile_score
    → task_shortlist / relative floor
    → select (diversity)
    → recommendation (reasons + next_action)
Поток /intent:
POST /api/intent → llm.interpret → Intent{goal, clarification}
То есть LLM — это отдельный необязательный шаг в UI, а не часть рекомендательного пайплайна. Для кейса это допустимо («генеративная LLM не обязательна»), но объяснимость и why/confidence из LLM сейчас не используются.
Ограничения аудита:
- Docker daemon недоступен (/var/run/docker.sock отсутствует), live docker compose up не выполнялся; docker compose config -q проходит.
- Полный каталог 1473 материалов и .private в окружении отсутствуют — retrieval проверялся на DEMO 36 карточках.
- Human labels = 0, поэтому реальные Recall/NDCG и превосходство над baseline не доказаны.
2. Диагноз: почему «RAG отвечает шлаково»
2.1. Что проверено
- pytest -q: 160 passed, 1 skipped — проект стабилен, проблема поведенческая.
- Прогон engine на 16 разговорных запросах с E5 и без:
- 12/16 вернули clarification и 0 карточек;
- среднее число карточек: 0.31 без E5, 0.38 с E5;
- пять карточек не вернул ни один запрос — но это ожидаемо, CONSTRAINT_LIMIT=3.
- Счётчики отсева:
- «нужно продвигать бизнес»: unsupported_task: 25, incidental_document_mention: 8, unrequested_specialization: 1, eligible = 2;
- «как выбрать налоговый режим для ип»: unsupported_task: 26, eligible = 1;
- «нужно чтобы больше покупателей приходило»: no_informative_anchor: 36, eligible = 0.
- Прототип «soft filters» через monkeypatch: 8/10 запросов начинают возвращать 2–3 карточки. Это доказывает, что бутылочное горлышко — фильтры, а не модель эмбеддингов.
- Проверены три сценария из Приложения 2 (раздел 4).
2.2. Шесть причин, по вкладу
#	Причина	Где	Доказательство	Вклад
1	E5 выключена в default-демо	compose.yaml:17-35, semantic.py:64-67	target: base, нет SEMANTIC_MODEL_DIR; algorithm="lexical-personal-v7", semantic_fallback=true	Высокий: жюри видит только TF-IDF
2	Anchor-gate требует ≥67% слов запроса в заголовке	eligibility.py:100-103	36/36 отсеяно для «нужно чтобы больше покупателей приходило»	Высокий: убивает естественные перефразировки
3	unsupported_task не знает синонимов задач	eligibility.py:179-180, tasks.py:298-299	25/36 для «продвижение бизнеса», 26/36 для «налоговый режим»	Высокий: широкие задачи становятся «неподдержанными»
4	Ранний intent.clarification до retrieval	engine.py:94-95	12/16 → 0 карточек	Высокий: пользователь не видит даже ближайших материалов
5	Нет BM25 + RRF + reranker; короткие карточки	index.py:24-56	Только TF-IDF word/char; описания 69–100 символов	Средний: точные термины («УСН», «НДС», «кассовый разрыв») теряются
6	task_shortlist + relative floor оставляют 1–2 карточки	engine.py:212-220	S1 = 2 карточки, S2 = 1 карточка	Средний: это в рамках правил проекта (≤3), но нет объяснения порядка
2.3. Что не подтвердилось
- E5 не «плохая». На реальных запросах она находит осмысленное:
- «не понимаю, куда уходят деньги» → «Кассовый разрыв», similarity 0.838;
- «нужно чтобы больше покупателей приходило» → «Клиентов мало», 0.841.
- Проблема не в падении тестов и не в Pydantic-валидации.
- Замена E5-small на BGE-M3 не исправит 12/16: кандидаты отсекаются до E5, поэтому более сильная модель просто не получит документов.
- TF-IDF не «нейросемантический поиск» — это честно указано в проекте, но в default-демо другого нет.
2.4. Ответ на жалобу
«Эмбеддинги плохо работают» — нет. В default-демо они не включены. Когда включены, они дают разумных соседей, но пайплайн отсекает их фильтрами no_informative_anchor и unsupported_task, а затем ранний clarification возвращает пустоту. E5-small действительно слабее BGE-M3, но это вторая проблема, а не первая.
3. Аудит по 8 блокам кейса
Блок	Что есть	Оценка	Чего нет
1. Архитектура	FastAPI + Engine + PostgreSQL + Next.js; детерминированный пайплайн; LLM только в /api/intent; baseline отдельным endpoint	✅ Чисто и тестируемо	Нет retrieval-first fallback, CRAG, judge-цикла; LLM не участвует в ранжировании/объяснении
2. Холодный старт	Profile из 5 полей; пустой профиль обрабатывается; 6 demo-персон; 32 eval-профиля	⚠️ Частично	Нет профилизатора с inferred-флагами, стартовой подборки с объяснением порядка, продолжения маршрута
3. Retrieval	TF-IDF word + char; optional E5-small; индексируются title×2 + description + topics + tags	❌ Главный bottleneck	Нет BM25, RRF, reranker, LLM-обогащения карточек; E5 не default; жёсткие фильтры до retrieval
4. Объяснимость / next best action	reasons из реальных сигналов; next_action из таблицы по source_type/task; phase	⚠️ Основа хорошая	Нет why (3 предложения), confidence, порядка изучения; фронт показывает reasons.slice(0,2)
5. Бейзлайн и метрики	/api/recommendations/baseline; parse_intent(baseline=True); P@5, pooled Recall@5, NDCG@5, MRR@5	⚠️ Baseline есть, метрики не доказаны	Нет Recall@10/NDCG@10/P@10, LLM-Judge, human labels, таблицы «baseline vs решение»
6. A/B-план	docs/product-metrics.md: события, рандомизация по user_id, основная метрика, ограничители	⚠️ План есть	Нет расчёта N/MDE, длительности, sequential testing; нет зафиксированных чисел
7. Docker / README / формат сдачи	3 сервиса, healthchecks, .env.example, README, docs/submission; docker compose config -q OK	✅/⚠️	Default demo без E5; live-запуск в этом окружении не проверен (daemon недоступен)
8. Стек	FastAPI, scikit-learn, onnxruntime, PostgreSQL, Next.js	✅ Минимальный и защитимый	Нет rank_bm25, reranker, Qdrant; Qdrant при 1.5k карточек не обязателен
Итог: архитектура и инженерия — сильные. Качество retrieval — слабое. LLM-слой формально есть, но используется только как «переформулировать запрос», а не как ранжировщик/объяснитель.
4. Прогон трёх сценариев из Приложения 2
Сценарий	Запрос	Факт	Ожидание кейса	Разрыв	Фикс
S1. Новый пользователь, «продвижение бизнеса»	«нужно продвигать бизнес»	2 карточки; нет стартовой подборки и объяснения порядка	Стартовая подборка ≤3 + почему эти + следующий шаг	unsupported_task/task_shortlist; нет learning path	P0-3, P1-4
S2. История действий / холодный старт	feedback + повторный запрос; пустой профиль	С feedback — 1 карточка; cold start — 1 карточка; нет positive memory и продолжения маршрута	Исключить completed, использовать helpful, продолжить маршрут	Feedback только исключает; нет маршрута	P1-3, P1-4
S3. Точного совпадения нет	«Яндекс.Директ для салона красоты»; «Instagram для услуг»	Первый — clarification, 0 карточек; второй — 1–2 карточки	Честно сказать «точного нет», step-back к широкой теме, маршрут	Ранний clarification; нет CRAG/step-back	P0-1, P0-2, P1-4
Вывод по сценариям: система либо молчит (clarification), либо выдаёт 1–2 карточки без объяснения порядка. Сценарий «точного совпадения нет» — самый провальный: вместо честного «нет точного материала, вот ближайший маршрут» возвращается пустой экран.
5. Приоритизированный план
P0 — до демо (must)
#	Файл / функция	Изменение	Критерий готовности	Усилие	Эффект	Риск
P0-1	engine.py, Engine.recommend, строки 94-95, 208-211, 233-238	Убрать ранний return по intent.clarification; сначала retrieval, затем либо карточки + вопрос в notice, либо вопрос без карточек	На 16 запросах: clarification ≤4, ≥12 с карточками; S3 даёт 1–3 карточки + честный notice	S	Убирает главный видимый провал — 0 карточек	UI может показать вопрос вместо карточек; нужен frontend-патч
P0-2	eligibility.py, exclusion_reason, строки 100-103	Удалить hard-gate no_informative_anchor; честность обеспечивает post-retrieval порог + notice	no_informative_anchor = 0; «нужно чтобы больше покупателей приходило» с E5 даёт ≥1 карточку	S	Разблокирует естественные перефразировки	Больше шума; компенсируется порогом и notice
P0-3	tasks.py, task_evidence, строки 298-299 + TASK_FAMILIES; eligibility.py:179-180; explanation.py:8-15	Считать задачу подтверждённой, если карточка содержит задачу или её семейство (promotion ↔ acquisition ↔ channels)	«продвижение бизнеса»: eligible 2→≥5; «налоговый режим»: 1→≥4	S/M	Широкие задачи перестают быть «unsupported»	Ложные срабатывания; объяснение должно говорить «смежная задача»
P0-4	index.py, SearchIndex, строки 9-56; policy.py:27	Добавить rank_bm25, Evidence.bm25, Evidence.fused — RRF k=60 по lexical + BM25; engine использует evidence.fused	Точные термины «УСН», «НДС», «кассовый разрыв» в top-3; ≥12/16 запросов с карточками	M	+5…11 п.п. Recall@5 по бенчмарку теории; ловит точные термины	Нужна рекалибровка MIN_RELEVANCE; BM25 на 36 документах нестабилен
P0-5	models.py:83-90; explanation.py:106-119; frontend/app/page.tsx:16,263,279-280	Добавить в Recommendation поля why, next_step, confidence; заполнять детерминированно из reasons/score; вывести на карточке	Каждая карточка: why 1–3 предложения, next_step, confidence 0…1; API additive	S	Закрывает критерий «объяснимость и следующий шаг»	confidence могут принять за вероятность; подписать «эвристическая оценка»
P0-6	compose.yaml:17-35; compose.semantic.yaml; scripts/download_model.py	Сделать E5 default: target: semantic, SEMANTIC_MODEL_DIR=/models/e5, model-download + named volume; graceful fallback	/api/bootstrap: semantic_model != null, semantic_fallback=false; cold start ≤180 с	M	Жюри видит эмбеддинги, а не TF-IDF; закрывает буквальную жалобу	Размер образа/время старта; offline-демо; нужно согласие владельца
P0 — условно, если есть время/GPU
#	Файл / функция	Изменение	Критерий готовности	Усилие	Эффект	Риск
P0-7	новый recommendation/rerank.py; engine.py после строки 205	CrossEncoder BAAI/bge-reranker-v2-m3 поверх top-20 кандидатов	Top-3 вручную лучше на 10 запросах; p95 ≤500 мс на 36 карточках	M	Самый крупный одиночный прирост Recall по теории (+12.1 п.п.)	CPU-латентность; +2 ГБ зависимостей; на 36 карточках эффект может быть нестабилен
P0-8	новый scripts/enrich_catalog.py; catalog.py/index.py	Один batch-прогон локальной Qwen/ручного обогащения: 5–8 поисковых фраз, аудитория, стадия; индексировать обогащённый текст	Описания ≥150 символов или 5–8 ключевых фраз; exact-term recall растёт	M/L	Устраняет root cause «эмбеддингам нечего кодировать»	Нельзя отправлять каталог внешнему API; локальная Qwen медленная; нужно решение владельца
P1 — до сдачи
#	Файл / функция	Изменение	Критерий готовности	Усилие	Эффект	Риск
P1-1	evaluation.py:8-23; scripts/evaluate.py	Добавить Recall@10, NDCG@10, P@10; сохранить @5; вывести таблицу baseline vs personal	Расчёт на 32 профилях; 0 human labels явно помечены	S/M	Главный слайд «baseline vs решение»	Без меток метрики нельзя называть финальными
P1-2	llm.py (новый judge); models.py	LLM-Judge 1–5 по why/next_step/relevance; один retry при среднем <3; судья не видит имя алгоритма	20 запросов, средний ≥4/5; нет утечки каталога/профиля	M	Judge-цикл и защита от шлака	Дополнительный вызов; bias судьи; только локальная модель по политике проекта
P1-3	llm.py, interpret; models.py:10-16	Профилизатор: stage/industry/task/experience + inferred-флаги; заполнять из одного запроса	Cold start: из запроса строится профиль, выдача меняется	M	Закрывает холодный старт	LLM может ошибиться; inferred не должен выглядеть как факт
P1-4	новый recommendation/route.py; engine.py:221-233	Детерминированный learning path ≤3 материалов по (стадия × задача) + объяснение порядка	S1/S3 получают маршрут и «продолжить»	M	Сценарий «точного совпадения нет» и возврат пользователя	Нельзя превышать правило ≤3; порядок должен быть объяснён
P1-5	docs/product-metrics.md	Добавить N/MDE: 2%→2.2% ≈ 64k/вариант; +20–30% ≈ 8–20k; 2 недели; sequential testing	Таблица с числами и допущениями	S	Честный A/B-план вместо лозунга	Числа зависят от трафика; нельзя обещать результат
P1-6	tests/	3 регрессионных теста ровно по сценариям S1–S3 + 16 natural-запросов	Тесты падают на текущем коде и проходят после P0	S	Защита от отката	Нет человеческих меток — только поведенческие проверки
P2 — после хакатона
#	Изменение	Почему P2
P2-1	Multi-query (2–3 перефразировки + RRF)	По теории эффект близок к нулю для конкретных запросов (Recall@5 0.640 vs 0.644) — не тратить время
P2-2	HyDE	По теории ухудшил результат (0.544); только если запросы короткие, а карточки длинные
P2-3	Qdrant	При 1.5k карточек in-memory BM25+E5 достаточно; Qdrant нужен при >10k или p95 >200 мс [вне референса: порог — инженерная оценка]
P2-4	BGE-M3 вместо E5-small	Сильнее (ruMTEB Retrieval 74.79 vs 67.14 у e5-base), но ~2.3 ГБ и GPU желателен; после стабилизации пайплайна
P2-5	LASA / память взаимодействий	Ценно для cold start, но требует отдельного storage и валидации; после сдачи
P2-6	Расширенный A/B: CTR блока, active days, negative rate	После того как offline-качество доказано
6. Конкретные патчи
6.1. P0-1 — retrieval-first fallback
Файл: backend/app/engine.py, строки 94-95.
# было
if intent.clarification:
    return response(clarification=intent.clarification)
# стало
# Уточнение больше не прерывает пайплайн: сначала retrieval,
# затем либо карточки + вопрос, либо вопрос без карточек.
Файл: backend/app/engine.py, строки 208-211.
# было
if not candidates:
    return response(
        clarification="Точного материала не нашли. Уточните задачу или выберите более общее направление."
    )
# стало
if not candidates:
    return response(
        clarification=intent.clarification
        or "Точного материала не нашли. Уточните задачу или выберите более общее направление."
    )
Файл: backend/app/engine.py, между строкой 238 и блоком missing_tasks.
# стало: если карточки есть, вопрос показываем как notice, а не вместо выдачи
if intent.clarification:
    notice = (notice + " " if notice else "") + intent.clarification
Фронт: frontend/app/page.tsx:374 — не рисовать clarification как empty-state, если route.items.length > 0:
// было
{route.clarification&&<div className="empty-state">...}

// стало
{route.clarification&&!route.items.length&&<div className="empty-state">...}
[вне референса: конкретный UI-патч; теория требует честного уточнения, но не диктует вёрстку]
6.2. P0-2 — убрать anchor-gate
Файл: backend/app/recommendation/eligibility.py, строки 100-103.
# было
if not intent.tasks and not intent.topics and not intent.sectors and not intent.constraints:
    words = informative_words(intent.search)
    if not words or len(words & informative_words(material.title)) / len(words) < 0.67:
        return "no_informative_anchor"
# стало
# Anchor-gate удалён: отсутствие буквального совпадения слов не равно
# нерелевантности. Честность обеспечивает CRAG-порог после retrieval.
Почему не «снизить 0.67 до 0.34»: для запроса «нужно чтобы больше покупателей приходило» в заголовке «Клиентов мало» нет ни одного общего слова, поэтому любой лексический порог всё равно даст 0. Нужен именно post-retrieval semantic-порог.
6.3. P0-3 — семейства задач
Файл: backend/app/recommendation/tasks.py, после словаря TASKS (строка 181).
# стало: синонимы/семейства задач; engineering map, не human labels
TASK_FAMILIES = {
    "promotion": frozenset({"promotion", "acquisition", "channels", "organic", "ad_metrics", "audience"}),
    "acquisition": frozenset({"acquisition", "channels", "promotion", "organic", "audience", "conversion"}),
    "sales_growth": frozenset({"sales_growth", "conversion", "average_check", "funnel", "retention"}),
    "profitability": frozenset({"profitability", "costing", "cost_reduction", "breakeven", "cash_flow"}),
    "cash_flow": frozenset({"cash_flow", "receivables", "management_accounts", "profitability"}),
    "tax_regime": frozenset({"tax_regime", "tax_payment", "self_employed", "vat"}),
    "recruitment": frozenset({"recruitment", "employment", "onboarding"}),
    "demand": frozenset({"demand", "audience", "conversion"}),
}
Файл: backend/app/recommendation/tasks.py, строки 298-299.
# было
def task_evidence(material, requested):
    return requested & material_tasks(material)
# стало
def task_evidence(material, requested):
    found = material_tasks(material)
    return frozenset(
        key for key in requested
        if key in found or (TASK_FAMILIES.get(key, frozenset()) & found)
    )
Файл: backend/app/recommendation/explanation.py, строки 8-15.
# было
def task_reasons(material, matched):
    in_title = matched & task_matches(material.title)
    ...
    if matched - in_title:
        reasons.append("В описании: " + ...)
# стало: не приписывать карточке задачу, которой в ней нет
def task_reasons(material, matched):
    direct = matched & material_tasks(material)
    via = matched - direct
    in_title = direct & task_matches(material.title)
    reasons = []
    if in_title:
        reasons.append("В названии: " + "; ".join(TASKS[key][0] for key in sorted(in_title)))
    if direct - in_title:
        reasons.append("В описании: " + "; ".join(TASKS[key][0] for key in sorted(direct - in_title)))
    if via:
        reasons.append("Смежная задача: " + "; ".join(TASKS[key][0] for key in sorted(via)))
    return reasons
Не забыть импорт: from .tasks import TASKS, material_tasks, task_matches.
6.4. P0-4 — BM25 + RRF
Файл: backend/app/recommendation/index.py, строки 1-56.
# было
from dataclasses import dataclass
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

@dataclass(frozen=True)
class Evidence:
    word: np.ndarray
    char: np.ndarray
    semantic: np.ndarray | None

    @property
    def lexical(self):
        return 0.45 * self.word + 0.55 * self.char
# стало
import re
from dataclasses import dataclass
import numpy as np
from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer


def _tokens(text: str) -> list[str]:
    return re.findall(r"[а-яёa-z0-9]+", text.casefold().replace("ё", "е"))


@dataclass(frozen=True)
class Evidence:
    word: np.ndarray
    char: np.ndarray
    semantic: np.ndarray | None
    bm25: np.ndarray | None = None

    @property
    def lexical(self):
        return 0.45 * self.word + 0.55 * self.char

    @property
    def fused(self):
        """RRF по lexical + BM25; semantic остаётся отдельным сигналом."""
        if self.bm25 is None:
            return self.lexical
        rrf = np.zeros(len(self.lexical), dtype=float)
        for scores in (self.lexical, self.bm25):
            order = np.argsort(-scores)
            rrf[order] += 1.0 / (60.0 + np.arange(1, len(order) + 1))
        peak = float(rrf.max())
        return rrf / peak if peak else rrf
В SearchIndex.__init__:
# стало
self.bm25 = BM25Okapi([_tokens(doc) for doc in self.documents]) if materials else None
В SearchIndex.search:
# стало
bm25 = self.bm25.get_scores(_tokens(query)) if self.bm25 is not None else None
return Evidence(word, char, semantic, bm25)
В engine.py:141:
# было
lexical = evidence.lexical

# стало
lexical = evidence.fused
[вне референса: нормализация RRF к 0…1 — инженерная деталь; теория даёт формулу RRF, но не требует нормализации]
После патча обязательно прогнать 16 запросов и подобрать MIN_RELEVANCE/GENERAL_RELATIVE_FLOOR: RRF меняет масштаб score.
6.5. P0-5 — why / next_step / confidence
Файл: backend/app/models.py, строки 83-90.
# было
class Recommendation(BaseModel):
    material: Material
    reasons: list[str]
    next_action: str
    phase: str
    score: float
    rank_score: float
    signals: dict[str, float]
# стало
class Recommendation(BaseModel):
    material: Material
    reasons: list[str]
    next_action: str
    phase: str
    score: float
    rank_score: float
    signals: dict[str, float]
    why: str = ""
    next_step: str = ""
    confidence: float = 0.0
Файл: backend/app/recommendation/explanation.py, строки 106-119.
# стало: детерминированно, без нового LLM-вызова
    why = " ".join(chosen.reasons[:3]) or "Материал ближе всего к вашей задаче."
    confidence = round(min(0.95, max(0.05, chosen.signals["relevance"])), 2)
    return Recommendation(
        material=material,
        reasons=chosen.reasons,
        next_action=action,
        phase=phase,
        score=round(chosen.score, 6),
        rank_score=round(chosen.rank_score, 6),
        signals={...},
        why=why,
        next_step=action,
        confidence=confidence,
    )
confidence — эвристика, не вероятность. Это надо подписать в UI и docs.
Фронт: frontend/app/page.tsx:16 добавить поля в Item; в routeCard (263–280) вывести item.why вместо reasons.slice(0,2) и бейдж confidence.
6.6. P0-6 — E5 в default compose
Файл: compose.yaml, строки 17-35.
# было
  api:
    build:
      context: .
      dockerfile: backend/Dockerfile
      target: base
    environment:
      DATABASE_URL: ...
      CATALOG_MODE: demo
      ENABLE_DIAGNOSTICS: "true"
# стало
  model-download:
    build:
      context: .
      dockerfile: backend/Dockerfile
      target: semantic
    entrypoint: ["python", "scripts/download_model.py"]
    environment:
      HF_HUB_DISABLE_TELEMETRY: "1"
    volumes:
      - model-e5:/models/e5
    restart: "no"

  api:
    build:
      context: .
      dockerfile: backend/Dockerfile
      target: semantic
    environment:
      DATABASE_URL: ...
      CATALOG_MODE: demo
      ENABLE_DIAGNOSTICS: "true"
      SEMANTIC_MODEL_DIR: /models/e5
      HF_HUB_OFFLINE: "1"
      TOKENIZERS_PARALLELISM: "false"
    volumes:
      - model-e5:/models/e5
    depends_on:
      db:
        condition: service_healthy
      model-download:
        condition: service_completed_successfully
В volumes: добавить model-e5:.
Важно: scripts/download_model.py:18 сейчас пишет в ROOT/.private/models/e5, а не в /models/e5. Нужен минимальный патч:
# было
target = ROOT / ".private/models/e5"

# стало
target = Path(os.getenv("SEMANTIC_MODEL_DIR", ROOT / ".private/models/e5"))
Иначе named volume останется пустым. [вне референса: инфраструктурная деталь]
6.7. P1 — метрики @10
Файл: backend/app/evaluation.py, строки 8-23.
# было: ключи жёстко _at_5, параметр k игнорируется в именах
return {
    "precision_at_5": hits / k,
    "pooled_recall_at_5": hits / len(positive) if positive else 0,
    "ndcg_at_5": dcg / idcg if idcg else 0,
    "mrr_at_5": reciprocal,
}
# стало
def _score(ranked_ids, relevance, k):
    top = ranked_ids[:k]
    if any(mid not in relevance for mid in top):
        raise ValueError("All retrieved top-k materials must be judged")
    positive = {mid for mid, grade in relevance.items() if grade >= 2}
    hits = sum(mid in positive for mid in top)
    dcg = sum((2 ** relevance[mid] - 1) / math.log2(i + 2) for i, mid in enumerate(top))
    ideal = sorted(relevance.values(), reverse=True)[:k]
    idcg = sum((2**grade - 1) / math.log2(i + 2) for i, grade in enumerate(ideal))
    reciprocal = next((1 / (i + 1) for i, mid in enumerate(top) if mid in positive), 0)
    return {
        f"precision_at_{k}": hits / k,
        f"pooled_recall_at_{k}": hits / len(positive) if positive else 0,
        f"ndcg_at_{k}": dcg / idcg if idcg else 0,
        f"mrr_at_{k}": reciprocal,
    }


def metrics(ranked_ids, relevance, k=5):
    result = _score(ranked_ids, relevance, 5)
    result.update(_score(ranked_ids, relevance, 10))
    return result
Фронт frontend/app/page.tsx:395 сейчас читает precision_at_5/ndcg_at_5/mrr_at_5 — @10 можно добавить колонками, не ломая старые.
6.8. P1 — judge-цикл
Файл: backend/app/llm.py, после interpret (строка 123).
# стало: тот же privacy-контур, что у interpret; судья не видит имя алгоритма
from typing import Literal

class JudgeItem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    material_id: str
    relevant: Literal["yes", "partial", "no"]
    why: str = Field(max_length=300)
    confidence: float = Field(ge=0, le=1)


class JudgeVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    items: list[JudgeItem]
Промт: только query, title, description, why; не передавать профиль, историю, каталожные тела и имя алгоритма. Один retry, если средняя релевантность <3/5. По политике проекта — только LLM_MODE=local, без внешнего API.
6.9. P1 — профилизатор и learning path
Файл: backend/app/models.py, после Profile (строка 16).
# стало
class InferredProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stage: Literal["idea", "start", "growth"] | None = None
    industry: str | None = Field(default=None, max_length=100)
    task: str | None = Field(default=None, max_length=100)
    experience: Literal["beginner", "experienced"] | None = None
    inferred: list[str] = Field(default_factory=list)
В Route добавить inferred_profile: InferredProfile | None = None. Заполнять только на сервере из interpret, не принимать от клиента.
Новый файл: backend/app/recommendation/route.py — build_learning_path(candidates, stage, limit=3); порядок: диагностика → действие → закрепление. [вне референса: конкретный порядок фаз — инженерное решение; теория требует объяснения порядка, а не конкретной последовательности]
7. Обновлённые requirements.txt и compose.yaml
7.1. backend/requirements.in
fastapi
uvicorn
sqlalchemy
psycopg[binary]
scikit-learn
httpx
pytest
ruff
rank-bm25==0.2.2
Пересобрать lock:
uv pip compile backend/requirements.in --python-version 3.13 --output-file backend/requirements.txt
В backend/requirements.txt появится:
rank-bm25==0.2.2
    # via -r backend/requirements.in
rank-bm25 — чистый Python, без torch, к default-образу добавляет копейки.
7.2. Опциональный reranker
Не добавлять в default. Отдельный файл backend/requirements-rerank.in:
-r requirements-semantic.txt
sentence-transformers==6.3.0
uv pip compile backend/requirements-rerank.in --python-version 3.13 \
  --output-file backend/requirements-rerank.txt
Этот файл тянет torch (~2 ГБ) — только для GPU/отдельного profile. [вне референса: выбор библиотеки; теория называет модель BAAI/bge-reranker-v2-m3, но не библиотеку]
7.3. compose.yaml — фрагмент
name: hackandchange
services:
  db:
    image: postgres:18@sha256:5a5a84b19854a9ffaa54082c166ff4ec27473a361e496e5ea167f298f2da9722
    environment:
      POSTGRES_DB: route
      POSTGRES_USER: route
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-local-demo-only}
    volumes:
      - route-db:/var/lib/postgresql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U route -d route"]
      interval: 5s
      timeout: 3s
      retries: 20
    restart: unless-stopped

  model-download:
    build:
      context: .
      dockerfile: backend/Dockerfile
      target: semantic
    entrypoint: ["python", "scripts/download_model.py"]
    environment:
      HF_HUB_DISABLE_TELEMETRY: "1"
    volumes:
      - model-e5:/models/e5
    restart: "no"

  api:
    build:
      context: .
      dockerfile: backend/Dockerfile
      target: semantic
    environment:
      DATABASE_URL: postgresql+psycopg://route:${POSTGRES_PASSWORD:-local-demo-only}@db:5432/route
      CATALOG_MODE: demo
      ENABLE_DIAGNOSTICS: "true"
      SEMANTIC_MODEL_DIR: /models/e5
      HF_HUB_OFFLINE: "1"
      HF_HUB_DISABLE_TELEMETRY: "1"
      TOKENIZERS_PARALLELISM: "false"
    volumes:
      - model-e5:/models/e5
    depends_on:
      db:
        condition: service_healthy
      model-download:
        condition: service_completed_successfully
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/ready')"]
      interval: 5s
      timeout: 5s
      start_period: 180s
      retries: 60
    restart: unless-stopped

  web:
    build:
      context: .
      dockerfile: frontend/Dockerfile
      args:
        API_ORIGIN: http://api:8000
    ports:
      - "127.0.0.1:${WEB_PORT:-3080}:3000"
    depends_on:
      api:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "node", "-e", "fetch('http://127.0.0.1:3000/api/ready').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"]
      interval: 10s
      timeout: 5s
      retries: 12
    restart: unless-stopped

volumes:
  route-db:
  model-e5:
Компромисс, если нельзя менять default: оставить compose.semantic.yaml и сделать его единственной командой в README/демо:
docker compose -f compose.yaml -f compose.semantic.yaml --profile models up --build
Но тогда жюри должно запускать именно эту команду — иначе снова увидит TF-IDF.
8. Что НЕ надо менять
1. Privacy-контур llm.py:60-77 — LLM_MODE=off по умолчанию, запрет внешнего API без LLM_ALLOW_EXTERNAL=true, запрет redirects, timeout 8 с, лимит ответа 32 КБ. Это сильная часть проекта.
2. Pydantic-валидацию — extra="forbid", protect_content (только synthetic + free), safe_url, лимиты query/limit/feedback. Не ослаблять ради «гибкости».
3. Жёсткие ограничения доступа/платности/отрицаний в eligibility.py — кроме anchor-gate и task-evidence. Правила excluded_format, unrequested_specialization, no_franchise, no_employees, opposite_action действительно защищают от мусора.
4. Независимость baseline — parse_intent(baseline=True), отсутствие профиля/истории, одинаковый каталог и фильтры. Не подмешивать персональные веса в baseline.
5. Feedback-исключения — completed/known/not_relevant должны и дальше исключаться. Не превращать их в положительную память.
6. Docker/README/healthchecks/тесты — 160 passed, 1 skipped; структура compose и healthcheck-и рабочие. Не переписывать инфраструктуру ради патчей.
7. Whole-card indexing без чанкинга — карточки 69–100 символов; чанкинг здесь только навредит. Это не тот случай, где нужен RAG по длинным документам.
8. API-контракт — только additive-поля (why, next_step, confidence). Не переименовывать reasons, next_action, signals, match_scope.
9. DEMO provenance — synthetic-only, без реального каталога, платных тел и .private в публичном образе.
9. Открытые вопросы
1. Есть ли доступ к .private и полному каталогу 1473 материалов? Сейчас retrieval проверен на 36 DEMO-карточках; на полном каталоге поведение фильтров может отличаться.
2. Можно ли включать внешний LLM API? Если нет — обогащение и judge только через локальную Qwen, это медленнее и требует отдельного прогона.
3. Есть ли GPU/время на BGE-M3 и bge-reranker-v2-m3? На CPU reranker может добавить секунды к p95; тогда он остаётся P2.
4. Кто разметит 50–100 пар? Сейчас 32 профиля / 51 пара / 0 human labels. Без меток Recall@10/NDCG@10 нельзя выдавать за финальные.
5. Можно ли менять DEMO-каталог или добавлять enriched-файл? Если только код — LLM-обогащение делается отдельным JSON и не коммитится.
6. Согласен ли владелец на E5 в default compose? Это меняет размер образа, время первого старта и правило «семантическая модель опциональна, пока не проверена».
7. Какой целевой p95 latency? Для демо на 36 карточках 300–500 мс нормально; для полного каталога нужен отдельный бюджет.
Что делать в первые 2–3 часа
1. P0-2 + P0-3 — снять anchor-gate и добавить семейства задач.
2. P0-1 — убрать ранний clarification, вернуть карточки + вопрос.
3. Прогнать 16 natural-запросов и три сценария; зафиксировать числа до/после.
4. P0-5 — добавить why/next_step/confidence.
5. P0-4 — BM25+RRF, если остаётся время.
6. P0-6 — включить E5 в default и проверить /api/bootstrap.
После каждого шага: pytest -q, ruff check, docker compose config -q. Live Docker в этом окружении недоступен, поэтому финальную проверку docker compose up --build нужно делать на машине с daemon.
