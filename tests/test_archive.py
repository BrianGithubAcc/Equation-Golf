from datetime import date, datetime, timedelta, timezone

from backend.archive_completed_challenges import archive_completed_challenges
from backend.models import ArchivedLeaderboard, Challenge, Submission


def test_completed_challenge_archives_top_100_prunes_raw_data_and_is_idempotent(
    client,
    db,
    challenge,
    user,
):
    yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
    old_challenge = Challenge(
        challenge_date=yesterday,
        target_expr="x + 2",
        target_latex="x+2",
        domain_min=-2,
        domain_max=2,
        range_min=-3,
        range_max=3,
    )
    db.add(old_challenge)
    db.commit()
    db.refresh(old_challenge)

    submissions = [
        Submission(
            user_id=user.id,
            challenge_id=old_challenge.id,
            equation=f"x + {index}",
            input_mode="basic",
            cost=index,
            error=float(102 - index),
            submitted_at=datetime.now(timezone.utc) + timedelta(seconds=index),
        )
        for index in range(1, 102)
    ]
    today_submission = Submission(
        user_id=user.id,
        challenge_id=challenge.id,
        equation="x",
        input_mode="basic",
        cost=1,
        error=0,
        submitted_at=datetime.now(timezone.utc),
    )
    db.add_all([*submissions, today_submission])
    db.commit()

    assert archive_completed_challenges(db, today=yesterday + timedelta(days=1)) == 1
    assert db.query(ArchivedLeaderboard).filter_by(
        challenge_id=old_challenge.id
    ).count() == 100
    assert db.query(Submission).filter_by(
        challenge_id=old_challenge.id
    ).count() == 0
    assert db.query(Submission).filter_by(
        challenge_id=challenge.id
    ).count() == 1

    assert archive_completed_challenges(db, today=yesterday + timedelta(days=1)) == 0
    assert db.query(ArchivedLeaderboard).filter_by(
        challenge_id=old_challenge.id
    ).count() == 100

    response = client.get("/api/challenge/yesterday")

    assert response.status_code == 200
    body = response.json()
    assert body["date"] == str(yesterday)
    assert body["target_expr"] == "x + 2"
    assert body["target_latex"] == "x+2"
    assert len(body["leaderboard"]) == 100
    assert body["leaderboard"][0]["rank"] == 1
    assert body["leaderboard"][-1]["rank"] == 100

    browse_response = client.get(
        f"/api/challenge/{yesterday}/leaderboard"
    )
    assert browse_response.status_code == 200
    browse_body = browse_response.json()
    assert browse_body["challenge"]["target_expr"] == "x + 2"
    assert len(browse_body["entries"]) == 100
    assert browse_body["entries"][0]["rank"] == 1
    assert browse_body["entries"][0]["equation"] == "x + 1"


def test_archive_uses_supplied_utc_rollover_date(db):
    current = date(2026, 9, 15)
    previous = Challenge(
        challenge_date=date(2026, 9, 14),
        target_expr="x",
        target_latex="x",
        domain_min=-1,
        domain_max=1,
        range_min=-1,
        range_max=1,
    )
    same_day = Challenge(
        challenge_date=current,
        target_expr="x + 1",
        target_latex="x+1",
        domain_min=-1,
        domain_max=1,
        range_min=-1,
        range_max=1,
    )
    db.add_all([previous, same_day])
    db.commit()

    assert archive_completed_challenges(db, today=current) == 1
    assert previous.archived_at is not None
    assert same_day.archived_at is None
