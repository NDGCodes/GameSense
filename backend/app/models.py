from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


class Game(Base):
    """Hand-written demo fixture table used by the existing API.

    Milestone 1 adds canonical catalog tables below without changing this table
    or the current fixture-backed API behavior.
    """

    __tablename__ = "demo_games"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    short_description: Mapped[str] = mapped_column(Text, nullable=False)
    genres: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    modes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    demo_reason: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="demo-fixture")
    popularity_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class CatalogSource(Base):
    __tablename__ = "catalog_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    manifest_version: Mapped[int] = mapped_column(Integer, nullable=False)
    manifest_uri: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    provenance: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    license_and_terms: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    attribution: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    allowed_uses: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    retrieval: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    review: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    games: Mapped[list["CatalogGame"]] = relationship(back_populates="source")
    recommendation_artifacts: Mapped[list["RecommendationArtifact"]] = relationship(back_populates="source")


class CatalogGame(Base):
    __tablename__ = "games"
    __table_args__ = (UniqueConstraint("source_pk", "source_game_id", name="uq_games_source_source_game_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_pk: Mapped[int] = mapped_column(ForeignKey("catalog_sources.id"), index=True, nullable=False)
    source_game_id: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(160), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    genres: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    platforms: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    release_date: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column("metadata", JSON, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    source: Mapped[CatalogSource] = relationship(back_populates="games")
    features: Mapped[list["GameFeature"]] = relationship(back_populates="game")


class GameFeature(Base):
    __tablename__ = "game_features"
    __table_args__ = (UniqueConstraint("game_id", "feature_version", name="uq_game_features_game_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), index=True, nullable=False)
    feature_version: Mapped[str] = mapped_column(String(80), nullable=False)
    text_features: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    categorical_features: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    numeric_features: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    vector_features: Mapped[Optional[dict[str, object]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    game: Mapped[CatalogGame] = relationship(back_populates="features")


class RecommendationArtifact(Base):
    __tablename__ = "recommendation_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    artifact_id: Mapped[str] = mapped_column(String(160), unique=True, index=True, nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_pk: Mapped[Optional[int]] = mapped_column(ForeignKey("catalog_sources.id"), index=True, nullable=True)
    feature_version: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    artifact_uri: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    training_source_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    parameters: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    metrics: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    manifest: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="registered")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    source: Mapped[Optional[CatalogSource]] = relationship(back_populates="recommendation_artifacts")
