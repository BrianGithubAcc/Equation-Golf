from datetime import datetime, timedelta, timezone

import pytest

from backend.models import ArchivedLeaderboard, Challenge, Submission, User


def test_health_reports_connected_database(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "connected",
    }


def test_today_challenge_exposes_only_public_fields(client, challenge):
    response = client.get("/api/challenge/today")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "id",
        "date",
        "domain",
        "range",
        "archived",
        "target_points",
    }
    assert body["id"] == challenge.id
    assert body["date"] == str(challenge.challenge_date)
    assert body["domain"] == {"min": -1.0, "max": 1.0}
    assert body["range"] == {"min": -2.0, "max": 2.0}
    assert "target_expr" not in body
    assert "target_latex" not in body


def test_me_is_anonymous_without_session(client):
    response = client.get("/api/me")

    assert response.status_code == 200
    assert response.json() == {"authenticated": False}


def test_me_resolves_authenticated_session(authenticated_client, user):
    response = authenticated_client.get("/api/me")

    assert response.status_code == 200
    assert response.json() == {
        "authenticated": True,
        "user": {
            "id": user.id,
            "username": user.username,
            "avatar_url": user.avatar_url,
        },
    }


def test_bootstrap_combines_challenge_dates_leaderboard_and_session(
    authenticated_client,
    challenge,
    user,
):
    response = authenticated_client.get("/api/bootstrap")

    assert response.status_code == 200
    body = response.json()
    assert body["challenge"]["date"] == str(challenge.challenge_date)
    assert body["challenges"][0]["date"] == str(challenge.challenge_date)
    assert body["leaderboard"]["entries"] == []
    assert body["me"]["authenticated"] is True
    assert body["me"]["user"]["id"] == user.id
    assert "target_expr" not in body["challenge"]
    assert "target_latex" not in body["challenge"]


