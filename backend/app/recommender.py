from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Literal, Mapping, Sequence

from app.schemas import CatalogGameSchema

BaselineRecommendationMode = Literal["similar", "cozy", "competitive", "non-trending"]
SparseVector = Mapping[int, float]

BASELINE_RECOMMENDER_VERSION = "gamesense-local-baseline-recommender-v1"
RRF_K = 60

_MODE_QUERY_TERMS: dict[str, tuple[str, ...]] = {
    "cozy": ("cozy", "relaxing", "crafting", "farming", "management", "gentle", "single-player"),
    "competitive": ("competitive", "multiplayer", "co-op", "teamwork", "action", "platforming", "sports"),
    "non-trending": ("single-player", "cozy", "management", "platforming", "crafting", "teamwork"),
}

_MODE_EXACT_TERMS: dict[str, tuple[str, ...]] = {
    "cozy": ("cozy", "relaxing", "crafting", "farming", "management"),
    "competitive": ("competitive", "multiplayer", "co-op", "cooperative", "teamwork", "action"),
}


@dataclass(frozen=True)
class ComponentEvidence:
    rank: int
    score: float
    signals: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BaselineRecommendation:
    slug: str
    title: str
    score: float
    componentRanks: dict[str, int]
    explanation: dict[str, Any]


def _tokenize(value: str | None) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", (value or "").lower())


def _norm_terms(values: Iterable[str]) -> list[str]:
    return [value.strip().lower() for value in values if value and value.strip()]


def _game_terms(game: CatalogGameSchema) -> list[str]:
    return _norm_terms([*game.genres, *game.tags])


def _game_document(game: CatalogGameSchema) -> list[str]:
    tokens = [*_tokenize(game.title), *_tokenize(game.description)]
    for term in _game_terms(game):
        tokens.extend(_tokenize(term))
    return tokens


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left or not right:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _rank_scores(scores: Mapping[str, tuple[float, dict[str, Any]]], games_by_slug: Mapping[str, CatalogGameSchema]) -> dict[str, ComponentEvidence]:
    ordered = sorted(
        ((slug, score, signals) for slug, (score, signals) in scores.items() if score > 0 and slug in games_by_slug),
        key=lambda item: (-item[1], games_by_slug[item[0]].title.lower(), item[0]),
    )
    return {
        slug: ComponentEvidence(rank=index, score=round(score, 10), signals=signals)
        for index, (slug, score, signals) in enumerate(ordered, start=1)
    }


def _tfidf_rankings(
    candidates: Sequence[CatalogGameSchema],
    *,
    query_tokens: Sequence[str],
) -> dict[str, ComponentEvidence]:
    docs = {game.slug: _game_document(game) for game in candidates}
    query = list(query_tokens)
    if not query:
        return {}
    doc_count = len(docs) + 1
    df: dict[str, int] = {}
    for tokens in [query, *docs.values()]:
        for token in set(tokens):
            df[token] = df.get(token, 0) + 1

    def vector(tokens: Sequence[str]) -> dict[str, float]:
        counts: dict[str, int] = {}
        for token in tokens:
            counts[token] = counts.get(token, 0) + 1
        return {
            token: count * (math.log((1 + doc_count) / (1 + df.get(token, 0))) + 1)
            for token, count in counts.items()
        }

    query_vector = vector(query)
    scores: dict[str, tuple[float, dict[str, Any]]] = {}
    for game in candidates:
        game_vector = vector(docs[game.slug])
        shared = sorted(set(query_vector).intersection(game_vector))
        score = _sparse_cosine(query_vector, game_vector)
        scores[game.slug] = (score, {"matchedTokens": shared, "sourceFields": ["title", "description", "genres", "tags"]})
    return _rank_scores(scores, {game.slug: game for game in candidates})


