"""Archive completed daily leaderboards and prune their raw submissions."""

from datetime import datetime, timezone

from sqlalchemy import delete, select

from .database import SessionLocal
from .main import pareto_frontier
from .models import ArchivedLeaderboard, Challenge, Submission, User


def archive_completed_challenges(db, today=None):
    today = today or datetime.now(timezone.utc).date()
    archived_at = datetime.now(timezone.utc)
    challenges = db.scalars(
        select(Challenge)
        .where(
            Challenge.challenge_date < today,
            Challenge.archived_at.is_(None),
        )
        .order_by(Challenge.challenge_date)
    ).all()

    archived_count = 0
    for challenge in challenges:
        submissions = db.scalars(
            select(Submission).where(
                Submission.challenge_id == challenge.id,
            )
        ).all()

        for position, submission in enumerate(
            pareto_frontier(submissions)[:100],
            start=1,
        ):
            user = db.get(User, submission.user_id)
            db.add(
                ArchivedLeaderboard(
                    challenge_id=challenge.id,
                    final_position=position,
                    user_id=submission.user_id,
                    username=user.username if user else "Deleted user",
                    avatar_url=user.avatar_url if user else None,
                    equation=submission.equation,
                    input_mode=submission.input_mode,
                    cost=submission.cost,
                    error=submission.error,
                    submitted_at=submission.submitted_at,
                )
            )

        challenge.archived_at = archived_at
        db.execute(
            delete(Submission).where(
                Submission.challenge_id == challenge.id,
            )
        )
        archived_count += 1

    db.commit()
    return archived_count


def main():
    with SessionLocal() as db:
        count = archive_completed_challenges(db)
    print(f"Archived {count} completed challenge(s).")


if __name__ == "__main__":
    main()