def test_authenticated_user_can_update_display_name(authenticated_client, user):
    response = authenticated_client.patch(
        "/api/me",
        json={"display_name": "New Player"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["username"] == "New Player"


def test_authenticated_user_can_delete_account_and_anonymize_archive(
    authenticated_client,
    db,
    challenge,
    user,
):
    user_id = user.id
    archived_challenge = Challenge(
        challenge_date=challenge.challenge_date - timedelta(days=1),
        target_expr="x + 2",
        target_latex="x+2",
        domain_min=-1,
        domain_max=1,
        range_min=-2,
        range_max=2,
        archived_at=datetime.now(timezone.utc),
    )
    db.add(archived_challenge)
    db.flush()
    db.add(
        Submission(
            user_id=user.id,
            challenge_id=challenge.id,
            equation="x",
            input_mode="basic",
            error=0,
            cost=1,
        )
    )
    archived_row = ArchivedLeaderboard(
        challenge_id=archived_challenge.id,
        final_position=1,
        user_id=user.id,
        username=user.username,
        avatar_url=user.avatar_url,
        equation="x + 2",
        input_mode="basic",
        error=0,
        cost=3,
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(archived_row)
    db.commit()

    response = authenticated_client.delete("/api/me")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "authenticated": False}
    db.expire_all()
    assert db.get(User, user_id) is None
    assert db.query(Submission).filter_by(user_id=user_id).count() == 0
    saved_archive = db.get(ArchivedLeaderboard, archived_row.id)
    assert saved_archive.user_id is None
    assert saved_archive.username == "Deleted player"
    assert saved_archive.avatar_url is None
    assert saved_archive.equation == "x + 2"
    assert authenticated_client.get("/api/me").json() == {
        "authenticated": False
    }


def test_anonymous_user_cannot_update_display_name(client):
    response = client.patch(
        "/api/me",
        json={"display_name": "New Player"},
    )

    assert response.status_code == 401


def test_anonymous_user_cannot_delete_account(client):
    response = client.delete("/api/me")

    assert response.status_code == 401


def test_authenticated_state_change_rejects_untrusted_origin(
    authenticated_client,
):
    response = authenticated_client.patch(
        "/api/me",
        json={"display_name": "New Player"},
        headers={"Origin": "https://evil.example"},
    )

    assert response.status_code == 403


@pytest.mark.parametrize("display_name", ["fuck", "F.u.c.k", "<script>alert(1)</script>"])
def test_display_name_rejects_inappropriate_or_unsafe_text(
    authenticated_client,
    display_name,
):
    response = authenticated_client.patch(
        "/api/me",
        json={"display_name": display_name},
    )

    assert response.status_code == 400


def test_submit_requires_authentication(client, challenge):
    response = client.post(
        "/api/challenge/today/submit",
        json={"equation": "x", "mode": "basic"},
    )

    assert response.status_code == 401


def test_submit_accepts_and_scores_valid_expression(
    authenticated_client,
    challenge,
):
    response = authenticated_client.post(
        "/api/challenge/today/submit",
        json={"equation": "x", "mode": "basic"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "error": pytest.approx(0),
        "cost": 1,
        "on_pareto_frontier": True,
        "display_position": 1,
    }


@pytest.mark.parametrize(
    "equation",
    [
        "x +",
        "y",
        "unknown_function(x)",
        "+".join(["x"] * 41),
        "x^13",
    ],
)
def test_submit_rejects_invalid_expressions(
    authenticated_client,
    challenge,
    equation,
):
    response = authenticated_client.post(
        "/api/challenge/today/submit",
        json={"equation": equation, "mode": "basic"},
    )

    assert response.status_code == 400


@pytest.mark.parametrize(
    "equation",
    ["sqrt(-1)", "0/0", "log(x)", "exp(1000*x)"],
)
def test_submit_rejects_complex_nan_or_infinite_evaluation(
    authenticated_client,
    challenge,
    equation,
):
    response = authenticated_client.post(
        "/api/challenge/today/submit",
        json={"equation": equation, "mode": "basic"},
    )

    assert response.status_code == 400


def test_submit_calculates_official_error_and_cost(
    authenticated_client,
    challenge,
):
    response = authenticated_client.post(
        "/api/challenge/today/submit",
        json={"equation": "x + 1", "mode": "basic"},
    )

    assert response.status_code == 200
    assert response.json()["error"] == pytest.approx(1.0)
    assert response.json()["cost"] == 3


def test_poor_but_valid_submission_is_accepted(
    authenticated_client,
    challenge,
):
    response = authenticated_client.post(
        "/api/challenge/today/submit",
        json={"equation": "x + 1", "mode": "basic"},
    )

    assert response.status_code == 200
    assert response.json()["error"] > 0.01


def test_today_leaderboard_is_pareto_paginated_and_ordered(
    client,
    db,
    challenge,
    user,
):
    from datetime import datetime, timedelta, timezone

    rows = [
        Submission(
            user_id=user.id,
            challenge_id=challenge.id,
            equation=f"x + {index}",
            input_mode="basic",
            cost=index,
            error=float(10 - index),
            submitted_at=datetime.now(timezone.utc) + timedelta(seconds=index),
        )
        for index in range(1, 6)
    ]
    rows.append(
        Submission(
            user_id=user.id,
            challenge_id=challenge.id,
            equation="x + 99",
            input_mode="basic",
            cost=6,
            error=20,
            submitted_at=datetime.now(timezone.utc),
        )
    )
    db.add_all(rows)
    db.commit()

    response = client.get(
        "/api/challenge/today/leaderboard?limit=2&offset=1"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5
    assert [entry["rank"] for entry in body["entries"]] == [2, 3]
    assert [entry["cost"] for entry in body["entries"]] == [2, 3]
    assert [entry["error"] for entry in body["entries"]] == [8.0, 7.0]
    assert all("equation" not in entry for entry in body["entries"])


def test_submission_rate_limit_returns_429(authenticated_client, challenge, monkeypatch):
    from backend import main

    main.SUBMISSION_RATE_LIMITS.clear()
    try:
        responses = [
            authenticated_client.post(
                "/api/challenge/today/submit",
                json={"equation": "x", "mode": "basic"},
            )
            for _ in range(main.SUBMISSION_USER_LIMIT + 1)
        ]
    finally:
        main.SUBMISSION_RATE_LIMITS.clear()

    assert responses[-1].status_code == 429


def test_today_leaderboard_rejects_limit_over_max(client):
    response = client.get(
        "/api/challenge/today/leaderboard?limit=5001"
    )

    assert response.status_code == 422


def test_challenge_browser_lists_only_public_metadata(client, db, challenge):
    db_challenge = Challenge(
        challenge_date=challenge.challenge_date + timedelta(days=1),
        target_expr="x + 1",
        target_latex="x+1",
        domain_min=-1,
        domain_max=1,
        range_min=-2,
        range_max=2,
    )
    db.add(db_challenge)
    db.commit()

    response = client.get("/api/challenges")

    assert response.status_code == 200
    body = response.json()
    assert [row["date"] for row in body["challenges"]] == [
        str(challenge.challenge_date),
    ]
    assert "target_expr" not in body["challenges"][0]
    assert "target_latex" not in body["challenges"][0]


def test_dated_leaderboard_hides_unarchived_target(client, challenge):
    response = client.get(
        f"/api/challenge/{challenge.challenge_date}/leaderboard"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["challenge"]["date"] == str(challenge.challenge_date)
    assert "target_expr" not in body["challenge"]
    assert "target_latex" not in body["challenge"]


def test_dated_leaderboard_rejects_future_dates(client, db, challenge):
    future = Challenge(
        challenge_date=challenge.challenge_date + timedelta(days=1),
        target_expr="x + 99",
        target_latex="x+99",
        domain_min=-1,
        domain_max=1,
        range_min=-2,
        range_max=2,
        archived_at=datetime.now(timezone.utc),
    )
    db.add(future)
    db.commit()

    response = client.get(f"/api/challenge/{future.challenge_date}/leaderboard")

    assert response.status_code == 404
