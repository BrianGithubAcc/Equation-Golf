from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.import_production_challenges import (
    _apply_plan,
    build_import_plan,
    describe_plan,
    import_records,
)
from backend.models import Base, Challenge
from backend.production_challenges import generate_challenges, validate_records


TEST_SEED = 3141592653


def test_checked_in_production_file_has_365_consecutive_valid_challenges():
    utc_today = datetime.now(timezone.utc).date()
    records = generate_challenges(
        start_date=utc_today,
        count=365,
        seed=TEST_SEED,
    )

    assert len(records) == 365
    assert records[0]["challenge_date"] == utc_today.isoformat()
    assert records[-1]["challenge_date"] == (
        utc_today + timedelta(days=364)
    ).isoformat()


def test_generation_is_deterministic_and_uses_more_than_365_candidates():
    from backend.production_challenges import _candidate_stream

    first = generate_challenges(
        start_date=date(2030, 1, 1),
        count=20,
        candidate_count_per_family=25,
        seed=TEST_SEED,
    )
    second = generate_challenges(
        start_date=date(2030, 1, 1),
        count=20,
        candidate_count_per_family=25,
        seed=TEST_SEED,
    )

    assert first == second
    assert len(_candidate_stream(TEST_SEED)) > 365
    assert len({record["challenge_date"] for record in first}) == 20


def test_validation_rejects_duplicate_normalized_expressions():
    records = generate_challenges(
        start_date=date(2030, 1, 1),
        count=10,
        candidate_count_per_family=15,
        seed=TEST_SEED,
    )
    records[1]["target_expr"] = records[0]["target_expr"]

    with pytest.raises(ValueError, match="duplicate normalized expression"):
        validate_records(records, expected_count=10)


def _record(day: str, expression: str = "x"):
    return {
        "challenge_date": day,
        "target_expr": expression,
        "target_latex": expression,
        "domain_min": -1.0,
        "domain_max": 1.0,
        "range_min": -1.1,
        "range_max": 1.1,
    }


@pytest.fixture
def challenge_session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        engine.dispose()


def test_importer_dry_run_and_repeat_are_non_destructive(challenge_session):
    records = [_record("2030-01-01"), _record("2030-01-02", "x + 1")]
    messages = []

    plan = import_records(
        records,
        challenge_session,
        apply=False,
        printer=messages.append,
    )
    assert [action.operation for action in plan] == ["insert", "insert"]
    with challenge_session() as db:
        assert db.scalars(select(Challenge)).all() == []

    assert messages[0].startswith("INSERT 2030-01-01")

    with challenge_session() as db:
        _apply_plan(db, plan)
        repeated = build_import_plan(db, records)
        assert [action.operation for action in repeated] == ["skip", "skip"]


def test_importer_does_not_overwrite_without_replace_and_does_with_replace(
    challenge_session,
):
    records = [_record("2030-01-01", "x + 2")]
    with challenge_session() as db:
        db.add(
            Challenge(
                challenge_date=date(2030, 1, 1),
                target_expr="x",
                target_latex="x",
                domain_min=-1,
                domain_max=1,
                range_min=-1,
                range_max=1,
            )
        )
        db.commit()

        no_replace = build_import_plan(db, records, replace=False)
        assert no_replace[0].operation == "skip"
        _apply_plan(db, no_replace)
        assert db.scalar(select(Challenge).where(Challenge.challenge_date == date(2030, 1, 1))).target_expr == "x"

        replace = build_import_plan(db, records, replace=True)
        assert replace[0].operation == "replace"
        _apply_plan(db, replace)
        assert db.scalar(select(Challenge).where(Challenge.challenge_date == date(2030, 1, 1))).target_expr == "x + 2"
