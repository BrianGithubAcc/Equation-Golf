"""Apply the small schema migration needed by the MVP scoring model."""

from sqlalchemy import inspect, text

from .database import engine


def main():
    inspector = inspect(engine)

    with engine.begin() as connection:
        users_columns = {
            column["name"]
            for column in inspector.get_columns("users")
        }

        if "google_sub" not in users_columns:
            connection.execute(
                text(
                    "ALTER TABLE users "
                    "ADD COLUMN google_sub VARCHAR(255)"
                )
            )

        if {"provider", "provider_user_id"}.issubset(
            users_columns
        ):
            connection.execute(
                text(
                    "UPDATE users SET google_sub = CASE "
                    "WHEN provider = 'google' THEN provider_user_id "
                    "ELSE provider || ':' || provider_user_id END "
                    "WHERE google_sub IS NULL"
                )
            )
        elif "provider_user_id" in users_columns:
            connection.execute(
                text(
                    "UPDATE users SET google_sub = provider_user_id "
                    "WHERE google_sub IS NULL"
                )
            )

        connection.execute(
            text(
                "ALTER TABLE users ALTER COLUMN google_sub SET NOT NULL"
            )
        )

        users_constraints = inspector.get_unique_constraints("users")
        if any(
            constraint["name"] == "uq_user_provider"
            for constraint in users_constraints
        ):
            connection.execute(
                text(
                    "ALTER TABLE users DROP CONSTRAINT uq_user_provider"
                )
            )

        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "ix_users_google_sub ON users (google_sub)"
            )
        )

        fresh_users_columns = {
            column["name"]
            for column in inspect(connection).get_columns("users")
        }
        for column_name in (
            "provider",
            "email",
            "provider_user_id",
            "access_token",
            "refresh_token",
            "id_token",
        ):
            if column_name in fresh_users_columns:
                connection.execute(
                    text(
                        f"ALTER TABLE users DROP COLUMN {column_name}"
                    )
                )

        submissions_columns = {
            column["name"]
            for column in inspector.get_columns("submissions")
        }
        if "cost" not in submissions_columns:
            if "golf_length" in submissions_columns:
                connection.execute(
                    text(
                        "ALTER TABLE submissions "
                        "RENAME COLUMN golf_length TO cost"
                    )
                )
            else:
                connection.execute(
                    text(
                        "ALTER TABLE submissions "
                        "ADD COLUMN cost INTEGER NOT NULL DEFAULT 1"
                    )
                )

        submission_constraints = inspector.get_unique_constraints(
            "submissions"
        )
        if any(
            constraint["name"] == "uq_user_challenge_submission"
            for constraint in submission_constraints
        ):
            connection.execute(
                text(
                    "ALTER TABLE submissions "
                    "DROP CONSTRAINT uq_user_challenge_submission"
                )
            )

    print("Database migration applied.")


if __name__ == "__main__":
    main()
