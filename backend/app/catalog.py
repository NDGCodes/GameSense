from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Game
from app.schemas import GameOut, RecommendationMode

FIXTURE_NOTICE = (
    "Demo fixture catalog only: these records are hand-written examples for local app and "
    "infrastructure validation, not a real Steam dataset and not model-generated output."
)

MODE_EXPLANATIONS: dict[RecommendationMode, str] = {
    "trending": "Ranks demo fixtures by the popularity score stored in the application database.",
    "similar": "Uses simple demo genre overlap when the favorite game matches a fixture; otherwise returns broadly similar demo fixtures.",
    "cozy": "Filters for hand-labeled cozy demo fixtures in the local catalog.",
    "competitive": "Filters for hand-labeled competitive demo fixtures in the local catalog.",
}


def list_active_games(session: Session) -> list[Game]:
    return list(
        session.scalars(
            select(Game).where(Game.is_active.is_(True)).order_by(Game.popularity_score.desc(), Game.title.asc())
        )
    )


def to_game_out(game: Game) -> GameOut:
    return GameOut(
        slug=game.slug,
        title=game.title,
        shortDescription=game.short_description,
        genres=game.genres,
        source=game.source,
        reason=game.demo_reason,
    )


def recommend_games(
    session: Session,
    mode: RecommendationMode,
    favorite_game: str | None,
    limit: int = 3,
) -> list[GameOut]:
    games = list_active_games(session)
    selected: list[Game]

    if mode == "similar" and favorite_game:
        normalized = favorite_game.strip().lower()
        favorite = next((game for game in games if game.title.lower() == normalized or game.slug == normalized), None)
        if favorite:
            favorite_genres = set(favorite.genres)
            selected = [
                game
                for game in games
                if game.slug != favorite.slug and favorite_genres.intersection(game.genres)
            ]
        else:
            selected = [game for game in games if "similar" in game.modes]
    else:
        selected = [game for game in games if mode in game.modes]

    if not selected:
        selected = games

    return [to_game_out(game) for game in selected[:limit]]
