"""Safely import the reviewed production challenge JSON into the database."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from dotenv import load_dotenv
from sqlalchemy import select

load_dotenv()

from .models import Challenge  # noqa: E402


@dataclass(frozen=True)
class ImportAction:
    operation: str
    record: dict
    existing_id: int | None = None


def _record_date(record: dict):
    from datetime import date

    return date.fromisoformat(record["challenge_date"])


def build_import_plan(db, records: Iterable[dict], replace: bool = False) -> list[ImportAction]:
    """Build a no-write plan, skipping existing dates unless replacing."""

    records = list(records)
    dates = [_record_date(record) for record in records]
    existing_rows = db.scalars(
        select(Challenge).where(Challenge.challenge_date.in_(dates))
    ).all()
    existing_by_date = {row.challenge_date: row for row in existing_rows}

    plan: list[ImportAction] = []
    for record in records:
        existing = existing_by_date.get(_record_date(record))
        if existing is None:
            operation = "insert"
            existing_id = None
        elif replace:
            operation = "replace"
            existing_id = existing.id
        else:
            operation = "skip"
            existing_id = existing.id
        plan.append(ImportAction(operation, record, existing_id))
    return plan


def describe_plan(plan: Iterable[ImportAction], printer: Callable[[str], None] = print) -> None:
    plan = list(plan)
    for action in plan:
        date = action.record["challenge_date"]
        expression = action.record["target_expr"]
        if action.operation == "insert":
            printer(f"INSERT {date}: {expression}")
        elif action.operation == "replace":
            printer(f"REPLACE id={action.existing_id} {date}: {expression}")
        else:
            printer(f"SKIP existing id={action.existing_id} {date}")
    insert_count = sum(action.operation == "insert" for action in plan)
    replace_count = sum(action.operation == "replace" for action in plan)
    skip_count = sum(action.operation == "skip" for action in plan)
    printer(
        f"Plan: {insert_count} insert, {replace_count} replace, {skip_count} skip"
    )


def _apply_plan(db, plan: Iterable[ImportAction]) -> None:
    for action in plan:
        if action.operation == "insert":
            db.add(
                Challenge(
                    challenge_date=_record_date(action.record),
                    target_expr=action.record["target_expr"],
                    target_latex=action.record["target_latex"],
                    domain_min=action.record["domain_min"],
                    domain_max=action.record["domain_max"],
                    range_min=action.record["range_min"],
                    range_max=action.record["range_max"],
                )
            )
        elif action.operation == "replace":
            existing = db.get(Challenge, action.existing_id)
            if existing is None:
                raise RuntimeError(
                    f"challenge id {action.existing_id} changed during import"
                )
            existing.target_expr = action.record["target_expr"]
            existing.target_latex = action.record["target_latex"]
            existing.domain_min = action.record["domain_min"]
            existing.domain_max = action.record["domain_max"]
            existing.range_min = action.record["range_min"]
            existing.range_max = action.record["range_max"]
    db.commit()


def import_file(
    path: str | Path,
    session_factory,
    *,
    apply: bool,
    replace: bool = False,
    printer: Callable[[str], None] = print,
) -> list[ImportAction]:
    """Validate, print, and optionally apply an import plan.

    The plan is built and printed before any object is added or updated.  A
    second plan is built immediately before applying, so a repeated invocation
    is naturally idempotent and the unique date constraint remains the final
    protection against accidental duplicates.
    """

    from .production_challenges import load_and_validate

    records = load_and_validate(path)
    return import_records(
        records,
        session_factory,
        apply=apply,
        replace=replace,
        printer=printer,
    )


def import_records(
    records: Iterable[dict],
    session_factory,
    *,
    apply: bool,
    replace: bool = False,
    printer: Callable[[str], None] = print,
) -> list[ImportAction]:
    """Preview or apply already-validated records.

    ``import_file`` is the production entry point and validates the complete
    365-record file first.  This smaller function keeps the database safety
    behavior directly testable without requiring a database fixture to load
    the full artifact for every unit test.
    """

    records = list(records)
    with session_factory() as db:
        plan = build_import_plan(db, records, replace=replace)
        describe_plan(plan, printer=printer)
        if not apply:
            printer("Dry run: no database changes made")
            return plan

        # Re-read the plan just before writing in case another process inserted
        # a date after the preview query.
        plan = build_import_plan(db, records, replace=replace)
        _apply_plan(db, plan)
        printer("Applied database changes")
        return plan


def _cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        type=Path,
        nargs="?",
        default=Path("data/production_challenges.json"),
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="replace existing dates; without this flag existing rows are skipped",
    )
    return parser


def main() -> None:
    args = _cli().parse_args()
    if not os.getenv("DATABASE_URL"):
        raise SystemExit(
            "DATABASE_URL must be set explicitly; refusing to use a default database"
        )

    # Import only after the explicit DATABASE_URL check.  The normal database
    # module still owns URL normalization and engine configuration.
    from .database import SessionLocal

    import_file(
        args.path,
        SessionLocal,
        apply=args.apply,
        replace=args.replace,
    )


if __name__ == "__main__":
    main()
