from typing import Literal

from pydantic import BaseModel, Field

RecommendationMode = Literal["similar", "trending", "cozy", "competitive"]


class RecommendationRequest(BaseModel):
    mode: RecommendationMode = "trending"
    favorite_game: str | None = Field(default=None, max_length=120)


class GameOut(BaseModel):
    slug: str
    title: str
    shortDescription: str
    genres: list[str]
    source: str
    reason: str


class RecommendationResponse(BaseModel):
    mode: RecommendationMode
    favoriteGame: str | None
    recommendations: list[GameOut]
    explanation: str
    fixtureNotice: str


class HealthResponse(BaseModel):
    status: str
    service: str


class ReadinessResponse(HealthResponse):
    database: str
    demoCatalogItems: int
