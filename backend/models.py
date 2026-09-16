from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)

from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
)


class Base(DeclarativeBase):
    pass


class Challenge(Base):
    __tablename__ = "daily_challenges"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    challenge_date: Mapped[date] = mapped_column(
        Date,
        unique=True,
        index=True,
        nullable=False,
    )

    # Secret server-side expression.
    target_expr: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Secret human-readable LaTeX.
    target_latex: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    domain_min: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    domain_max: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    range_min: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    range_max: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    google_sub: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )

    username: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    avatar_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        index=True,
        nullable=False,
    )

    challenge_id: Mapped[int] = mapped_column(
        ForeignKey(
            "daily_challenges.id",
            ondelete="CASCADE",
        ),
        index=True,
        nullable=False,
    )

    equation: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    input_mode: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    error: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    cost: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ArchivedLeaderboard(Base):
    __tablename__ = "archived_leaderboard"

    id: Mapped[int] = mapped_column(primary_key=True)

    challenge_id: Mapped[int] = mapped_column(
        ForeignKey("daily_challenges.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    final_position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    username: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    avatar_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    equation: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    input_mode: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    error: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    cost: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
