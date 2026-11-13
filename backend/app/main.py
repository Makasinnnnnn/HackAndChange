from __future__ import annotations

import json
import logging
import os
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .catalog import load_catalog
from .engine import Engine
from .llm import interpret
from .models import FeedbackRequest, HistoryImportRequest, Profile, RecommendationRequest
from .semantic import optional_encoder
from .storage import Learner, Signal, make_engine, signals

http_log = logging.getLogger("route.http")
http_log.setLevel(logging.INFO)
if not http_log.handlers:
    http_log.addHandler(logging.StreamHandler())


@asynccontextmanager
async def lifespan(app: FastAPI):
    materials, mode, version = load_catalog()
    semantic, fallback_reason = optional_encoder()
    try:
        app.state.recommender = Engine(materials, mode, version, semantic=semantic)
    except Exception:
        if semantic is None:
            raise
        app.state.recommender = Engine(materials, mode, version)
        fallback_reason = "local_model_index_unavailable"
    app.state.semantic_fallback = fallback_reason
    app.state.db = make_engine(os.getenv("DATABASE_URL", "sqlite:///./.private/app.db"))
    yield
    app.state.db.dispose()


app = FastAPI(
    title="Альфа-Маршрут",
    version="1.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
)


@app.exception_handler(SQLAlchemyError)
async def database_unavailable(request: Request, exc: SQLAlchemyError):
    return JSONResponse(
        status_code=503, content={"detail": "Хранилище временно недоступно. Повторите запрос позже."}
    )


