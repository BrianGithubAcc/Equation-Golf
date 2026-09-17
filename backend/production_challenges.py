"""Generate and validate the production Equation Golf challenge set.

This module deliberately keeps challenge generation separate from the small,
development-only seed modules.  It uses the same parser, compiler, and target
sampling implementation as the application so a generated target is checked
against the code that scores it.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable

from sympy import latex
from sympy.printing.repr import srepr

from .main import compile_target, parse_basic_expression, sample_target


GENERATOR_VERSION = "1"
CHALLENGE_COUNT = 365
DEFAULT_OUTPUT = Path("data/production_challenges.json")

# The application scores at 0.05 x intervals.  These extra points catch sharp
# features between scoring points and make the validation useful to reviewers.
DENSE_SAMPLE_COUNT = 1601
MAX_ABS_GRAPH_VALUE = 25.0
MIN_GRAPH_SPAN = 0.18
MIN_GRAPH_STANDARD_DEVIATION = 0.045

FAMILIES = (
    "polynomial",
    "rational",
    "trigonometric",
    "damped_trigonometric",
    "exponential",
    "logarithmic",
    "square_root",
    "absolute_value",
    "tangent",
    "composition",
)


def _number(value: float) -> str:
    """Render a compact finite decimal accepted by the basic parser."""

    if abs(value) < 0.00005:
        value = 0.0
    return f"{value:.4f}".rstrip("0").rstrip(".")


def _signed_terms(*terms: tuple[float, str]) -> str:
    """Join coefficient/expression pairs without producing ``+ -`` text."""

    rendered: list[str] = []
    for coefficient, expression in terms:
        if not math.isfinite(coefficient) or coefficient == 0:
            continue
        magnitude = _number(abs(coefficient))
        if expression == "1":
            term = magnitude
        elif abs(abs(coefficient) - 1.0) < 0.00005:
            term = expression
        else:
            term = f"{magnitude}*{expression}"
        if not rendered:
            rendered.append(f"-{term}" if coefficient < 0 else term)
        else:
            rendered.append(("- " if coefficient < 0 else "+ ") + term)
    return " ".join(rendered) or "0"


def _signed_offset(value: float) -> str:
    return f" + {_number(value)}" if value >= 0 else f" - {_number(abs(value))}"


def _x_minus(value: float) -> str:
    return f"x - {_number(value)}" if value >= 0 else f"x + {_number(abs(value))}"


def _random_domain(rng: random.Random, low: int = 4, high: int = 7) -> tuple[float, float]:
    half_width = rng.randint(low, high)
    return -float(half_width), float(half_width)


def _polynomial(rng: random.Random) -> tuple[str, tuple[float, float]]:
    domain = _random_domain(rng, 3, 5)
    coefficients = (
        rng.uniform(-0.06, 0.06),
        rng.uniform(-0.16, 0.16),
        rng.uniform(-0.65, 0.65),
        rng.uniform(-0.9, 0.9),
    )
    expression = _signed_terms(
        (coefficients[0], "x**3"),
        (coefficients[1], "x**2"),
        (coefficients[2], "x"),
        (coefficients[3], "1"),
    )
    return expression, domain


def _rational(rng: random.Random) -> tuple[str, tuple[float, float]]:
    domain = _random_domain(rng, 4, 7)
    shift = rng.uniform(0.5, 2.2)
    scale = rng.uniform(0.7, 2.0)
    expression = _signed_terms(
        (rng.uniform(0.45, 1.2), f"x/({scale:.4f}+x**2)"),
        (rng.uniform(-1.0, 1.0), f"1/({shift:.4f}+x**2)"),
        (rng.uniform(-0.16, 0.16), "x"),
        (rng.uniform(-0.7, 0.7), "1"),
    )
    return expression, domain


def _trigonometric(rng: random.Random) -> tuple[str, tuple[float, float]]:
    domain = _random_domain(rng, 5, 8)
    expression = _signed_terms(
        (rng.uniform(0.35, 1.05), f"sin({_number(rng.uniform(0.35, 1.25))}*x{_signed_offset(rng.uniform(-1, 1))})"),
        (rng.uniform(0.15, 0.65), f"cos({_number(rng.uniform(0.8, 2.7))}*x{_signed_offset(rng.uniform(-1, 1))})"),
        (rng.uniform(-0.08, 0.08), "x"),
        (rng.uniform(-0.4, 0.4), "1"),
    )
    return expression, domain


def _damped_trigonometric(rng: random.Random) -> tuple[str, tuple[float, float]]:
    domain = _random_domain(rng, 5, 7)
    center = rng.uniform(-2.0, 2.0)
    width = rng.uniform(1.4, 4.0)
    carrier = _signed_terms(
        (rng.uniform(0.4, 1.1), f"sin({_number(rng.uniform(0.45, 1.3))}*x{_signed_offset(rng.uniform(-1, 1))})"),
        (rng.uniform(0.15, 0.55), f"cos({_number(rng.uniform(1.3, 3.0))}*x{_signed_offset(rng.uniform(-1, 1))})"),
    )
    expression = _signed_terms(
        (1.0, f"exp(-(({_x_minus(center)})**2)/{_number(width)})*({carrier})"),
        (rng.uniform(-0.12, 0.12), "x"),
        (rng.uniform(-0.5, 0.5), "1"),
    )
    return expression, domain


def _exponential(rng: random.Random) -> tuple[str, tuple[float, float]]:
    domain = _random_domain(rng, 2, 4)
    expression = _signed_terms(
        (rng.uniform(0.12, 0.5), f"exp({_number(rng.uniform(0.18, 0.55))}*x)"),
        (rng.uniform(0.12, 0.5), f"exp(-{_number(rng.uniform(0.18, 0.65))}*x)"),
        (rng.uniform(-0.12, 0.12), "x"),
        (rng.uniform(-0.8, 0.8), "1"),
    )
    return expression, domain


def _logarithmic(rng: random.Random) -> tuple[str, tuple[float, float]]:
    domain = _random_domain(rng, 4, 6)
    left_shift = rng.uniform(5.5, 8.5)
    right_shift = rng.uniform(5.5, 8.5)
    expression = _signed_terms(
        (rng.uniform(0.35, 0.95), f"log(x+{_number(left_shift)})"),
        (rng.uniform(-0.75, 0.75), f"log({_number(right_shift)}-x)"),
        (rng.uniform(0.18, 0.65), f"sin({_number(rng.uniform(0.35, 1.1))}*x)"),
        (rng.uniform(-0.5, 0.5), "1"),
    )
    return expression, domain


def _square_root(rng: random.Random) -> tuple[str, tuple[float, float]]:
    domain = _random_domain(rng, 4, 6)
    left_shift = rng.uniform(5.5, 8.5)
    right_shift = rng.uniform(5.5, 8.5)
    expression = _signed_terms(
        (rng.uniform(0.18, 0.75), f"sqrt(x+{_number(left_shift)})"),
        (rng.uniform(-0.65, 0.65), f"sqrt({_number(right_shift)}-x)"),
        (rng.uniform(0.12, 0.5), f"cos({_number(rng.uniform(0.35, 1.2))}*x)"),
        (rng.uniform(-0.7, 0.7), "1"),
    )
    return expression, domain


def _absolute_value(rng: random.Random) -> tuple[str, tuple[float, float]]:
    domain = _random_domain(rng, 4, 7)
    first_center = rng.uniform(-2.5, 2.5)
    second_center = rng.uniform(-2.5, 2.5)
    expression = _signed_terms(
        (rng.uniform(0.15, 0.75), f"abs({_x_minus(first_center)})"),
        (rng.uniform(-0.5, 0.5), f"abs({_x_minus(-second_center)})"),
        (rng.uniform(0.2, 0.75), f"sin({_number(rng.uniform(0.3, 1.1))}*x)"),
        (rng.uniform(-0.5, 0.5), "1"),
    )
    return expression, domain


def _tangent(rng: random.Random) -> tuple[str, tuple[float, float]]:
    domain = _random_domain(rng, 4, 6)
    # The argument remains inside roughly [-1.1, 1.1], well away from tan's
    # poles, over every generated domain.
    frequency = rng.uniform(0.08, 0.16)
    phase = rng.uniform(-0.25, 0.25)
    expression = _signed_terms(
        (rng.uniform(0.3, 0.9), f"tan({_number(frequency)}*x{_signed_offset(phase)})"),
        (rng.uniform(0.15, 0.6), f"cos({_number(rng.uniform(0.5, 1.5))}*x)"),
        (rng.uniform(-0.08, 0.08), "x"),
        (rng.uniform(-0.5, 0.5), "1"),
    )
    return expression, domain


def _composition(rng: random.Random) -> tuple[str, tuple[float, float]]:
    domain = _random_domain(rng, 4, 6)
    shift = rng.uniform(5.5, 8.0)
    expression = _signed_terms(
        (rng.uniform(0.25, 0.8), f"sin(sqrt(x+{_number(shift)}))"),
        (rng.uniform(0.15, 0.65), f"log(exp({_number(rng.uniform(0.1, 0.35))}*x)+{_number(rng.uniform(1.4, 3.5))})"),
        (rng.uniform(0.12, 0.45), f"exp(-abs({_x_minus(rng.uniform(-2, 2))}))"),
        (rng.uniform(-0.5, 0.5), "1"),
    )
    return expression, domain


FAMILY_BUILDERS: dict[str, Callable[[random.Random], tuple[str, tuple[float, float]]]] = {
    "polynomial": _polynomial,
    "rational": _rational,
    "trigonometric": _trigonometric,
    "damped_trigonometric": _damped_trigonometric,
    "exponential": _exponential,
    "logarithmic": _logarithmic,
    "square_root": _square_root,
    "absolute_value": _absolute_value,
    "tangent": _tangent,
    "composition": _composition,
}


def normalized_expression(expression: str) -> str:
    """Return a canonical symbolic fingerprint for duplicate checks.

    ``parse_basic_expression`` constructs canonical SymPy Add/Mul/Pow nodes,
    which catches formatting-only variants without invoking the very expensive
    general-purpose ``simplify`` routine.  The validation pass also keeps a
    numeric fingerprint, catching equivalent forms such as identities that
    are not reduced by SymPy's basic constructors.
    """

    parsed = parse_basic_expression(expression)
    return srepr(parsed)


def _numeric_fingerprint(expression: str) -> tuple[float, ...]:
    function = compile_target(expression)
    points = (-6.25, -4.5, -2.75, -1.0, 0.0, 1.25, 3.0, 4.75, 6.5)
    return tuple(round(float(function(point)), 7) for point in points)


def _evaluate_dense(expression: str, domain: tuple[float, float]) -> list[float]:
    minimum_x, maximum_x = domain
    if not minimum_x < maximum_x:
        raise ValueError("Domain minimum must be less than maximum")

    function = compile_target(expression)
    values: list[float] = []
    for index in range(DENSE_SAMPLE_COUNT):
        current_x = minimum_x + (maximum_x - minimum_x) * index / (DENSE_SAMPLE_COUNT - 1)
        try:
            value = function(current_x)
            if isinstance(value, complex):
                raise ValueError("complex graph value")
            value = float(value)
        except (ValueError, ZeroDivisionError, OverflowError, TypeError) as error:
            raise ValueError(f"undefined graph value at x={current_x}") from error
        if not math.isfinite(value):
            raise ValueError(f"non-finite graph value at x={current_x}")
        if abs(value) > MAX_ABS_GRAPH_VALUE:
            raise ValueError("graph value is too large")
        values.append(value)
    return values


def _derive_range(values: list[float]) -> tuple[float, float]:
    minimum = min(values)
    maximum = max(values)
    span = maximum - minimum
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    if span < MIN_GRAPH_SPAN:
        raise ValueError("graph is effectively constant")
    if math.sqrt(variance) < MIN_GRAPH_STANDARD_DEVIATION:
        raise ValueError("graph has too little variation")

    padding = max(0.1, span * 0.08)
    range_min = round(minimum - padding, 4)
    range_max = round(maximum + padding, 4)
    if not math.isfinite(range_min) or not math.isfinite(range_max) or range_min >= range_max:
        raise ValueError("invalid graph range")
    return range_min, range_max


def validate_candidate(expression: str, domain: tuple[float, float]) -> tuple[float, float]:
    """Parse, compile, fully sample, and derive a padded graph range."""

    if len(expression) > 200:
        raise ValueError("expression is too long")
    parse_basic_expression(expression)
    # sample_target is the production path used by the API.  Requiring every
    # scoring point to be present catches cases that its public helper skips.
    scoring_points = sample_target(expression, domain[0], domain[1])
    expected_points = round((domain[1] - domain[0]) / 0.05) + 1
    if len(scoring_points) != expected_points:
        raise ValueError("expression is not defined over the scoring domain")
    values = _evaluate_dense(expression, domain)
    return _derive_range(values)


def _resolve_seed(seed: int | None) -> int:
    if seed is not None:
        return seed
    raw_seed = os.getenv("PRODUCTION_CHALLENGE_SEED")
    if not raw_seed:
        raise RuntimeError(
            "PRODUCTION_CHALLENGE_SEED must be set; keep it private"
        )
    try:
        return int(raw_seed)
    except ValueError as error:
        raise RuntimeError("PRODUCTION_CHALLENGE_SEED must be an integer") from error


def _candidate_stream(seed: int, candidate_count_per_family: int = 140) -> list[dict]:
    rng = random.Random(seed)
    candidates: list[dict] = []
    for family in FAMILIES:
        builder = FAMILY_BUILDERS[family]
        for _ in range(candidate_count_per_family):
            expression, domain = builder(rng)
            candidates.append({"family": family, "target_expr": expression, "domain": domain})
    return candidates


def _validated_candidates(seed: int, candidate_count_per_family: int = 140) -> dict[str, list[dict]]:
    accepted: dict[str, list[dict]] = defaultdict(list)
    seen_normalized: set[str] = set()
    seen_numeric: set[tuple[float, ...]] = set()
    for candidate in _candidate_stream(seed, candidate_count_per_family):
        expression = candidate["target_expr"]
        try:
            normalized = normalized_expression(expression)
            numeric = _numeric_fingerprint(expression)
            if normalized in seen_normalized or numeric in seen_numeric:
                continue
            range_min, range_max = validate_candidate(expression, candidate["domain"])
        except (TypeError, ValueError, ZeroDivisionError, OverflowError):
            continue
        seen_normalized.add(normalized)
        seen_numeric.add(numeric)
        candidate = {
            **candidate,
            "range_min": range_min,
            "range_max": range_max,
            "normalized": normalized,
        }
        accepted[candidate["family"]].append(candidate)
    return accepted


def _target_record(candidate: dict, challenge_date: date) -> dict:
    parsed = parse_basic_expression(candidate["target_expr"])
    return {
        "challenge_date": challenge_date.isoformat(),
        "target_expr": candidate["target_expr"],
        "target_latex": latex(parsed),
        "domain_min": candidate["domain"][0],
        "domain_max": candidate["domain"][1],
        "range_min": candidate["range_min"],
        "range_max": candidate["range_max"],
    }


def generate_challenges(
    start_date: date | None = None,
    count: int = CHALLENGE_COUNT,
    candidate_count_per_family: int = 140,
    seed: int | None = None,
) -> list[dict]:
    """Generate a deterministic, family-balanced sequence of challenges."""

    if count < 1:
        raise ValueError("count must be positive")
    if count > len(FAMILIES) * candidate_count_per_family:
        raise ValueError("candidate pool is too small")
    if start_date is None:
        start_date = datetime.now(timezone.utc).date()

    seed = _resolve_seed(seed)
    accepted = _validated_candidates(seed, candidate_count_per_family)
    # Take an equal-ish quota from every family, using a second fixed shuffle so
    # the selection is stable while still avoiding a visually repetitive order.
    base_quota, remainder = divmod(count, len(FAMILIES))
    selector = random.Random(seed + 1)
    selected: list[dict] = []
    for index, family in enumerate(FAMILIES):
        quota = base_quota + (index < remainder)
        family_candidates = list(accepted[family])
        selector.shuffle(family_candidates)
        if len(family_candidates) < quota:
            raise RuntimeError(
                f"only {len(family_candidates)} valid {family} candidates; need {quota}"
            )
        selected.extend(family_candidates[:quota])

    selector.shuffle(selected)
    records = [
        _target_record(candidate, start_date + timedelta(days=index))
        for index, candidate in enumerate(selected)
    ]
    validate_records(records, expected_count=count)
    return records


def validate_records(records: Iterable[dict], expected_count: int = CHALLENGE_COUNT) -> list[dict]:
    """Validate the complete JSON shape and every target in a challenge file."""

    records = list(records)
    if len(records) != expected_count:
        raise ValueError(f"expected exactly {expected_count} entries, got {len(records)}")

    required = {
        "challenge_date",
        "target_expr",
        "target_latex",
        "domain_min",
        "domain_max",
        "range_min",
        "range_max",
    }
    dates: list[date] = []
    normalized_seen: set[str] = set()
    for index, record in enumerate(records):
        if set(record) != required:
            raise ValueError(f"entry {index} has an invalid field set")
        try:
            challenge_date = date.fromisoformat(record["challenge_date"])
            domain = (float(record["domain_min"]), float(record["domain_max"]))
            graph_range = (float(record["range_min"]), float(record["range_max"]))
        except (TypeError, ValueError) as error:
            raise ValueError(f"entry {index} has invalid dates or ranges") from error
        if not all(math.isfinite(value) for value in (*domain, *graph_range)):
            raise ValueError(f"entry {index} contains a non-finite bound")
        if domain[0] >= domain[1] or graph_range[0] >= graph_range[1]:
            raise ValueError(f"entry {index} has an invalid range")

        expression = record["target_expr"]
        if not isinstance(expression, str):
            raise ValueError(f"entry {index} target_expr is not a string")
        if not isinstance(record["target_latex"], str) or not record["target_latex"].strip():
            raise ValueError(f"entry {index} target_latex is not a non-empty string")
        normalized = normalized_expression(expression)
        if normalized in normalized_seen:
            raise ValueError(f"duplicate normalized expression at entry {index}")
        normalized_seen.add(normalized)
        derived_range = validate_candidate(expression, domain)
        if any(
            not math.isclose(
                float(record[field]),
                derived_range[index],
                rel_tol=0,
                abs_tol=0.00011,
            )
            for index, field in enumerate(("range_min", "range_max"))
        ):
            raise ValueError(f"entry {index} does not contain its derived graph range")
        dates.append(challenge_date)

    if len(set(dates)) != expected_count:
        raise ValueError("challenge dates are not unique")
    if dates != list(sorted(dates)):
        raise ValueError("challenge dates must be in chronological order")
    if dates != [dates[0] + timedelta(days=index) for index in range(expected_count)]:
        raise ValueError("challenge dates are not consecutive")
    return records


def load_and_validate(path: str | Path, expected_count: int = CHALLENGE_COUNT) -> list[dict]:
    path = Path(path)
    try:
        with path.open(encoding="utf-8") as handle:
            records = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"could not read challenge file {path}") from error
    if not isinstance(records, list):
        raise ValueError("challenge file must contain a JSON array")
    return validate_records(records, expected_count=expected_count)


def write_challenges(path: str | Path, records: Iterable[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(list(records), handle, indent=2)
        handle.write("\n")


def _cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--validate", type=Path, metavar="PATH")
    return parser


def main() -> None:
    args = _cli().parse_args()
    if args.validate:
        records = load_and_validate(args.validate)
        print(f"Validated {len(records)} production challenges: {args.validate}")
        return
    records = generate_challenges(start_date=args.start_date)
    write_challenges(args.output, records)
    print(f"Generated and validated {len(records)} production challenges: {args.output}")


if __name__ == "__main__":
    main()
