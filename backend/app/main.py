import os
from time import perf_counter

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db import database_is_ready, get_session
from app.models import SavedGame
from app.recommender_service import active_catalog_count_for_api, active_game_by_slug_for_api, list_games_for_api, recommend_for_api
from app.schemas import (
    GameOut,
    HealthResponse,
    ReadinessResponse,
    RecommendationRequest,
    RecommendationResponse,
    SavedGameInput,
    SavedGameOut,
)

REQUEST_COUNT = Counter(
    "gamesense_http_requests",
    "Total HTTP requests served by the GameSense API",
    ["method", "route", "status_code"],
)
REQUEST_LATENCY = Histogram(
    "gamesense_http_request_duration_seconds",
    "HTTP request duration for the GameSense API",
    ["method", "route"],
)
RECOMMENDATION_LATENCY = Histogram(
    "gamesense_recommendation_seconds",
    "Recommendation response latency for the recommendation endpoint",
)
RECOMMENDATION_REQUESTS = Counter(
    "gamesense_recommendation_requests",
    "Recommendation endpoint requests by bounded recommender metadata",
    ["mode", "algorithm", "version", "data_snapshot"],
)
RECOMMENDATION_FALLBACKS = Counter(
    "gamesense_recommendation_fallbacks",
    "Recommendation fallbacks by bounded reason and target algorithm",
    ["reason", "algorithm"],
)
RECOMMENDATION_MODEL_INFO = Gauge(
    "gamesense_recommendation_model_info",
    "Static info gauge for the active recommendation algorithm and version",
    ["algorithm", "version", "data_snapshot"],
)
RECOMMENDATION_CATALOG_ITEMS = Gauge(
    "gamesense_recommendation_catalog_items",
    "Catalog items visible to the active recommendation mode",
    ["algorithm", "data_snapshot"],
)
DEMO_CATALOG_GAMES = Gauge(
    "gamesense_demo_catalog_games",
    "Active records in the hand-written demo fixture catalog",
)


def _allowed_origins() -> list[str]:
    configured = os.getenv("CORS_ALLOWED_ORIGINS")
    if configured:
        return [origin.strip() for origin in configured.split(",") if origin.strip()]
    return ["http://localhost:5173", "http://localhost:3000"]


app = FastAPI(title="GameSense API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def record_http_metrics(request: Request, call_next):
    start = perf_counter()
    response = await call_next(request)
    route = request.scope.get("route")
    route_path = getattr(route, "path", request.url.path)
    REQUEST_COUNT.labels(
        method=request.method,
        route=route_path,
        status_code=str(response.status_code),
    ).inc()
    REQUEST_LATENCY.labels(method=request.method, route=route_path).observe(perf_counter() - start)
    return response


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="gamesense-api")


@app.get("/ready", response_model=ReadinessResponse)
def ready(session: Session = Depends(get_session)) -> ReadinessResponse:
    database_is_ready(session)
    count = active_catalog_count_for_api(session)
    DEMO_CATALOG_GAMES.set(count)
    return ReadinessResponse(
        status="ok",
        service="gamesense-api",
        database="ok",
        demoCatalogItems=count,
    )


@app.get("/api/games", response_model=list[GameOut])
def games(limit: int = 500, offset: int = 0, q: str | None = None, session: Session = Depends(get_session)) -> list[GameOut]:
    catalog = list_games_for_api(session, limit=max(1, min(limit, 1000)), offset=max(0, offset), query=q)
    DEMO_CATALOG_GAMES.set(len(catalog))
    return catalog


@app.get("/api/saved-games", response_model=list[SavedGameOut])
def saved_games(session: Session = Depends(get_session)) -> list[SavedGameOut]:
    return [SavedGameOut(slug=row.slug, note=row.note) for row in session.scalars(select(SavedGame).order_by(SavedGame.slug))]


@app.put("/api/saved-games/{slug}", response_model=SavedGameOut)
def save_game(slug: str, payload: SavedGameInput, session: Session = Depends(get_session)) -> SavedGameOut:
    if active_game_by_slug_for_api(session, slug) is None:
        raise HTTPException(status_code=404, detail="Game is not in the active catalog")
    row = session.get(SavedGame, slug)
    if row is None:
        row = SavedGame(slug=slug, note=payload.note)
        session.add(row)
    else:
        row.note = payload.note
    session.commit()
    return SavedGameOut(slug=row.slug, note=row.note)


@app.delete("/api/saved-games/{slug}", status_code=204)
def delete_saved_game(slug: str, session: Session = Depends(get_session)) -> Response:
    row = session.get(SavedGame, slug)
    if row is None:
        raise HTTPException(status_code=404, detail="Saved game not found")
    session.delete(row)
    session.commit()
    return Response(status_code=204)


@app.post("/api/recommendations", response_model=RecommendationResponse)
def recommendations(
    payload: RecommendationRequest,
    session: Session = Depends(get_session),
) -> RecommendationResponse:
    start = perf_counter()
    result = recommend_for_api(session, mode=payload.mode, favorite_game=payload.favorite_game, limit=payload.limit)
    visible_catalog_count = active_catalog_count_for_api(session)
    DEMO_CATALOG_GAMES.set(visible_catalog_count)
    RECOMMENDATION_CATALOG_ITEMS.labels(algorithm=result.algorithm, data_snapshot=result.dataSnapshot).set(result.catalogItems)
    RECOMMENDATION_MODEL_INFO.labels(
        algorithm=result.algorithm,
        version=result.version,
        data_snapshot=result.dataSnapshot,
    ).set(1)
    RECOMMENDATION_REQUESTS.labels(
        mode=payload.mode,
        algorithm=result.algorithm,
        version=result.version,
        data_snapshot=result.dataSnapshot,
    ).inc()
    if result.fallbackReason != "none":
        RECOMMENDATION_FALLBACKS.labels(reason=result.fallbackReason, algorithm=result.algorithm).inc()
    RECOMMENDATION_LATENCY.observe(perf_counter() - start)
    return RecommendationResponse(
        mode=payload.mode,
        favoriteGame=payload.favorite_game,
        recommendations=result.recommendations,
        explanation=result.explanation,
        fixtureNotice=result.fixtureNotice,
        algorithm=result.algorithm,
        version=result.version,
        dataSnapshot=result.dataSnapshot,
        disclosure=result.disclosure,
    )


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
