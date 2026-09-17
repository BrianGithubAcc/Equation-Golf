"""Load a privately supplied production challenge artifact for development."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from sqlalchemy import select

from .database import SessionLocal
from .models import Challenge
from .production_challenges import load_and_validate


DEFAULT_CHALLENGE_FILE = (
    Path(__file__).parents[1] / "data" / "production_challenges.json"
)


def main(path: str | Path = DEFAULT_CHALLENGE_FILE):
    path = Path(path)
    if not path.exists():
        raise RuntimeError(
            f"Private challenge file is missing: {path}. "
            "Generate or securely copy it before seeding."
        )

    records = load_and_validate(path)
    with SessionLocal() as db:
        for record in records:
            challenge_date = date.fromisoformat(record["challenge_date"])
            existing = db.scalar(
                select(Challenge).where(
                    Challenge.challenge_date == challenge_date
                )
            )
            values = {
                "target_expr": record["target_expr"],
                "target_latex": record["target_latex"],
                "domain_min": record["domain_min"],
                "domain_max": record["domain_max"],
                "range_min": record["range_min"],
                "range_max": record["range_max"],
            }
            if existing:
                for field, value in values.items():
                    setattr(existing, field, value)
                print("Updated:", record["challenge_date"])
                continue

            db.add(
                Challenge(
                    challenge_date=challenge_date,
                    **values,
                )
            )
            print("Added:", record["challenge_date"])

        db.commit()


if __name__ == "__main__":
    main()
