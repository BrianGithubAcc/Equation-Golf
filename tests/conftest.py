import base64
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from itsdangerous import TimestampSigner
from sqlalchemy import create_engine, delete, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parents[1]))

from backend import main
from backend.models import ArchivedLeaderboard, Challenge, Submission, User


DEFAULT_DATABASE_URL = (
    "postgresql+psycopg://equationgolf:equationgolf"
    "@127.0.0.1:5432/equationgolf"
)
DEVELOPMENT_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    DEFAULT_DATABASE_URL,
)
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    make_url(DEVELOPMENT_DATABASE_URL)
    .set(database="equationgolf_test")
    .render_as_string(hide_password=False),
)


def _database_identity(url):
    parsed = make_url(url)
    return parsed.host, parsed.port, parsed.database


def _ensure_database(url):
    engine = create_engine(url)
    try:
        with engine.connect():
            return engine, False
    except Exception:
        parsed = make_url(url)
        database = parsed.database
        if not database or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", database):
            engine.dispose()
            raise RuntimeError("TEST_DATABASE_URL must name a safe database")

        maintenance_engine = create_engine(
            parsed.set(database="postgres"),
        )
        try:
            with maintenance_engine.connect() as connection:
                connection = connection.execution_options(
                    isolation_level="AUTOCOMMIT",
                )
                exists = connection.scalar(
                    text(
                        "SELECT 1 FROM pg_database WHERE datname = :database"
                    ),
                    {"database": database},
                )
                if not exists:
                    connection.exec_driver_sql(
                        f'CREATE DATABASE "{database}"'
                    )
        finally:
            maintenance_engine.dispose()

        return engine, True


@pytest.fixture(scope="session")
def test_engine():
    if _database_identity(TEST_DATABASE_URL) == _database_identity(
        DEVELOPMENT_DATABASE_URL
    ):
        pytest.fail("TEST_DATABASE_URL must be separate from DATABASE_URL")

    engine, created = _ensure_database(TEST_DATABASE_URL)
    alembic_config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    alembic_config.set_main_option(
        "sqlalchemy.url",
        TEST_DATABASE_URL.replace("%", "%%"),
    )

    try:
        command.upgrade(alembic_config, "head")
        yield engine
    finally:
        try:
            command.downgrade(alembic_config, "base")
        finally:
            engine.dispose()
            if created:
                parsed = make_url(TEST_DATABASE_URL)
                maintenance_engine = create_engine(
                    parsed.set(database="postgres"),
                )
                try:
                    with maintenance_engine.connect() as connection:
                        connection = connection.execution_options(
                            isolation_level="AUTOCOMMIT",
                        )
                        connection.exec_driver_sql(
                            f'DROP DATABASE IF EXISTS "{parsed.database}"'
                        )
                finally:
                    maintenance_engine.dispose()


@pytest.fixture
def db(test_engine):
    with test_engine.begin() as connection:
        connection.execute(delete(Submission))
        connection.execute(delete(ArchivedLeaderboard))
        connection.execute(delete(User))
        connection.execute(delete(Challenge))

    factory = sessionmaker(
        bind=test_engine,
        autoflush=False,
        expire_on_commit=False,
    )
    with factory() as session:
        yield session
        session.rollback()


@pytest.fixture
def client(test_engine, db, monkeypatch):
    factory = sessionmaker(
        bind=test_engine,
        autoflush=False,
        expire_on_commit=False,
    )
    monkeypatch.setattr(main, "SessionLocal", factory)

    with TestClient(main.app) as test_client:
        yield test_client


@pytest.fixture
def challenge(db):
    challenge = Challenge(
        challenge_date=datetime.now(timezone.utc).date(),
        target_expr="x",
        target_latex="x",
        domain_min=-1,
        domain_max=1,
        range_min=-2,
        range_max=2,
    )
    db.add(challenge)
    db.commit()
    db.refresh(challenge)
    return challenge


@pytest.fixture
def user(db):
    user = User(
        google_sub="test-google-sub",
        username="Test Player",
        avatar_url="https://example.test/avatar.png",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(test_client, user):
    payload = base64.b64encode(
        json.dumps({"user_id": user.id}).encode()
    )
    cookie = TimestampSigner(main.SESSION_SECRET).sign(payload).decode()
    test_client.cookies.set("session", cookie)


@pytest.fixture
def authenticated_client(client, user):
    authenticate(client, user)
    return client
