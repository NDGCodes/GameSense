import json
from pathlib import Path

from app.recommender import BASELINE_RECOMMENDER_VERSION, recommend_baseline
from app.schemas import CatalogGameSchema

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = REPO_ROOT / "data/fixtures/ml/sample_games.self-authored.json"
SOURCE_ID = "gamesense-self-authored-smoke-fixture"


def load_sample_games() -> list[CatalogGameSchema]:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    games: list[CatalogGameSchema] = []
    for index, record in enumerate(fixture["records"], start=1):
        games.append(
            CatalogGameSchema.model_validate(
                {
                    "sourceId": SOURCE_ID,
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


def test_similar_mode_excludes_seed_and_uses_synthetic_dense_vectors() -> None:
    games = load_sample_games()
    synthetic_test_vectors = {
        "fixture-moonlit-market": [1.0, 0.0, 0.0],
        "fixture-orbit-runners": [0.92, 0.08, 0.0],
    }

    recommendations = recommend_baseline(
        games,
        mode="similar",
        seed_slug="fixture-moonlit-market",
        dense_vectors=synthetic_test_vectors,
    )

    assert [item.slug for item in recommendations] == ["fixture-orbit-runners"]
    assert "fixture-moonlit-market" not in [item.slug for item in recommendations]
    assert recommendations[0].componentRanks["dense"] == 1
    assert recommendations[0].explanation["signals"]["dense"]["vectorInput"] == "precomputed-or-synthetic-test-vector"


def test_missing_vector_falls_back_to_tfidf_and_exact_rankings() -> None:
    games = load_sample_games()

    recommendations = recommend_baseline(
        games,
        mode="similar",
        seed_slug="fixture-moonlit-market",
        dense_vectors={"fixture-moonlit-market": [1.0, 0.0]},
    )

    assert [item.slug for item in recommendations] == ["fixture-orbit-runners"]
    assert "dense" not in recommendations[0].componentRanks
    assert set(recommendations[0].componentRanks) == {"tfidf"}


def test_cozy_and_competitive_modes_use_exact_tag_and_genre_matches() -> None:
    games = load_sample_games()

    cozy = recommend_baseline(games, mode="cozy")
    competitive = recommend_baseline(games, mode="competitive")

    assert cozy[0].slug == "fixture-moonlit-market"
    assert cozy[0].explanation["signals"]["exact"]["matchedTerms"] == ["cozy", "crafting", "management", "relaxing"]
    assert competitive[0].slug == "fixture-orbit-runners"
    assert competitive[0].explanation["signals"]["exact"]["matchedTerms"] == ["action", "co-op", "teamwork"]


def test_tfidf_mode_query_and_mode_vector_inputs_contribute_to_stable_ranking() -> None:
    games = load_sample_games()
    synthetic_mode_vectors = {"cozy": [1.0, 0.0]}
    synthetic_game_vectors = {
        "fixture-moonlit-market": [0.95, 0.05],
        "fixture-orbit-runners": [0.1, 0.9],
    }

    first = recommend_baseline(
        games,
        mode="cozy",
        dense_vectors=synthetic_game_vectors,
        mode_query_vectors=synthetic_mode_vectors,
    )
    second = recommend_baseline(
        list(reversed(games)),
        mode="cozy",
        dense_vectors=synthetic_game_vectors,
        mode_query_vectors=synthetic_mode_vectors,
    )

    assert [item.slug for item in first] == [item.slug for item in second]
    assert first[0].slug == "fixture-moonlit-market"
    assert first[0].componentRanks == {"dense": 1, "tfidf": 1, "exact": 1}
    assert "matchedTokens" in first[0].explanation["signals"]["tfidf"]


def test_non_trending_mode_filters_trending_slugs_and_returns_source_grounded_explanations() -> None:
    games = load_sample_games()

    recommendations = recommend_baseline(
        games,
        mode="non-trending",
        trending_slugs={"fixture-orbit-runners"},
    )

    assert [item.slug for item in recommendations] == ["fixture-moonlit-market"]
    explanation = recommendations[0].explanation
    assert explanation["version"] == BASELINE_RECOMMENDER_VERSION
    assert explanation["sourceId"] == SOURCE_ID
    assert explanation["sourceGameId"] == "fixture-moonlit-market"
    assert explanation["fusion"] == {"method": "reciprocal-rank-fusion", "k": 60}
    assert set(explanation["sourceFieldsUsed"]).issuperset({"genres", "tags"})