@app.middleware("http")
async def boundaries(request: Request, call_next):
    started = time.perf_counter()
    size = request.headers.get("content-length", "0")
    try:
        if int(size) > 16384:
            return Response("Request too large", status_code=413)
    except ValueError:
        return Response("Invalid content length", status_code=400)
    # Same-origin JSON writes; API and UI are proxied through the same local origin.
    if (
        request.method in {"POST", "PATCH", "DELETE"}
        and request.headers.get("sec-fetch-site") == "cross-site"
    ):
        return Response("Cross-site write rejected", status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    route = request.scope.get("route")
    http_log.info(
        json.dumps(
            {
                "event": "http_request",
                "method": request.method,
                "route": getattr(route, "path", "unmatched"),
                "status": response.status_code,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            },
            ensure_ascii=False,
        )
    )
    return response


def database(request: Request):
    with Session(request.app.state.db) as session:
        yield session


def learner(request: Request, response: Response, db: Session = Depends(database)):
    token = request.cookies.get("route_session", "")
    record = db.get(Learner, token) if len(token) == 48 else None
    if record is None:
        token = secrets.token_hex(24)
        record = Learner(id=token, profile={}, last_query="")
        db.add(record)
        db.commit()
        response.set_cookie(
            "route_session",
            token,
            httponly=True,
            samesite="strict",
            max_age=60 * 60 * 24 * 30,
            secure=os.getenv("COOKIE_SECURE", "false") == "true",
        )
    return record


def recommender(request: Request) -> Engine:
    return request.app.state.recommender


@app.get("/api/health")
def health():
    return {"status": "ok", "version": app.version}


@app.get("/api/ready")
def ready(db: Session = Depends(database), engine: Engine = Depends(recommender)):
    db.execute(text("SELECT 1"))
    if not engine.materials:
        raise HTTPException(503, "Catalog is empty")
    return {
        "status": "ready",
        "catalog_mode": engine.mode,
        "materials": len(engine.materials),
        "catalog_version": engine.version,
    }


@app.get("/api/bootstrap")
def bootstrap(
    user: Learner = Depends(learner), db: Session = Depends(database), engine: Engine = Depends(recommender)
):
    return {
        "profile": Profile.model_validate(user.profile).model_dump(),
        "query": user.last_query,
        "signals": {mid: value for mid, value in signals(db, user.id).items() if mid in engine.by_id},
        "catalog_mode": engine.mode,
        "catalog_count": len(engine.materials),
        "catalog_version": engine.version,
        "semantic_model": engine.semantic.model_id if engine.semantic else None,
        "semantic_fallback": engine.semantic is None,
        "llm_enabled": os.getenv("LLM_MODE", "off") in {"local", "api"},
        "llm_external": os.getenv("LLM_MODE") == "api",
        "industries": sorted({industry for m in engine.materials for industry in m.industries}),
    }


@app.post("/api/recommendations")
def recommendations(
    body: RecommendationRequest,
    user: Learner = Depends(learner),
    db: Session = Depends(database),
    engine: Engine = Depends(recommender),
):
    user.profile = body.profile.model_dump()
    user.last_query = body.query.strip()
    db.commit()
    return engine.recommend(body.query, body.profile, signals(db, user.id), body.limit)


@app.post("/api/intent")
def intent_assistant(body: RecommendationRequest):
    intent, status = interpret(body.query)
    return {"status": status, "intent": intent.model_dump() if intent else None}



@app.post("/api/recommendations/baseline")
def baseline(body: RecommendationRequest, engine: Engine = Depends(recommender)):
    return engine.recommend(body.query, limit=body.limit, baseline=True)


@app.get("/api/catalog")
def catalog(
    q: str = Query(default="", max_length=150),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    engine: Engine = Depends(recommender),
):
    items = [m for m in engine.materials if q.casefold() in (m.title + " " + m.description).casefold()]
    return {
        "total": len(items),
        "items": [m.model_dump(exclude={"demo_content"}) for m in items[offset : offset + limit]],
        "catalog_mode": engine.mode,
    }


@app.get("/api/catalog/{material_id}")
def material(material_id: str, engine: Engine = Depends(recommender)):
    item = engine.by_id.get(material_id)
    if item is None:
        raise HTTPException(404, "Материал не найден")
    return item


@app.post("/api/feedback")
def feedback(
    body: FeedbackRequest,
    user: Learner = Depends(learner),
    db: Session = Depends(database),
    engine: Engine = Depends(recommender),
):
    if body.material_id not in engine.by_id:
        raise HTTPException(404, "Материал не найден")
    record = db.scalar(
        select(Signal).where(Signal.learner_id == user.id, Signal.material_id == body.material_id)
    )
    if body.signal == "reset":
        if record:
            db.delete(record)
    elif record:
        record.value = body.signal
    else:
        db.add(Signal(learner_id=user.id, material_id=body.material_id, value=body.signal))
    db.commit()
    return {"saved": True, "signals": signals(db, user.id)}


@app.post("/api/history/import")
def import_history(
    body: HistoryImportRequest,
    user: Learner = Depends(learner),
    db: Session = Depends(database),
    engine: Engine = Depends(recommender),
):
    if body.catalog_version != engine.version:
        raise HTTPException(409, "История подготовлена для другой версии каталога")
    if any(mid not in engine.by_id or engine.by_id[mid].source_type != "course" for mid in body.completed_material_ids):
        raise HTTPException(422, "История содержит неизвестные материалы или не курсы")
    for mid in body.completed_material_ids:
        record = db.scalar(select(Signal).where(Signal.learner_id == user.id, Signal.material_id == mid))
        if record:
            record.value = "completed"
        else:
            db.add(Signal(learner_id=user.id, material_id=mid, value="completed"))
    db.commit()
    return {"imported": len(body.completed_material_ids), "signals": signals(db, user.id)}


@app.get("/api/progress")
def progress(
    user: Learner = Depends(learner), db: Session = Depends(database), engine: Engine = Depends(recommender)
):
    history = signals(db, user.id)
    return {
        "items": [
            {"material": engine.by_id[mid].model_dump(exclude={"demo_content"}), "signal": signal}
            for mid, signal in history.items()
            if mid in engine.by_id
        ],
        "profile": Profile.model_validate(user.profile).model_dump(),
    }


@app.get("/api/demo/profiles")
def demo_profiles():
    return json.loads((Path(__file__).parents[1] / "data/profiles.json").read_text(encoding="utf-8"))


@app.post("/api/demo/compare")
def compare(
    body: RecommendationRequest,
    user: Learner = Depends(learner),
    db: Session = Depends(database),
    engine: Engine = Depends(recommender),
):
    if os.getenv("ENABLE_DIAGNOSTICS", "true") != "true":
        raise HTTPException(404)
    return {
        "baseline": engine.recommend(body.query, limit=body.limit, baseline=True),
        "personal": engine.recommend(body.query, body.profile, signals(db, user.id), body.limit),
        "note": "Одинаковые запрос и каталог. Baseline не использует профиль и историю. Баллы разных алгоритмов напрямую несравнимы. Это сравнение выдачи, а не доказательство качества или роста конверсии.",
    }


@app.get("/api/evaluation/results")
def evaluation(engine: Engine = Depends(recommender)):
    result_path = os.getenv("EVALUATION_PATH")
    if result_path and Path(result_path).is_file():
        result = json.loads(Path(result_path).read_text(encoding="utf-8"))
        if (
            result.get("catalog_version") == engine.version
            and result.get("algorithm_version") == engine.algorithm_id
        ):
            return result
        return {
            "status": "stale_catalog",
            "metrics": None,
            "note": "Каталог изменился. Требуется повторный расчёт оценки.",
        }
    return {
        "status": "awaiting_human_judgments",
        "metrics": None,
        "note": "Экспертные метки ещё не получены. Метрики качества не рассчитаны; сравнение выдачи доступно в деморежиме.",
    }
