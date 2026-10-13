from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Sequence

from pydantic import ValidationError

from app.recommender import BASELINE_RECOMMENDER_VERSION, recommend_baseline
from app.schemas import CatalogGameSchema

EVALUATION_VERSION = "gamesense-baseline-offline-eval-v1"
SOURCE_ID = "gamesense-self-authored-smoke-fixture"
DEFAULT_FIXTURE = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "ml" / "sample_games.self-authored.json"

SYNTHETIC_DENSE_VECTORS: dict[str, list[float]] = {
    "fixture-moonlit-market": [1.0, 0.0, 0.0],
    "fixture-orbit-runners": [0.0, 1.0, 0.0],
}

SYNTHETIC_MODE_QUERY_VECTORS: dict[str, list[float]] = {
    "cozy": [1.0, 0.0, 0.0],
    "competitive": [0.0, 1.0, 0.0],
}

GOLDEN_QUERIES: tuple[dict[str, Any], ...] = (
    {
        "id": "similar_from_moonlit_market",
        "mode": "similar",
        "seedSlug": "fixture-moonlit-market",
        "expectedTopSlug": "fixture-orbit-runners",
        "expectedExcludedSlugs": ["fixture-moonlit-market"],
    },
    {
        "id": "cozy_mode_prefers_moonlit_market",
        "mode": "cozy",
        "expectedTopSlug": "fixture-moonlit-market",
        "expectedIncludedTerms": ["cozy", "crafting", "management", "relaxing"],
    },
    {
        "id": "competitive_mode_prefers_orbit_runners",
        "mode": "competitive",
        "expectedTopSlug": "fixture-orbit-runners",
        "expectedIncludedTerms": ["action", "co-op", "teamwork"],
    },
    {
        "id": "non_trending_excludes_caller_trending_slug",
        "mode": "non-trending",
        "trendingSlugs": ["fixture-orbit-runners"],
        "expectedTopSlug": "fixture-moonlit-market",
        "expectedExcludedSlugs": ["fixture-orbit-runners"],
    },
)