def _sparse_cosine(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    dot = sum(weight * right.get(token, 0.0) for token, weight in left.items())
    left_norm = math.sqrt(sum(weight * weight for weight in left.values()))
    right_norm = math.sqrt(sum(weight * weight for weight in right.values()))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _indexed_sparse_cosine(left: SparseVector, right: SparseVector) -> float:
    dot = sum(weight * right.get(index, 0.0) for index, weight in left.items())
    left_norm = math.sqrt(sum(weight * weight for weight in left.values()))
    right_norm = math.sqrt(sum(weight * weight for weight in right.values()))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _dense_rankings(
    candidates: Sequence[CatalogGameSchema],
    *,
    query_vector: Sequence[float] | None,
    dense_vectors: Mapping[str, Sequence[float]],
) -> dict[str, ComponentEvidence]:
    if query_vector is None:
        return {}
    scores = {
        game.slug: (
            _cosine(query_vector, dense_vectors.get(game.slug, ())),
            {"sourceFields": ["precomputedDenseDescriptionVector"], "vectorInput": "precomputed-or-synthetic-test-vector"},
        )
        for game in candidates
        if game.slug in dense_vectors
    }
    return _rank_scores(scores, {game.slug: game for game in candidates})


def _exact_rankings(
    candidates: Sequence[CatalogGameSchema],
    *,
    mode: BaselineRecommendationMode,
    seed_game: CatalogGameSchema | None,
    trending_slugs: set[str],
) -> dict[str, ComponentEvidence]:
    scores: dict[str, tuple[float, dict[str, Any]]] = {}
    if mode == "similar" and seed_game is not None:
        seed_genres = set(_norm_terms(seed_game.genres))
        seed_tags = set(_norm_terms(seed_game.tags))
        for game in candidates:
            shared_genres = sorted(seed_genres.intersection(_norm_terms(game.genres)))
            shared_tags = sorted(seed_tags.intersection(_norm_terms(game.tags)))
            score = (2 * len(shared_genres)) + len(shared_tags)
            scores[game.slug] = (float(score), {"sharedGenres": shared_genres, "sharedTags": shared_tags, "sourceFields": ["genres", "tags"]})
    elif mode in _MODE_EXACT_TERMS:
        wanted = set(_MODE_EXACT_TERMS[mode])
        for game in candidates:
            matched = sorted(wanted.intersection(_game_terms(game)))
            scores[game.slug] = (float(len(matched)), {"matchedTerms": matched, "sourceFields": ["genres", "tags"]})
    elif mode == "non-trending":
        for game in candidates:
            is_non_trending = game.slug not in trending_slugs and not bool(game.metadata.get("trending", False))
            scores[game.slug] = (1.0 if is_non_trending else 0.0, {"excludedTrendingSlug": game.slug in trending_slugs, "metadataTrending": bool(game.metadata.get("trending", False)), "sourceFields": ["metadata", "callerTrendingSlugs"]})
    return _rank_scores(scores, {game.slug: game for game in candidates})


def _prefit_query_vector(
    query_tokens: Sequence[str],
    *,
    vocabulary: Mapping[str, int],
    idf: Sequence[float],
) -> dict[int, float]:
    counts: dict[int, int] = {}
    for token in query_tokens:
        index = vocabulary.get(token)
        if index is not None:
            counts[index] = counts.get(index, 0) + 1
    weighted = {index: count * idf[index] for index, count in counts.items() if index < len(idf)}
    norm = math.sqrt(sum(value * value for value in weighted.values()))
    if norm == 0:
        return {}
    return {index: value / norm for index, value in weighted.items()}


def _prefit_tfidf_rankings(
    candidates: Sequence[CatalogGameSchema],
    *,
    query_vector: SparseVector,
    item_vectors: Mapping[str, SparseVector],
    tokens_by_index: Sequence[str],
) -> dict[str, ComponentEvidence]:
    if not query_vector:
        return {}
    scores: dict[str, tuple[float, dict[str, Any]]] = {}
    for game in candidates:
        item_vector = item_vectors.get(game.slug, {})
        shared_indices = set(query_vector).intersection(item_vector)
        matched_tokens = sorted(
            (tokens_by_index[index], query_vector[index] * item_vector[index])
            for index in shared_indices
            if index < len(tokens_by_index)
        )
        matched_tokens.sort(key=lambda item: (-item[1], item[0]))
        score = _indexed_sparse_cosine(query_vector, item_vector)
        scores[game.slug] = (
            score,
            {
                "matchedTokens": [token for token, _ in matched_tokens[:8]],
                "sourceFields": ["fittedTfidfTitleDescriptionGenresTags"],
            },
        )
    return _rank_scores(scores, {game.slug: game for game in candidates})


def _catalog_score_rankings(
    candidates: Sequence[CatalogGameSchema],
    *,
    catalog_scores: Mapping[str, float],
) -> dict[str, ComponentEvidence]:
    scores = {
        game.slug: (
            float(catalog_scores.get(game.slug, 0.0)),
            {"contentBundleScore": float(catalog_scores.get(game.slug, 0.0)), "sourceFields": ["metadata.contentBundleScore"]},
        )
        for game in candidates
        if catalog_scores.get(game.slug, 0.0) > 0
    }
    return _rank_scores(scores, {game.slug: game for game in candidates})


def recommend_prefit_content(
    games: Sequence[CatalogGameSchema],
    *,
    mode: BaselineRecommendationMode,
    seed_slug: str | None = None,
    item_vectors: Mapping[str, SparseVector],
    vocabulary: Mapping[str, int],
    idf: Sequence[float],
    tokens_by_index: Sequence[str],
    catalog_scores: Mapping[str, float] | None = None,
    limit: int = 10,
) -> list[BaselineRecommendation]:
    """Rank catalog records using fitted portable TF-IDF vectors plus existing exact signals."""

    active_games = [game for game in games if game.isActive]
    games_by_slug = {game.slug: game for game in active_games}
    seed_game = games_by_slug.get(seed_slug or "")
    excluded_slugs = {seed_game.slug} if mode == "similar" and seed_game else set()
    candidates = [game for game in active_games if game.slug not in excluded_slugs]

    if mode == "similar" and seed_game is not None:
        query_vector = item_vectors.get(seed_game.slug, {})
    else:
        query_tokens = [token for term in _MODE_QUERY_TERMS.get(mode, ()) for token in _tokenize(term)]
        query_vector = _prefit_query_vector(query_tokens, vocabulary=vocabulary, idf=idf)

    component_evidence = {
        "tfidf": _prefit_tfidf_rankings(
            candidates,
            query_vector=query_vector,
            item_vectors=item_vectors,
            tokens_by_index=tokens_by_index,
        ),
        "exact": _exact_rankings(candidates, mode=mode, seed_game=seed_game, trending_slugs=set()),
        "catalog": _catalog_score_rankings(candidates, catalog_scores=catalog_scores or {}),
    }

    candidate_union = sorted({slug for rankings in component_evidence.values() for slug in rankings})
    recommendations: list[BaselineRecommendation] = []
    for slug in candidate_union:
        score = sum(1 / (RRF_K + evidence[slug].rank) for evidence in component_evidence.values() if slug in evidence)
        game = games_by_slug[slug]
        component_ranks = {name: rankings[slug].rank for name, rankings in component_evidence.items() if slug in rankings}
        signals = {
            name: {"rank": rankings[slug].rank, "score": rankings[slug].score, **rankings[slug].signals}
            for name, rankings in component_evidence.items()
            if slug in rankings
        }
        recommendations.append(
            BaselineRecommendation(
                slug=slug,
                title=game.title,
                score=round(score, 10),
                componentRanks=component_ranks,
                explanation={
                    "version": BASELINE_RECOMMENDER_VERSION,
                    "mode": mode,
                    "seedSlug": seed_game.slug if seed_game else None,
                    "sourceId": game.sourceId,
                    "sourceGameId": game.sourceGameId,
                    "sourceFieldsUsed": sorted({field for signal in signals.values() for field in signal.get("sourceFields", [])}),
                    "signals": signals,
                    "fusion": {"method": "reciprocal-rank-fusion", "k": RRF_K},
                    "prefitTfidf": True,
                },
            )
        )

    recommendations.sort(key=lambda item: (-item.score, item.title.lower(), item.slug))
    return recommendations[:limit]


def recommend_baseline(
    games: Sequence[CatalogGameSchema],
    *,
    mode: BaselineRecommendationMode,
    seed_slug: str | None = None,
    dense_vectors: Mapping[str, Sequence[float]] | None = None,
    mode_query_vectors: Mapping[str, Sequence[float]] | None = None,
    trending_slugs: Iterable[str] = (),
    limit: int = 10,
) -> list[BaselineRecommendation]:
    """Rank local catalog records with RRF over dense, TF-IDF, and exact tag/genre signals.

    Dense vectors are consumed only when supplied by the caller. This module never downloads
    model weights, trains an encoder, or generates embeddings for catalog records.
    """

    active_games = [game for game in games if game.isActive]
    games_by_slug = {game.slug: game for game in active_games}
    seed_game = games_by_slug.get(seed_slug or "")
    trending = set(trending_slugs)
    excluded_slugs = {seed_game.slug} if mode == "similar" and seed_game else set()
    if mode == "non-trending":
        excluded_slugs.update(game.slug for game in active_games if game.slug in trending or bool(game.metadata.get("trending", False)))
    candidates = [game for game in active_games if game.slug not in excluded_slugs]
    vectors = dense_vectors or {}

    if mode == "similar" and seed_game is not None:
        query_tokens = _game_document(seed_game)
        query_vector = vectors.get(seed_game.slug)
    else:
        query_tokens = [token for term in _MODE_QUERY_TERMS.get(mode, ()) for token in _tokenize(term)]
        query_vector = (mode_query_vectors or {}).get(mode)

    component_evidence = {
        "dense": _dense_rankings(candidates, query_vector=query_vector, dense_vectors=vectors),
        "tfidf": _tfidf_rankings(candidates, query_tokens=query_tokens),
        "exact": _exact_rankings(candidates, mode=mode, seed_game=seed_game, trending_slugs=trending),
    }

    candidate_union = sorted({slug for rankings in component_evidence.values() for slug in rankings})
    recommendations: list[BaselineRecommendation] = []
    for slug in candidate_union:
        score = sum(1 / (RRF_K + evidence[slug].rank) for evidence in component_evidence.values() if slug in evidence)
        game = games_by_slug[slug]
        component_ranks = {name: rankings[slug].rank for name, rankings in component_evidence.items() if slug in rankings}
        signals = {
            name: {"rank": rankings[slug].rank, "score": rankings[slug].score, **rankings[slug].signals}
            for name, rankings in component_evidence.items()
            if slug in rankings
        }
        recommendations.append(
            BaselineRecommendation(
                slug=slug,
                title=game.title,
                score=round(score, 10),
                componentRanks=component_ranks,
                explanation={
                    "version": BASELINE_RECOMMENDER_VERSION,
                    "mode": mode,
                    "seedSlug": seed_game.slug if seed_game else None,
                    "sourceId": game.sourceId,
                    "sourceGameId": game.sourceGameId,
                    "sourceFieldsUsed": sorted({field for signal in signals.values() for field in signal.get("sourceFields", [])}),
                    "signals": signals,
                    "fusion": {"method": "reciprocal-rank-fusion", "k": RRF_K},
                },
            )
        )

    recommendations.sort(key=lambda item: (-item.score, item.title.lower(), item.slug))
    return recommendations[:limit]
