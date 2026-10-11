from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


class Game(Base):
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
