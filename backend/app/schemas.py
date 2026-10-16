from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

RecommendationMode = Literal["similar", "trending", "cozy", "competitive"]


class RecommendationRequest(BaseModel):
    mode: RecommendationMode = "trending"
    favorite_game: str | None = Field(default=None, max_length=240)
    limit: int = Field(default=3, ge=1, le=12)


class GameOut(BaseModel):
    slug: str
    title: str
    shortDescription: str
    genres: list[str]
    source: str
    reason: str
    steamAppId: str | None = None
    imageUrl: str | None = None
    imageFallbackUrl: str | None = None


class SavedGameInput(BaseModel):
    note: str = Field(default="", max_length=500)


class SavedGameOut(BaseModel):
    slug: str
    note: str


class RecommendationResponse(BaseModel):
    mode: RecommendationMode
    favoriteGame: str | None
    recommendations: list[GameOut]
    explanation: str
    fixtureNotice: str
    algorithm: str
    version: str
    dataSnapshot: str
    disclosure: str


class HealthResponse(BaseModel):
    status: str
    service: str


class ReadinessResponse(HealthResponse):
    database: str
    demoCatalogItems: int


class SourceManifestProvenance(BaseModel):
    origin: str = Field(min_length=1)
    sourceType: Literal["self-authored", "public-dataset", "api", "scrape", "vendor", "other"]
    collectedBy: str = Field(min_length=1)
    collectionMethod: str = Field(min_length=1)
    notes: str | None = None


class SourceManifestLicenseAndTerms(BaseModel):
    licenseName: str = Field(min_length=1)
    termsUrl: str | None
    redistributionAllowed: bool
    trainingAllowed: bool
    commercialUseAllowed: bool
    uncertainties: list[str]


class SourceManifestAttribution(BaseModel):
    required: bool
    text: str


class SourceManifestAllowedUses(BaseModel):
    commitToRepository: bool
    localDevelopment: bool
    ci: bool
    training: bool
    evaluation: bool
    serving: bool
    notes: str | None = None


class SourceManifestContentHash(BaseModel):
    algorithm: Literal["sha256"]
    value: str = Field(pattern="^[a-f0-9]{64}$")


class SourceManifestRetrieval(BaseModel):
    retrievedAt: str
    version: str = Field(min_length=1)
    uri: str | None
    contentHash: SourceManifestContentHash


class SourceManifestReview(BaseModel):
    state: Literal["draft", "needs-legal-review", "approved", "rejected"]
    reviewedBy: str | None
    reviewedAt: str | None
    notes: str


class CatalogSourceSchema(BaseModel):
    """Canonical source manifest shape persisted by the catalog_sources table."""

    manifestVersion: Literal[1]
    sourceId: str = Field(pattern="^[a-z0-9][a-z0-9._-]*$")
    name: str = Field(min_length=1)
    provenance: SourceManifestProvenance
    licenseAndTerms: SourceManifestLicenseAndTerms
    attribution: SourceManifestAttribution
    allowedUses: SourceManifestAllowedUses
    retrieval: SourceManifestRetrieval
    review: SourceManifestReview


class CatalogGameSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    sourceId: str = Field(pattern="^[a-z0-9][a-z0-9._-]*$")
    sourceGameId: str = Field(min_length=1, max_length=160)
    slug: str = Field(pattern="^[a-z0-9][a-z0-9._-]*$", max_length=160)
    title: str = Field(min_length=1, max_length=240)
    description: str | None = None
    genres: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    platforms: list[str] = Field(default_factory=list)
    releaseDate: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    isActive: bool = True


class GameFeatureSchema(BaseModel):
    gameSlug: str = Field(pattern="^[a-z0-9][a-z0-9._-]*$", max_length=160)
    featureVersion: str = Field(min_length=1, max_length=80)
    textFeatures: dict[str, Any] = Field(default_factory=dict)
    categoricalFeatures: dict[str, Any] = Field(default_factory=dict)
    numericFeatures: dict[str, float | int] = Field(default_factory=dict)
    vectorFeatures: dict[str, list[float]] | None = None


class RecommendationArtifactSchema(BaseModel):
    artifactId: str = Field(pattern="^[a-z0-9][a-z0-9._-]*$", max_length=160)
    artifactType: Literal["baseline", "features", "model", "index", "evaluation"]
    sourceId: str | None = Field(default=None, pattern="^[a-z0-9][a-z0-9._-]*$")
    featureVersion: str | None = Field(default=None, max_length=80)
    artifactUri: str | None = Field(default=None, max_length=500)
    trainingSourceIds: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, float | int | str] = Field(default_factory=dict)
    manifest: dict[str, Any] = Field(default_factory=dict)
    status: Literal["registered", "validated", "deprecated"] = "registered"
