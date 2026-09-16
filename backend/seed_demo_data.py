"""Seed development-only users, submissions, and completed leaderboards."""

import argparse
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from sqlalchemy import delete, select

load_dotenv()

from .archive_completed_challenges import archive_completed_challenges  # noqa: E402
from .database import SessionLocal  # noqa: E402
from .models import ArchivedLeaderboard, Challenge, Submission, User  # noqa: E402
from .seed_dev import main as seed_development  # noqa: E402


DEMO_SUB_PREFIX = "demo-seed-"
DEMO_NAME_PREFIX = "Demo Player "


def _arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--today-count", type=int, default=5000)
    parser.add_argument("--archive-count", type=int, default=150)
    return parser.parse_args()


def main(today_count=5000, archive_count=150):
    if today_count < 1 or archive_count < 101:
        raise ValueError("Use at least 1 today row and 101 archive rows")

    seed_development()
    today = datetime.now(timezone.utc).date()

    with SessionLocal() as db:
        challenges = db.scalars(
            select(Challenge)
            .where(Challenge.challenge_date <= today)
            .order_by(Challenge.challenge_date)
        ).all()
        today_challenge = next(
            (row for row in challenges if row.challenge_date == today),
            None,
        )
        if today_challenge is None:
            raise RuntimeError(f"No development challenge exists for {today}")

        demo_users = db.scalars(
            select(User)
            .where(User.google_sub.like(f"{DEMO_SUB_PREFIX}%"))
            .order_by(User.id)
        ).all()
        user_count = max(1000, (today_count + archive_count) // 5)
        new_users = []
        for index in range(len(demo_users), user_count):
            new_users.append(
                User(
                    google_sub=f"{DEMO_SUB_PREFIX}{index + 1}",
                    username=f"{DEMO_NAME_PREFIX}{index + 1:04d}",
                    avatar_url=None,
                )
            )
        demo_users.extend(new_users)
        db.add_all(new_users)
        db.flush()

        demo_user_ids = [user.id for user in demo_users]
        if demo_user_ids:
            db.execute(
                delete(Submission).where(
                    Submission.user_id.in_(demo_user_ids),
                )
            )
            db.execute(
                delete(ArchivedLeaderboard).where(
                    ArchivedLeaderboard.user_id.in_(demo_user_ids),
                )
            )

        # Reset archives made by an earlier run when they contain demo rows only.
        for challenge in challenges:
            if challenge.archived_at is None:
                continue
            archived = db.scalars(
                select(ArchivedLeaderboard).where(
                    ArchivedLeaderboard.challenge_id == challenge.id,
                )
            ).all()
            if archived and all(
                row.username.startswith(DEMO_NAME_PREFIX)
                for row in archived
            ):
                db.execute(
                    delete(ArchivedLeaderboard).where(
                        ArchivedLeaderboard.challenge_id == challenge.id,
                    )
                )
                challenge.archived_at = None

        now = datetime.now(timezone.utc)
        current_rows = []
        for index in range(1, today_count + 1):
            current_rows.append(
                Submission(
                    user_id=demo_users[(index - 1) % len(demo_users)].id,
                    challenge_id=today_challenge.id,
                    equation=f"x + {index / 1000:.6f}",
                    input_mode="basic",
                    cost=index,
                    error=(today_count - index + 1) / 1000,
                    submitted_at=now + timedelta(microseconds=index),
                )
            )
        db.add_all(current_rows)

        old_rows = 0
        for challenge in challenges:
            if challenge.challenge_date >= today:
                continue

            if challenge.archived_at is not None:
                existing_positions = set(
                    db.scalars(
                        select(ArchivedLeaderboard.final_position).where(
                            ArchivedLeaderboard.challenge_id == challenge.id,
                        )
                    ).all()
                )
                for position in range(1, 101):
                    if position in existing_positions:
                        continue
                    is_solution = position == 100
                    db.add(
                        ArchivedLeaderboard(
                            challenge_id=challenge.id,
                            final_position=position,
                            user_id=demo_users[(position - 1) % len(demo_users)].id,
                            username=demo_users[(position - 1) % len(demo_users)].username,
                            avatar_url=None,
                            equation=(
                                challenge.target_expr
                                if is_solution
                                else f"x + {position / 100:.3f}"
                            ),
                            input_mode="basic",
                            cost=position,
                            error=0 if is_solution else (100 - position) / 1000,
                            submitted_at=now + timedelta(microseconds=position),
                        )
                    )
                    old_rows += 1
                continue

            for index in range(1, archive_count + 1):
                db.add(
                    Submission(
                        user_id=demo_users[(index - 1) % len(demo_users)].id,
                        challenge_id=challenge.id,
                        equation=f"x + {index / 100:.3f}",
                        input_mode="basic",
                        cost=index,
                        error=(archive_count - index + 1) / 1000,
                        submitted_at=now + timedelta(microseconds=index),
                    )
                )
            # Include the official solution as the final, lowest-error point.
            db.add(
                Submission(
                    user_id=demo_users[archive_count % len(demo_users)].id,
                    challenge_id=challenge.id,
                    equation=challenge.target_expr,
                    input_mode="basic",
                    cost=archive_count + 1,
                    error=0,
                    submitted_at=now + timedelta(microseconds=archive_count + 1),
                )
            )
            old_rows += archive_count + 1

        db.commit()
        archived_count = archive_completed_challenges(db, today=today)

        print(f"Seeded {today_count} demo submissions for {today}.")
        print(f"Seeded {old_rows} completed-day demo submissions.")
        print(f"Archived {archived_count} completed challenge(s); each keeps at most 100 rows.")


if __name__ == "__main__":
    args = _arguments()
    main(args.today_count, args.archive_count)
