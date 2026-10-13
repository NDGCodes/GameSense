import json
from pathlib import Path

from app.ml_evaluation import DEFAULT_FIXTURE, EVALUATION_VERSION, evaluate_baseline, main
from app.recommender import BASELINE_RECOMMENDER_VERSION


def test_evaluation_report_schema_and_scope_labels() -> None:
    report = evaluate_baseline(fixture_path=DEFAULT_FIXTURE)

    assert report["ok"] is True
    assert report["evaluationVersion"] == EVALUATION_VERSION
    assert report["recommenderVersion"] == BASELINE_RECOMMENDER_VERSION
    assert report["generatedAt"] == "1970-01-01T00:00:00Z"
    assert set(report) == {
        "evaluationVersion",
        "recommenderVersion",
        "generatedAt",
        "scope",
        "metrics",
        "queries",
        "limitations",
        "ok",
    }
    assert report["scope"]["catalogType"] == "tiny-self-authored-fixture"
    assert report["scope"]["externalDataUsed"] is False
    assert report["scope"]["realCatalogEvidence"] is False
    assert report["scope"]["userInteractionEvidence"] is False
    assert "purpose" in report["scope"]["syntheticVectorInputs"]
    assert "not trained embeddings" in report["scope"]["syntheticVectorInputs"]["purpose"]


def test_evaluation_is_reproducible() -> None:
    first = evaluate_baseline(fixture_path=DEFAULT_FIXTURE)
    second = evaluate_baseline(fixture_path=DEFAULT_FIXTURE)

    assert first == second


def test_evaluation_metrics_and_golden_query_sanity_checks() -> None:
    report = evaluate_baseline(fixture_path=DEFAULT_FIXTURE)
    metrics = report["metrics"]

    assert metrics["activeCatalogSize"] == 2
    assert metrics["evaluatedQueryCount"] == 4
    assert metrics["catalogCoverage"] == {
        "recommendedActiveSlugCount": 2,
        "activeCatalogSize": 2,
        "ratio": 1.0,
        "recommendedActiveSlugs": ["fixture-moonlit-market", "fixture-orbit-runners"],
    }
    assert metrics["intraListDiversity"]["method"].startswith("mean pairwise Jaccard distance")
    assert metrics["intraListDiversity"]["meanAcrossEligibleQueries"] == 1.0
    assert metrics["goldenQuerySanity"] == {"passed": 4, "total": 4, "ok": True}
    assert all(query["sanity"]["ok"] for query in report["queries"])

    by_id = {query["id"]: query for query in report["queries"]}
    assert by_id["similar_from_moonlit_market"]["recommendationSlugs"] == ["fixture-orbit-runners"]
    assert by_id["cozy_mode_prefers_moonlit_market"]["recommendationSlugs"][0] == "fixture-moonlit-market"
    assert by_id["competitive_mode_prefers_orbit_runners"]["recommendationSlugs"][0] == "fixture-orbit-runners"
    assert by_id["non_trending_excludes_caller_trending_slug"]["recommendationSlugs"] == ["fixture-moonlit-market"]


def test_cli_writes_report_only_when_output_is_requested(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "evaluation.json"

    exit_code = main(["--fixture", str(DEFAULT_FIXTURE), "--output", str(output_path)])

    assert exit_code == 0
    assert capsys.readouterr().out == ""
    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert written == evaluate_baseline(fixture_path=DEFAULT_FIXTURE)


def test_cli_stdout_is_deterministic(capsys) -> None:
    assert main(["--fixture", str(DEFAULT_FIXTURE)]) == 0
    first = capsys.readouterr().out
    assert main(["--fixture", str(DEFAULT_FIXTURE)]) == 0
    second = capsys.readouterr().out

    assert first == second
    assert json.loads(first)["ok"] is True
