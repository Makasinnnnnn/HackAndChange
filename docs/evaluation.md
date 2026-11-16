# Оценка релевантности

Основной инструмент: `scripts/evaluate.py`, градуированная шкала 0–3. Для текущего FULL1476/e4dc26acca5e0e25 подготовлен пул 32 профиля/51 пара; человеческих меток 0, метрики null. Подробные реальные capture и заполненные CSV хранятся только в `.private/`.

```powershell
.venv/Scripts/python.exe scripts/evaluate.py prepare --full --semantic --directory .private/evaluation-new
.venv/Scripts/python.exe scripts/evaluate.py calculate --directory .private/evaluation-new
```

Для semantic предварительно задайте SEMANTIC_MODEL_DIR и установите semantic-зависимости. `prepare` формирует слепой объединённый пул обоих алгоритмов; `calculate` требует совместимую разметку с явными label_source=human и автором. Не перезаписывайте прежнюю работу и не переносите метки между версиями каталога/алгоритма автоматически.

Оцениваются P@5 при grade≥2, pooled Recall@5, nDCG@5 с gain=2^grade−1 и MRR@5. Recall относится к размеченному пулу, не ко всему каталогу. Фиксированный dev/test split не гарантирует независимость: набор, использованный для настройки, становится регрессией. Отложенные запросы и оценщики для независимого теста должны быть новыми.

Дополнительная бинарная CSV-диагностика — [audit/score_blind_eval.py](../audit/score_blind_eval.py), методика [здесь](../audit/blind_eval_queries.md). Её цифры не смешиваются с градуированным оценщиком. Внутренние score и косинус E5 не являются измеренной точностью.

Разбор 150 запросов и повтор 120 выполнены при отладке. Это оценки разработчика/AI по метаданным, не человеческие метки, не независимый holdout и не доказательство роста конверсии. План онлайн-проверки — [product-metrics.md](product-metrics.md).
