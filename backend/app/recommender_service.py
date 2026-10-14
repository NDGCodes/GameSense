from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.catalog import FIXTURE_NOTICE, MODE_EXPLANATIONS, list_active_games, recommend_games, to_game_out
from app.models import Game
from app.ml_bundle import BundleError, LoadedContentBundle, load_content_bundle
from app.recommender import (
    BASELINE_RECOMMENDER_VERSION,
    BaselineRecommendationMode,
    recommend_baseline,
    recommend_prefit_content,
)
from app.schemas import CatalogGameSchema, GameOut, RecommendationMode

RecommenderMode = Literal["fixture", "content"]

FIXTURE_ALGORITHM = "demo-fixture-rules"
FIXTURE_VERSION = "gamesense-demo-fixture-rules-v1"
FIXTURE_DATA_SNAPSHOT = "demo-database-fixtures"
CONTENT_ALGORITHM = "content-baseline-rrf"
CONTENT_DATA_SNAPSHOT = "gamesense-ml-self-authored-smoke-v1"
CONTENT_DISCLOSURE = (
    "Content mode uses only the tiny self-authored smoke fixture committed in this repository. "
    "It does not use a real Steam catalog, external Kaggle data, trained embeddings, or production accuracy claims."
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONTENT_FIXTURE = Path(
    os.getenv("CONTENT_FIXTURE_PATH", str(_REPO_ROOT / "data/fixtures/ml/sample_games.self-authored.json"))
)
_SOURCE_ID = "gamesense-self-authored-smoke-fixture"
_BUNDLE_CACHE: tuple[str, LoadedContentBundle] | None = None


@dataclass(frozen=True)
class RecommendationServiceResult:
    recommendations: list[GameOut]
    explanation: str
    fixtureNotice: str
    algorithm: str
    version: str
    dataSnapshot: str
    disclosure: str
    catalogItems: int
    fallbackReason: str = "none"


def get_recommender_mode() -> RecommenderMode:
    value = os.getenv("RECOMMENDER_MODE", "fixture").strip().lower()
    return "content" if value == "content" else "fixture"


def recommend_for_api(
    session: Session,
    *,
    mode: RecommendationMode,
    favorite_game: str | None,
    limit: int = 3,
) -> RecommendationServiceResult:
    if get_recommender_mode() == "content":
        bundle = _load_configured_bundle()
        if bundle is not None:
            return _bundle_recommendations(bundle, mode=mode, favorite_game=favorite_game, limit=limit)
        return _content_recommendations(mode=mode, favorite_game=favorite_game, limit=limit)
    return _fixture_recommendations(session, mode=mode, favorite_game=favorite_game, limit=limit)


def list_games_for_api(session: Session, *, limit: int = 500, query: str | None = None) -> list[GameOut]:
    if get_recommender_mode() == "content":
        bundle = _load_configured_bundle()
        if bundle is not None:
            return _list_bundle_games(bundle, limit=limit, query=query)
        games = _load_content_games()
        return [_to_content_catalog_game_out(game) for game in _filter_catalog_games(games, limit=limit, query=query)]
    rows = [to_game_out(game) for game in list_active_games(session)]
    if query:
        normalized = query.strip().lower()
        rows = [game for game in rows if normalized in game.title.lower() or normalized in game.slug.lower()]
    return rows[:limit]


def active_catalog_count_for_api(session: Session) -> int:
    if get_recommender_mode() == "content":
        bundle = _load_configured_bundle()
        if bundle is not None:
            return len([game for game in bundle.catalog if game.isActive])
        return len([game for game in _load_content_games() if game.isActive])
    return session.scalar(select(func.count()).select_from(Game).where(Game.is_active.is_(True))) or 0


def _fixture_recommendations(
    session: Session,
    *,
    mode: RecommendationMode,
    favorite_game: str | None,
    limit: int,
) -> RecommendationServiceResult:
    return RecommendationServiceResult(
        recommendations=recommend_games(session, mode, favorite_game, limit=limit),
        explanation=MODE_EXPLANATIONS[mode],
        fixtureNotice=FIXTURE_NOTICE,
        algorithm=FIXTURE_ALGORITHM,
        version=FIXTURE_VERSION,
        dataSnapshot=FIXTURE_DATA_SNAPSHOT,
        disclosure=FIXTURE_NOTICE,
        catalogItems=session.scalar(select(func.count()).select_from(Game).where(Game.is_active.is_(True))) or 0,
    )


def clear_content_bundle_cache() -> None:
    global _BUNDLE_CACHE
    _BUNDLE_CACHE = None


def _bundle_path_from_env() -> Path | None:
    raw = os.getenv("CONTENT_BUNDLE_PATH")
    if not raw:
        return None
    return Path(raw).expanduser().resolve()


def _load_configured_bundle() -> LoadedContentBundle | None:
    global _BUNDLE_CACHE
    path = _bundle_path_from_env()
    if path is None:
        return None
    cache_key = str(path)
    if _BUNDLE_CACHE is None or _BUNDLE_CACHE[0] != cache_key:
        try:
            _BUNDLE_CACHE = (cache_key, load_content_bundle(path))
        except BundleError as exc:
            raise RuntimeError(f"Configured content bundle is invalid: {exc}") from exc
    return _BUNDLE_CACHE[1]


def _load_content_games() -> list[CatalogGameSchema]:
    fixture = json.loads(_CONTENT_FIXTURE.read_text(encoding="utf-8"))
    games: list[CatalogGameSchema] = []
    for index, record in enumerate(fixture["records"], start=1):
        games.append(
            CatalogGameSchema.model_validate(
                {
                    "sourceId": _SOURCE_ID,
                    "sourceGameId": record["id"],
                    "slug": record["id"],
                    "title": record["title"],
                    "description": record["description"],
                    "genres": record["genres"],
                    "tags": record["tags"],
                    "platforms": [],
                    "releaseDate": None,
                    "metadata": {"fixtureRow": index, "fixtureSource": fixture["source"]},
                    "isActive": True,
                }
            )
        )
    return games


def _content_recommendations(
    *,
    mode: RecommendationMode,
    favorite_game: str | None,
    limit: int,
) -> RecommendationServiceResult:
    games = _load_content_games()
    seed_slug = _resolve_seed_slug(games, favorite_game)
    fallback_reason = "similar_seed_not_found" if mode == "similar" and favorite_game and not seed_slug else "none"
    baseline_mode = _to_baseline_mode(mode, seed_slug)
    ranked = recommend_baseline(games, mode=baseline_mode, seed_slug=seed_slug, limit=limit)

    if not ranked and mode == "similar":
        fallback_reason = "similar_no_candidates"
        baseline_mode = "cozy"
        ranked = recommend_baseline(games, mode=baseline_mode, limit=limit)

    games_by_slug = {game.slug: game for game in games}
    return RecommendationServiceResult(
        recommendations=[_to_content_game_out(games_by_slug[item.slug], item) for item in ranked],
        explanation=_content_explanation(mode, baseline_mode, bool(seed_slug)),
        fixtureNotice=FIXTURE_NOTICE,
        algorithm=CONTENT_ALGORITHM,
        version=BASELINE_RECOMMENDER_VERSION,
        dataSnapshot=CONTENT_DATA_SNAPSHOT,
        disclosure=CONTENT_DISCLOSURE,
        catalogItems=len([game for game in games if game.isActive]),
        fallbackReason=fallback_reason,
    )


def _bundle_recommendations(
    bundle: LoadedContentBundle,
    *,
    mode: RecommendationMode,
    favorite_game: str | None,
    limit: int,
) -> RecommendationServiceResult:
    seed_slug = _resolve_seed_slug(bundle.catalog, favorite_game)
    fallback_reason = "similar_seed_not_found" if mode == "similar" and favorite_game and not seed_slug else "none"
    baseline_mode = _to_baseline_mode(mode, seed_slug)
    tokens_by_index = [token for token, _ in sorted(bundle.vocabulary.items(), key=lambda item: item[1])]
    ranked = recommend_prefit_content(
        bundle.catalog,
        mode=baseline_mode,
        seed_slug=seed_slug,
        item_vectors=bundle.item_vectors,
        vocabulary=bundle.vocabulary,
        idf=bundle.idf,
        tokens_by_index=tokens_by_index,
        catalog_scores=bundle.catalog_scores(),
        limit=limit,
    )
    if not ranked and mode == "similar":
        fallback_reason = "similar_no_candidates"
        baseline_mode = "cozy"
        ranked = recommend_prefit_content(
            bundle.catalog,
            mode=baseline_mode,
            item_vectors=bundle.item_vectors,
            vocabulary=bundle.vocabulary,
            idf=bundle.idf,
            tokens_by_index=tokens_by_index,
            catalog_scores=bundle.catalog_scores(),
            limit=limit,
        )

    games_by_slug = {game.slug: game for game in bundle.catalog}
    return RecommendationServiceResult(
        recommendations=[_to_bundle_game_out(games_by_slug[item.slug], item) for item in ranked],
        explanation=_bundle_explanation(mode, baseline_mode, bool(seed_slug)),
        fixtureNotice="",
        algorithm=bundle.algorithm,
        version=bundle.model_version,
        dataSnapshot=bundle.data_snapshot,
        disclosure=bundle.disclosure,
        catalogItems=len([game for game in bundle.catalog if game.isActive]),
        fallbackReason=fallback_reason,
    )


def _filter_catalog_games(games: list[CatalogGameSchema], *, limit: int, query: str | None) -> list[CatalogGameSchema]:
    active = [game for game in games if game.isActive]
    if query:
        normalized = query.strip().lower()
        active = [
            game
            for game in active
            if normalized in game.title.lower()
            or normalized in game.slug.lower()
            or normalized in game.sourceGameId.lower()
            or any(normalized in term.lower() for term in [*game.genres, *game.tags])
        ]
    active.sort(key=lambda game: (game.title.lower(), game.slug))
    return active[: max(0, limit)]


def _list_bundle_games(bundle: LoadedContentBundle, *, limit: int, query: str | None) -> list[GameOut]:
    return [_to_bundle_catalog_game_out(bundle, game) for game in _filter_catalog_games(bundle.catalog, limit=limit, query=query)]


def _resolve_seed_slug(games: list[CatalogGameSchema], favorite_game: str | None) -> str | None:
    normalized = (favorite_game or "").strip().lower()
    if not normalized:
        return None
    slug_match = next((game.slug for game in games if game.slug == normalized), None)
    if slug_match is not None:
        return slug_match
    return next(
        (
            game.slug
            for game in games
            if game.title.lower() == normalized or game.sourceGameId.lower() == normalized
        ),
        None,
    )


def _to_baseline_mode(mode: RecommendationMode, seed_slug: str | None) -> BaselineRecommendationMode:
    if mode == "similar" and seed_slug:
        return "similar"
    if mode == "cozy":
        return "cozy"
    if mode == "competitive":
        return "competitive"
    return "non-trending"


def _content_explanation(mode: RecommendationMode, baseline_mode: BaselineRecommendationMode, has_seed: bool) -> str:
    if mode == "trending":
        return "Content mode has no real trend signal, so it ranks the self-authored sample with the baseline non-trending text/tag scorer."
    if mode == "similar" and not has_seed:
        return "The favorite game was not found in the self-authored sample, so content mode falls back to source-grounded sample recommendations."
    if mode == "similar":
        return "Ranks the self-authored sample by text, genre, and tag overlap with the matched favorite game."
    return f"Ranks the self-authored sample with the baseline {baseline_mode} text, genre, and tag scorer."


def _bundle_explanation(mode: RecommendationMode, baseline_mode: BaselineRecommendationMode, has_seed: bool) -> str:
    if mode == "trending":
        return "The selected snapshot has no live trend signal, so this mode returns deterministic catalog picks using fitted TF-IDF/tag features plus historical source popularity fields when present."
    if mode == "similar" and not has_seed:
        return "The favorite game was not found in the loaded catalog snapshot, so the app falls back to source-grounded catalog recommendations from the same bundle."
    if mode == "similar":
        return "Ranks games from the same loaded catalog snapshot by fitted TF-IDF text similarity plus genre/tag overlap, excluding the selected seed."
    return f"Ranks games from the same loaded catalog snapshot with the baseline {baseline_mode} TF-IDF, genre, and tag scorer."


def _to_content_catalog_game_out(game: CatalogGameSchema) -> GameOut:
    return GameOut(
        slug=game.slug,
        title=game.title,
        shortDescription=game.description or "Self-authored sample game record.",
        genres=game.genres,
        source=game.sourceId,
        reason="Available in the labeled self-authored content-smoke fixture.",
    )


def _to_bundle_catalog_game_out(bundle: LoadedContentBundle, game: CatalogGameSchema) -> GameOut:
    return GameOut(
        slug=game.slug,
        title=game.title,
        shortDescription=game.description or "No description was available in the normalized snapshot.",
        genres=game.genres,
        source=bundle.source_id,
        reason="Catalog item from the loaded Kaggle snapshot bundle. Recommendations use this same snapshot and exclude a selected seed when applicable.",
    )


def _to_bundle_game_out(game: CatalogGameSchema, item) -> GameOut:
    return GameOut(
        slug=game.slug,
        title=game.title,
        shortDescription=game.description or "No description was available in the normalized snapshot.",
        genres=game.genres,
        source=game.sourceId,
        reason=_build_content_reason(item),
    )


def _to_content_game_out(game: CatalogGameSchema, item) -> GameOut:
    return GameOut(
        slug=game.slug,
        title=game.title,
        shortDescription=game.description or "Self-authored sample game record.",
        genres=game.genres,
        source=game.sourceId,
        reason=_build_content_reason(item),
    )


def _build_content_reason(item) -> str:
    explanation = item.explanation
    signals = explanation.get("signals", {})
    fragments: list[str] = []
    exact = signals.get("exact", {})
    if exact.get("sharedGenres") or exact.get("sharedTags"):
        fragments.append(
            "overlaps on " + ", ".join([*exact.get("sharedGenres", []), *exact.get("sharedTags", [])])
        )
    if exact.get("matchedTerms"):
        fragments.append("matches tags/genres " + ", ".join(exact["matchedTerms"]))
    tfidf = signals.get("tfidf", {})
    if tfidf.get("matchedTokens"):
        fragments.append("shares text tokens " + ", ".join(tfidf["matchedTokens"][:5]))
    fields = ", ".join(explanation.get("sourceFieldsUsed", [])) or "catalog fields"
    evidence = "; ".join(fragments) if fragments else "ranked by available source fields"
    return f"{evidence}. Evidence fields: {fields}. Score source: {explanation.get('version', BASELINE_RECOMMENDER_VERSION)}."
