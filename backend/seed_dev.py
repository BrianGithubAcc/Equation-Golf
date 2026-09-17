"""Apply the schema and seed the development challenge data."""

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from sqlalchemy.engine import make_url


load_dotenv()

from .database import DATABASE_URL  # noqa: E402
from .seed import main as seed_challenges  # noqa: E402


def _database_identity(url):
    parsed = make_url(url)
    return parsed.host, parsed.port, parsed.database


def main():
    if os.getenv("APP_ENV", "development").lower() != "development":
        raise RuntimeError(
            "Development seeding requires APP_ENV=development"
        )

    test_url = os.getenv("TEST_DATABASE_URL")
    if (
        test_url
        and _database_identity(DATABASE_URL) == _database_identity(test_url)
    ) or (make_url(DATABASE_URL).database or "").endswith("_test"):
        raise RuntimeError("Refusing to seed a test database")

    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option(
        "sqlalchemy.url",
        DATABASE_URL.replace("%", "%%"),
    )
    command.upgrade(config, "head")
    seed_challenges()


if __name__ == "__main__":
    main()
