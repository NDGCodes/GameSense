import os
from time import perf_counter

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.catalog import list_active_games, to_game_out
from app.db import database_is_ready, get_session
from app.models import Game
from app.recommender_service import recommend_for_api
from app.schemas import (
    GameOut,
    HealthResponse,
    ReadinessResponse,
    RecommendationRequest,
    RecommendationResponse,
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
    "Recommendation response latency for the rules-based demo endpoint",
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
    count = session.scalar(select(func.count()).select_from(Game).where(Game.is_active.is_(True))) or 0
    DEMO_CATALOG_GAMES.set(count)
    return ReadinessResponse(
        status="ok",
        service="gamesense-api",
        database="ok",
        demoCatalogItems=count,
    )


@app.get("/api/games", response_model=list[GameOut])
def games(session: Session = Depends(get_session)) -> list[GameOut]:
    catalog = list_active_games(session)
    DEMO_CATALOG_GAMES.set(len(catalog))
    return [to_game_out(game) for game in catalog]


@app.post("/api/recommendations", response_model=RecommendationResponse)
def recommendations(
    payload: RecommendationRequest,
    session: Session = Depends(get_session),
) -> RecommendationResponse:
    start = perf_counter()
    result = recommend_for_api(session, mode=payload.mode, favorite_game=payload.favorite_game)
    DEMO_CATALOG_GAMES.set(session.scalar(select(func.count()).select_from(Game).where(Game.is_active.is_(True))) or 0)
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
