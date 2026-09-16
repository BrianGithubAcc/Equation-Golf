from datetime import datetime, timezone

from backend.main import pareto_frontier
from backend.models import Submission, User


def submission(identifier, user_id, cost, error):
    return Submission(
        id=identifier,
        user_id=user_id,
        challenge_id=1,
        equation="x",
        input_mode="basic",
        cost=cost,
        error=error,
        submitted_at=datetime.now(timezone.utc),
    )


def test_pareto_frontier_excludes_dominated_and_orders_results():
    rows = [
        submission(1, 1, 1, 0.5),
        submission(2, 2, 3, 0.25),
        submission(3, 3, 3, 0.6),  # Dominated by 1.
        submission(4, 4, 2, 0.3),
        submission(5, 4, 4, 0.2),  # Same user, still non-dominated.
        submission(6, 5, 1, 0.7),  # Dominated by 1.
    ]

    frontier = pareto_frontier(rows)

    assert [row.id for row in frontier] == [1, 4, 2, 5]


def test_user_schema_does_not_persist_identity_tokens():
    columns = set(User.__table__.columns.keys())

    assert "email" not in columns
    assert not any(
        token in column
        for column in columns
        for token in ("access_token", "refresh_token", "id_token")
    )