class EvaluationError(RuntimeError):
    """Raised when offline evaluation cannot safely continue."""


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise EvaluationError(f"fixture not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise EvaluationError(f"{path} is not valid JSON: {exc}") from exc


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def load_sample_games(fixture_path: Path) -> tuple[str, list[CatalogGameSchema]]:
    fixture = load_json(fixture_path)
    if fixture.get("source") != "self-authored-fixture":
        raise EvaluationError("offline evaluation only accepts the self-authored smoke fixture")
    records = fixture.get("records")
    if not isinstance(records, list):
        raise EvaluationError("fixture records must be a list")

    games: list[CatalogGameSchema] = []
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            raise EvaluationError(f"fixture record {index} must be an object")
        try:
            games.append(
                CatalogGameSchema.model_validate(
                    {
                        "sourceId": SOURCE_ID,
                        "sourceGameId": record.get("id"),
                        "slug": record.get("id"),
                        "title": record.get("title"),
                        "description": record.get("description"),
                        "genres": record.get("genres") or [],
                        "tags": record.get("tags") or [],
                        "platforms": record.get("platforms") or [],
                        "releaseDate": record.get("releaseDate"),
                        "metadata": {
                            "fixtureId": fixture.get("fixtureId"),
                            "fixtureSource": fixture.get("source"),
                            "fixtureRow": index,
                        },
                        "isActive": True,
                    }
                )
            )
        except ValidationError as exc:
            raise EvaluationError(f"fixture record {index} failed catalog schema validation: {exc}") from exc
    return str(fixture.get("fixtureId", "unknown")), games


def _terms(game: CatalogGameSchema) -> set[str]:
    return {value.strip().lower() for value in [*game.genres, *game.tags] if value and value.strip()}


def intra_list_diversity(slugs: Sequence[str], games_by_slug: dict[str, CatalogGameSchema]) -> float | None:
    if len(slugs) < 2:
        return None
    distances: list[float] = []
    for left_index, left_slug in enumerate(slugs):
        for right_slug in slugs[left_index + 1 :]:
            left_terms = _terms(games_by_slug[left_slug])
            right_terms = _terms(games_by_slug[right_slug])
            union = left_terms | right_terms
            similarity = (len(left_terms & right_terms) / len(union)) if union else 1.0
            distances.append(1.0 - similarity)
    return round(sum(distances) / len(distances), 6) if distances else None


def _sanity_check(query: dict[str, Any], slugs: list[str], top_explanation: dict[str, Any] | None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    expected_top = query.get("expectedTopSlug")
    if expected_top:
        actual_top = slugs[0] if slugs else None
        checks.append({"name": "expected_top_slug", "ok": actual_top == expected_top, "expected": expected_top, "actual": actual_top})

    for excluded in query.get("expectedExcludedSlugs", []):
        checks.append({"name": "excluded_slug_absent", "ok": excluded not in slugs, "slug": excluded})

    expected_terms = query.get("expectedIncludedTerms", [])
    if expected_terms:
        exact_signal = (top_explanation or {}).get("signals", {}).get("exact", {})
        matched_terms = exact_signal.get("matchedTerms", [])
        checks.append(
            {
                "name": "expected_exact_terms_on_top_slug",
                "ok": sorted(matched_terms) == sorted(expected_terms),
                "expected": sorted(expected_terms),
                "actual": sorted(matched_terms),
            }
        )

    return {"ok": all(check["ok"] for check in checks), "checks": checks}


def evaluate_baseline(*, fixture_path: Path = DEFAULT_FIXTURE, limit: int = 10) -> dict[str, Any]:
    fixture_id, games = load_sample_games(fixture_path)
    active_games = [game for game in games if game.isActive]
    games_by_slug = {game.slug: game for game in active_games}
    query_reports: list[dict[str, Any]] = []
    covered_slugs: set[str] = set()
    diversity_values: list[float] = []

    for query in GOLDEN_QUERIES:
        recommendations = recommend_baseline(
            games,
            mode=query["mode"],
            seed_slug=query.get("seedSlug"),
            dense_vectors=SYNTHETIC_DENSE_VECTORS,
            mode_query_vectors=SYNTHETIC_MODE_QUERY_VECTORS,
            trending_slugs=query.get("trendingSlugs", []),
            limit=limit,
        )
        slugs = [item.slug for item in recommendations]
        covered_slugs.update(slugs)
        diversity = intra_list_diversity(slugs, games_by_slug)
        if diversity is not None:
            diversity_values.append(diversity)
        sanity = _sanity_check(query, slugs, recommendations[0].explanation if recommendations else None)
        query_reports.append(
            {
                "id": query["id"],
                "mode": query["mode"],
                "seedSlug": query.get("seedSlug"),
                "trendingSlugs": query.get("trendingSlugs", []),
                "expectedTopSlug": query.get("expectedTopSlug"),
                "recommendationSlugs": slugs,
                "topRecommendation": recommendations[0].__dict__ if recommendations else None,
                "recommendationCount": len(recommendations),
                "catalogCoverageContribution": sorted(set(slugs)),
                "intraListDiversity": diversity,
                "sanity": sanity,
            }
        )

    catalog_size = len(active_games)
    report = {
        "evaluationVersion": EVALUATION_VERSION,
        "recommenderVersion": BASELINE_RECOMMENDER_VERSION,
        "generatedAt": "1970-01-01T00:00:00Z",
        "scope": {
            "fixturePath": str(fixture_path),
            "fixtureId": fixture_id,
            "sourceId": SOURCE_ID,
            "catalogType": "tiny-self-authored-fixture",
            "externalDataUsed": False,
            "realCatalogEvidence": False,
            "userInteractionEvidence": False,
            "syntheticVectorInputs": {
                "purpose": "deterministic evaluation sanity checks only; not trained embeddings or model outputs",
                "gameVectorSlugs": sorted(SYNTHETIC_DENSE_VECTORS),
                "modeQueryVectorModes": sorted(SYNTHETIC_MODE_QUERY_VECTORS),
            },
        },
        "metrics": {
            "activeCatalogSize": catalog_size,
            "evaluatedQueryCount": len(query_reports),
            "catalogCoverage": {
                "recommendedActiveSlugCount": len(covered_slugs),
                "activeCatalogSize": catalog_size,
                "ratio": round(len(covered_slugs) / catalog_size, 6) if catalog_size else 0.0,
                "recommendedActiveSlugs": sorted(covered_slugs),
            },
            "intraListDiversity": {
                "method": "mean pairwise Jaccard distance over lowercase genre/tag sets; null when a list has fewer than two items",
                "meanAcrossEligibleQueries": round(sum(diversity_values) / len(diversity_values), 6) if diversity_values else None,
                "eligibleQueryCount": len(diversity_values),
            },
            "goldenQuerySanity": {
                "passed": sum(1 for query in query_reports if query["sanity"]["ok"]),
                "total": len(query_reports),
                "ok": all(query["sanity"]["ok"] for query in query_reports),
            },
        },
        "queries": query_reports,
        "limitations": [
            "Evaluation uses only two self-authored fixture records.",
            "Synthetic vectors are hand-written test inputs and are not evidence of embedding quality.",
            "No real catalog, traffic, relevance labels, user feedback, ranking fairness, latency, or business-impact evidence is measured.",
        ],
    }
    report["ok"] = bool(report["metrics"]["goldenQuerySanity"]["ok"])
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GameSense offline evaluation for the local baseline recommender")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE, help="Path to the tiny self-authored fixture JSON")
    parser.add_argument("--limit", type=int, default=10, help="Recommendation limit per golden query")
    parser.add_argument("--output", type=Path, help="Opt-in path for writing the JSON report; stdout is used by default")
    return parser


def emit(data: dict[str, Any], output: Path | None) -> None:
    if output:
        write_json(output, data)
    else:
        print(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False))


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        data = evaluate_baseline(fixture_path=args.fixture, limit=args.limit)
        emit(data, args.output)
        return 0 if data.get("ok", False) else 1
    except EvaluationError as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
