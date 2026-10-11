from time import perf_counter
from typing import Literal

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel

REQUEST_COUNT = Counter("gamesense_requests_total", "Total HTTP requests served", ["route"])
RECOMMENDATION_LATENCY = Histogram("gamesense_recommendation_seconds", "Recommendation response latency")

app = FastAPI(title="GameSense API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RecommendationRequest(BaseModel):
    mode: Literal["similar", "trending", "cozy", "competitive"] = "trending"
    favorite_game: str | None = None


@app.get("/health")
def health() -> dict[str, str]:
    REQUEST_COUNT.labels(route="/health").inc()
    return {"status": "ok", "service": "gamesense-api"}


@app.post("/api/recommendations")
def recommendations(payload: RecommendationRequest) -> dict[str, object]:
    start = perf_counter()
    REQUEST_COUNT.labels(route="/api/recommendations").inc()
    catalog = {
        "similar": ["Hades", "Dead Cells", "Risk of Rain 2"],
        "trending": ["Baldur's Gate 3", "Helldivers 2", "Palworld"],
        "cozy": ["Stardew Valley", "Dave the Diver", "Spiritfarer"],
        "competitive": ["Counter-Strike 2", "Dota 2", "Apex Legends"],
    }
    result = {
        "mode": payload.mode,
        "favoriteGame": payload.favorite_game,
        "recommendations": catalog[payload.mode],
        "explanation": "Starter rules-based response for local demos; replace with Steam data and model scoring in later slices.",
    }
    RECOMMENDATION_LATENCY.observe(perf_counter() - start)
    return result


@app.get("/metrics")
def metrics() -> Response:
    REQUEST_COUNT.labels(route="/metrics").inc()
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
