"""Generate and import the initial private production challenge set."""

from __future__ import annotations

import os

if not os.getenv("DATABASE_URL"):
    raise SystemExit("DATABASE_URL must be set explicitly")
if not os.getenv("PRODUCTION_CHALLENGE_SEED"):
    raise SystemExit("PRODUCTION_CHALLENGE_SEED must be set and kept private")

from backend.database import SessionLocal
from backend.import_production_challenges import import_records
from backend.production_challenges import generate_challenges


def main() -> None:
    records = generate_challenges()
    plan = import_records(
        records,
        SessionLocal,
        apply=True,
        printer=lambda _: None,
    )
    inserted = sum(action.operation == "insert" for action in plan)
    skipped = sum(action.operation == "skip" for action in plan)
    print(
        f"Initialized {inserted} production challenges; "
        f"skipped {skipped} existing dates."
    )


if __name__ == "__main__":
    main()
