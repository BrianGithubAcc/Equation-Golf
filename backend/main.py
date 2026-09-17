import ast
from collections import deque
import math
import os
import re
import threading
import time
import unicodedata

from datetime import datetime, timedelta, timezone
from typing import Literal

from authlib.integrations.starlette_client import OAuth

from dotenv import load_dotenv

from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    Request,
)

from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel, Field

from sqlalchemy import func, select, text

from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse
from starlette.responses import RedirectResponse

from authlib.integrations.base_client.errors import OAuthError

from sympy import (
    Abs,
    Add,
    E,
    Float,
    Integer,
    Mul,
    Pow,
    Rational,
    Symbol,
    cos,
    exp,
    log,
    pi,
    sin,
    sqrt,
    sympify,
    tan,
)

from sympy.parsing.latex import parse_latex
from sympy import preorder_traversal
from sympy.utilities.lambdify import lambdify

load_dotenv()

from .database import SessionLocal
from .models import ArchivedLeaderboard, Challenge, Submission, User


FRONTEND_URL = os.getenv(
    "FRONTEND_URL",
    "http://localhost:5173",
)

BACKEND_URL = os.getenv(
    "BACKEND_URL",
    "http://localhost:8000",
)

APP_ENV = os.getenv(
    "APP_ENV",
    "production" if os.getenv("VERCEL") == "1" else "development",
).lower()

configured_session_secret = os.getenv("SESSION_SECRET")
if APP_ENV == "production" and (
    not configured_session_secret
    or len(configured_session_secret) < 32
):
    raise RuntimeError(
        "SESSION_SECRET must be set to at least 32 characters in production"
    )

if APP_ENV == "production":
    missing_production_settings = [
        name
        for name in ("DATABASE_URL", "FRONTEND_URL", "BACKEND_URL")
        if not os.getenv(name)
    ]
    if missing_production_settings:
        raise RuntimeError(
            "Missing production settings: "
            + ", ".join(missing_production_settings)
        )

SESSION_SECRET = configured_session_secret or "dev-only-change-me"


app = FastAPI(
    title="Equation Golf API",
    version="0.3.0",
)


app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=APP_ENV == "production",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def validate_api_origin(request: Request, call_next):
    if (
        request.url.path.startswith("/api/")
        and request.method in {"POST", "PATCH", "DELETE"}
    ):
        origin = request.headers.get("origin")
        if origin is not None and origin.rstrip("/") != FRONTEND_URL.rstrip("/"):
            return JSONResponse(
                status_code=403,
                content={"detail": "Request origin is not allowed"},
            )

    return await call_next(request)


oauth = OAuth()


# ---------------------------------------------------------
# Google OAuth
# ---------------------------------------------------------

google_client_id = os.getenv(
    "GOOGLE_CLIENT_ID"
)

google_client_secret = os.getenv(
    "GOOGLE_CLIENT_SECRET"
)

if google_client_id and google_client_secret:
    oauth.register(
        name="google",
        client_id=google_client_id,
        client_secret=google_client_secret,

        server_metadata_url=(
            "https://accounts.google.com/"
            ".well-known/openid-configuration"
        ),

        client_kwargs={
            "scope": "openid profile",
        },
    )


x_symbol = Symbol("x")


SYMPY_NAMES = {
    "x": x_symbol,
    "sin": sin,
    "cos": cos,
    "tan": tan,
    "exp": exp,
    "log": log,
    "sqrt": sqrt,
    "abs": Abs,
    "pi": pi,
    "e": E,
}


class SubmissionRequest(BaseModel):
    equation: str = Field(
        min_length=1,
        max_length=200,
    )

    mode: Literal[
        "basic",
        "latex",
    ]


class DisplayNameRequest(BaseModel):
    display_name: str = Field(
        min_length=1,
        max_length=50,
    )


BLOCKED_DISPLAY_NAME_TERMS = {
    "asshole",
    "bastard",
    "bitch",
    "cunt",
    "dick",
    "faggot",
    "fuck",
    "motherfucker",
    "nigga",
    "nigger",
    "pussy",
    "retard",
    "shit",
    "slut",
    "whore",
}


def clean_display_name(value):
    value = unicodedata.normalize("NFKC", value)
    value = " ".join(value.split())
    if not re.fullmatch(r"[\w][\w .'-]{0,49}", value, re.UNICODE):
        return None

    compact = re.sub(r"[\W_]+", "", value.casefold())
    if any(term in compact for term in BLOCKED_DISPLAY_NAME_TERMS):
        return None

    return value


# ---------------------------------------------------------
# Trusted target expressions
# ---------------------------------------------------------

def compile_target(expression: str):
    symbolic = sympify(
        expression,
        locals=SYMPY_NAMES,
    )

    return lambdify(
        x_symbol,
        symbolic,
        modules=["math"],
    )


# ---------------------------------------------------------
# Safe BASIC parser
#
# Allows things like:
#
# sin(x) + 1
# x^2
# sqrt(x)
# ---------------------------------------------------------

def parse_basic_expression(source: str):
    if len(source) > 200:
        raise ValueError("Expression is too long")

    source = source.replace("^", "**")

    try:
        tree = ast.parse(
            source,
            mode="eval",
        )
    except SyntaxError as error:
        raise ValueError(
            "Invalid basic expression"
        ) from error

    if sum(1 for _ in ast.walk(tree)) > 80:
        raise ValueError("Expression is too complex")

    def numeric_ast_value(node):
        if isinstance(node, ast.Constant) and isinstance(
            node.value,
            (int, float),
        ) and not isinstance(node.value, bool):
            value = float(node.value)
            if math.isfinite(value):
                return value
            return None

        if isinstance(node, ast.UnaryOp) and isinstance(
            node.op,
            (ast.USub, ast.UAdd),
        ):
            value = numeric_ast_value(node.operand)
            if value is None:
                return None
            return -value if isinstance(node.op, ast.USub) else value

        return None

    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(
            node.op,
            ast.Pow,
        ):
            exponent = numeric_ast_value(node.right)
            if exponent is None:
                raise ValueError(
                    "Exponents must be numeric constants"
                )
            if abs(exponent) > 12:
                raise ValueError("Exponent is too large")

    def convert(node):
        if isinstance(node, ast.Expression):
            return convert(node.body)

        if isinstance(node, ast.Constant):
            if isinstance(
                node.value,
                (int, float),
            ) and not isinstance(
                node.value,
                bool,
            ) and math.isfinite(float(node.value)):
                return (
                    Integer(node.value)
                    if isinstance(node.value, int)
                    else Float(node.value)
                )

            raise ValueError(
                "Only numeric constants are allowed"
            )

        if isinstance(node, ast.Name):
            if node.id == "x":
                return x_symbol

            if node.id == "pi":
                return pi

            if node.id == "e":
                return E

            raise ValueError(
                f"Unknown symbol: {node.id}"
            )

        if isinstance(node, ast.UnaryOp):
            value = convert(node.operand)

            if isinstance(node.op, ast.USub):
                return -value

            if isinstance(node.op, ast.UAdd):
                return value

            raise ValueError(
                "Unsupported unary operator"
            )

        if isinstance(node, ast.BinOp):
            left = convert(node.left)
            right = convert(node.right)

            if isinstance(node.op, ast.Add):
                return left + right

            if isinstance(node.op, ast.Sub):
                return left - right

            if isinstance(node.op, ast.Mult):
                return left * right

            if isinstance(node.op, ast.Div):
                return left / right

            if isinstance(node.op, ast.Pow):
                return left ** right

            raise ValueError(
                "Unsupported operator"
            )

        if isinstance(node, ast.Call):
            if not isinstance(
                node.func,
                ast.Name,
            ):
                raise ValueError(
                    "Invalid function"
                )

            functions = {
                "sin": sin,
                "cos": cos,
                "tan": tan,
                "exp": exp,
                "log": log,
                "sqrt": sqrt,
                "abs": Abs,
            }

            function = functions.get(
                node.func.id
            )

            if function is None:
                raise ValueError(
                    f"Unsupported function: "
                    f"{node.func.id}"
                )

            if len(node.args) != 1:
                raise ValueError(
                    "Functions currently take "
                    "one argument"
                )

            return function(
                convert(node.args[0])
            )

        raise ValueError(
            "Unsupported expression"
        )

    return convert(tree)


# ---------------------------------------------------------
# Validate parsed LaTeX
# ---------------------------------------------------------

def validate_expression(expression):
    allowed_functions = {
        Add,
        Mul,
        Pow,
        sin,
        cos,
        tan,
        exp,
        log,
        Abs,
    }

    nodes = list(preorder_traversal(expression))

    if len(nodes) > 80:
        raise ValueError("Expression is too complex")

    for node in nodes:
        if node == x_symbol:
            continue

        if node == pi or node == E:
            continue

        if getattr(node, "is_real", None) is False:
            raise ValueError("Complex values are not allowed")

        if getattr(node, "is_Number", False):
            try:
                numeric_value = float(node)
            except (TypeError, OverflowError):
                raise ValueError(
                    "Numeric constant is too large"
                ) from None
            if not math.isfinite(numeric_value):
                raise ValueError(
                    "NaN and infinity are not allowed"
                )
            continue

        if node.func in allowed_functions:
            if node.func is Pow:
                exponent = node.args[1]
                if not getattr(exponent, "is_number", False):
                    raise ValueError(
                        "Exponents must be numeric constants"
                    )
                try:
                    exponent_value = float(exponent)
                except (TypeError, OverflowError):
                    raise ValueError(
                        "Exponent is invalid"
                    ) from None
                if not math.isfinite(exponent_value) or abs(
                    exponent_value
                ) > 12:
                    raise ValueError("Exponent is too large")
            continue

        raise ValueError(
            f"Unsupported expression: "
            f"{node.func}"
        )


def parse_player_expression(
    source: str,
    mode: str,
):
    if mode == "basic":
        expression = parse_basic_expression(
            source
        )

    elif mode == "latex":
        if len(source) > 200:
            raise ValueError("Expression is too long")
        try:
            expression = parse_latex(
                source
            )
        except Exception as error:
            raise ValueError(
                "Invalid LaTeX"
            ) from error

    else:
        raise ValueError(
            "Unknown input mode"
        )

    validate_expression(expression)

    return expression


def compile_player(
    source: str,
    mode: str,
):
    expression = parse_player_expression(
        source,
        mode,
    )

    function = lambdify(
        x_symbol,
        expression,
        modules=["math"],
    )

    return expression, function


APPROVED_FUNCTIONS = {
    sin,
    cos,
    tan,
    exp,
    log,
    Abs,
}


def expression_cost(expression) -> int:
    if (
        expression == x_symbol
        or expression == pi
        or expression == E
        or getattr(expression, "is_Number", False)
    ):
        return 1

    if expression.func in APPROVED_FUNCTIONS:
        return 1 + sum(
            expression_cost(argument)
            for argument in expression.args
        )

    if (
        expression.func is Pow
        and expression.args[1] == Rational(1, 2)
    ):
        return 1 + expression_cost(expression.args[0])

    if expression.func in {Add, Mul, Pow}:
        return 1 + sum(
            expression_cost(argument)
            for argument in expression.args
        )

    raise ValueError("Unsupported expression")


def dominates(left: Submission, right: Submission) -> bool:
    return (
        left.cost <= right.cost
        and left.error <= right.error
        and (
            left.cost < right.cost
            or left.error < right.error
        )
    )


def pareto_frontier(rows):
    valid_rows = [
        row
        for row in rows
        if math.isfinite(row.error)
    ]

    ordered = sorted(
        valid_rows,
        key=lambda row: (
            row.cost,
            row.error,
            row.submitted_at,
            row.id,
        ),
    )
    frontier = []
    lower_cost_error = math.inf
    index = 0

    while index < len(ordered):
        cost = ordered[index].cost
        same_cost_error = math.inf

        while index < len(ordered) and ordered[index].cost == cost:
            row = ordered[index]
            if (
                lower_cost_error > row.error
                and same_cost_error >= row.error
            ):
                frontier.append(row)
            same_cost_error = min(same_cost_error, row.error)
            index += 1

        lower_cost_error = min(lower_cost_error, same_cost_error)

    return frontier


# ---------------------------------------------------------
# Graph sampling
# ---------------------------------------------------------

def sample_target(
    expression: str,
    minimum_x: float,
    maximum_x: float,
    step: float = 0.05,
):
    function = compile_target(
        expression
    )

    points = []

    count = round(
        (maximum_x - minimum_x)
        / step
    )

    for i in range(count + 1):
        current_x = (
            minimum_x + i * step
        )

        try:
            current_y = float(
                function(current_x)
            )

            if not math.isfinite(
                current_y
            ):
                continue

            points.append({
                "x": round(
                    current_x,
                    8,
                ),

                "y": round(
                    current_y,
                    8,
                ),
            })

        except (
            ValueError,
            ZeroDivisionError,
            OverflowError,
            TypeError,
        ):
            continue

    return points


def calculate_error(
    target_expression: str,
    player_function,
    minimum_x: float,
    maximum_x: float,
    step: float = 0.05,
):
    target_function = compile_target(
        target_expression
    )

    squared_error = 0.0
    count = 0

    sample_count = round(
        (maximum_x - minimum_x)
        / step
    )

    for i in range(
        sample_count + 1
    ):
        current_x = (
            minimum_x + i * step
        )

        try:
            target_value = target_function(
                current_x
            )
            player_value = player_function(
                current_x
            )

            if isinstance(
                target_value,
                complex,
            ) or isinstance(
                player_value,
                complex,
            ):
                return math.inf

            target_y = float(target_value)
            player_y = float(player_value)

        except (
            ValueError,
            ZeroDivisionError,
            OverflowError,
            TypeError,
        ):
            return math.inf

        if (
            not math.isfinite(target_y)
            or
            not math.isfinite(player_y)
        ):
            return math.inf

        difference = (
            target_y - player_y
        )

        squared_error += (
            difference * difference
        )

        count += 1

    if count == 0:
        return math.inf

    return math.sqrt(
        squared_error / count
    )


# ---------------------------------------------------------
# Database helpers
# ---------------------------------------------------------

def get_today_challenge(db):
    today = datetime.now(
        timezone.utc
    ).date()

    challenge = db.scalar(
        select(Challenge).where(
            Challenge.challenge_date
            == today
        )
    )

    if challenge is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No challenge exists "
                f"for {today}"
            ),
        )

    return challenge


def can_reveal_target(challenge, current_date=None):
    if current_date is None:
        current_date = datetime.now(timezone.utc).date()

    return (
        challenge.archived_at is not None
        and challenge.challenge_date < current_date
    )


def public_challenge(challenge, include_target=False):
    payload = {
        "id": challenge.id,
        "date": str(challenge.challenge_date),
        "domain": {
            "min": challenge.domain_min,
            "max": challenge.domain_max,
        },
        "range": {
            "min": challenge.range_min,
            "max": challenge.range_max,
        },
        "archived": challenge.archived_at is not None,
    }

    if include_target and can_reveal_target(challenge):
        payload["target_expr"] = challenge.target_expr
        payload["target_latex"] = challenge.target_latex

    return payload


FRONTIER_CACHE = {}

SUBMISSION_USER_LIMIT = 20
SUBMISSION_IP_LIMIT = 60
SUBMISSION_RATE_WINDOW_SECONDS = 60
SUBMISSION_RATE_LIMITS = {}
SUBMISSION_RATE_LIMIT_LOCK = threading.Lock()


def enforce_submission_rate_limit(request, user_id):
    now = time.monotonic()
    ip_key = ("ip", request.client.host if request.client else "unknown")
    user_key = ("user", str(user_id))
    limits = (
        (ip_key, SUBMISSION_IP_LIMIT),
        (user_key, SUBMISSION_USER_LIMIT),
    )

    with SUBMISSION_RATE_LIMIT_LOCK:
        for key, limit in limits:
            timestamps = SUBMISSION_RATE_LIMITS.setdefault(key, deque())
            while timestamps and now - timestamps[0] >= SUBMISSION_RATE_WINDOW_SECONDS:
                timestamps.popleft()
            if len(timestamps) >= limit:
                raise HTTPException(
                    status_code=429,
                    detail="Submission rate limit exceeded",
                    headers={"Retry-After": "60"},
                )

        for key, _ in limits:
            SUBMISSION_RATE_LIMITS[key].append(now)


def leaderboard_payload(db, challenge, limit, offset):
    include_equations = can_reveal_target(challenge)
    if challenge.archived_at is not None:
        archived_rows = db.scalars(
            select(ArchivedLeaderboard)
            .where(
                ArchivedLeaderboard.challenge_id == challenge.id,
            )
            .order_by(ArchivedLeaderboard.final_position)
        ).all()
        page = archived_rows[offset:offset + limit]
        entries = [
            {
                "rank": row.final_position,
                "username": row.username,
                "avatar_url": row.avatar_url,
                **({"equation": row.equation} if include_equations else {}),
                "cost": row.cost,
                "error": row.error,
                "mode": row.input_mode,
                "submitted_at": row.submitted_at,
            }
            for row in page
        ]
        total = len(archived_rows)
    else:
        signature = db.execute(
            select(
                func.count(Submission.id),
                func.max(Submission.id),
            ).where(
                Submission.challenge_id == challenge.id,
            )
        ).one()
        cached = FRONTIER_CACHE.get(challenge.id)
        if cached is None or cached[0] != signature:
            rows = db.scalars(
                select(Submission).where(
                    Submission.challenge_id == challenge.id,
                )
            ).all()
            frontier = pareto_frontier(rows)
            FRONTIER_CACHE[challenge.id] = (signature, frontier)
        else:
            frontier = cached[1]
        page = frontier[offset:offset + limit]
        entries = [
            {
                "rank": offset + index,
                "username": db.get(User, submission.user_id).username,
                "avatar_url": db.get(User, submission.user_id).avatar_url,
                "cost": submission.cost,
                "error": submission.error,
                "mode": submission.input_mode,
                "submitted_at": submission.submitted_at,
            }
            for index, submission in enumerate(page, start=1)
        ]
        total = len(frontier)

    return {
        "challenge": public_challenge(
            challenge,
            include_target=True,
        ),
        "total": total,
        "limit": limit,
        "offset": offset,
        "entries": entries,
    }


def get_logged_in_user(
    request: Request,
):
    user_id = request.session.get(
        "user_id"
    )

    if user_id is None:
        return None

    with SessionLocal() as db:
        return db.get(
            User,
            user_id,
        )


def upsert_user(
    google_sub: str,
    username: str,
    avatar_url: str | None,
):
    with SessionLocal() as db:
        user = db.scalar(
            select(User).where(
                User.google_sub == google_sub,
            )
        )

        if user is None:
            user = User(
                google_sub=google_sub,
                username=username,
                avatar_url=avatar_url,
            )

            db.add(user)

        else:
            user.avatar_url = (
                avatar_url
            )

        db.commit()
        db.refresh(user)

        return user


# ---------------------------------------------------------
# Basic API
# ---------------------------------------------------------

@app.get("/")
def root():
    return {
        "message":
            "Equation Golf API is running"
    }


@app.get("/api/health")
def health():
    try:
        with SessionLocal() as db:
            db.execute(
                text("SELECT 1")
            )

        return {
            "status": "ok",
            "database": "connected",
        }

    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=(
                "Database unavailable"
            ),
        ) from error


# ---------------------------------------------------------
# Today's challenge
# ---------------------------------------------------------

@app.get(
    "/api/challenge/today"
)
def today_challenge():
    with SessionLocal() as db:
        challenge = (
            get_today_challenge(db)
        )

        points = sample_target(
            challenge.target_expr,
            challenge.domain_min,
            challenge.domain_max,
        )

        return {
            **public_challenge(challenge),
            # Secret expression is deliberately not returned.
            "target_points": points,
        }


@app.get("/api/challenges")
def challenges():
    with SessionLocal() as db:
        today = datetime.now(timezone.utc).date()
        rows = db.scalars(
            select(Challenge)
            .where(Challenge.challenge_date <= today)
            .order_by(Challenge.challenge_date)
        ).all()
        return {
            "challenges": [public_challenge(row) for row in rows]
        }


@app.get("/api/bootstrap")
def bootstrap(request: Request):
    with SessionLocal() as db:
        challenge = get_today_challenge(db)
        rows = db.scalars(
            select(Challenge)
            .where(
                Challenge.challenge_date
                <= datetime.now(timezone.utc).date()
            )
            .order_by(Challenge.challenge_date)
        ).all()
        leaderboard = leaderboard_payload(db, challenge, 100, 0)
        user = db.get(User, request.session.get("user_id"))

        return {
            "challenge": {
                **public_challenge(challenge),
                "target_points": sample_target(
                    challenge.target_expr,
                    challenge.domain_min,
                    challenge.domain_max,
                ),
            },
            "challenges": [public_challenge(row) for row in rows],
            "leaderboard": leaderboard,
            "me": {
                "authenticated": user is not None,
                **(
                    {
                        "user": {
                            "id": user.id,
                            "username": user.username,
                            "avatar_url": user.avatar_url,
                        }
                    }
                    if user is not None
                    else {}
                ),
            },
        }


# ---------------------------------------------------------
# Authentication state
# ---------------------------------------------------------

@app.get("/api/me")
def me(request: Request):
    user = get_logged_in_user(
        request
    )

    if user is None:
        return {
            "authenticated": False
        }

    return {
        "authenticated": True,

        "user": {
            "id": user.id,
            "username":
                user.username,
            "avatar_url":
                user.avatar_url,
        },
    }


@app.patch("/api/me")
def update_me(payload: DisplayNameRequest, request: Request):
    display_name = clean_display_name(payload.display_name)
    if display_name is None:
        raise HTTPException(
            status_code=400,
            detail="Display name contains unsupported or inappropriate text",
        )

    user_id = request.session.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=401,
            detail="Login required",
        )

    with SessionLocal() as db:
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(
                status_code=401,
                detail="Login required",
            )

        user.username = display_name
        db.commit()
        db.refresh(user)

        return {
            "authenticated": True,
            "user": {
                "id": user.id,
                "username": user.username,
                "avatar_url": user.avatar_url,
            },
        }


@app.delete("/api/me")
def delete_me(request: Request):
    user_id = request.session.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=401,
            detail="Login required",
        )

    with SessionLocal() as db:
        user = db.get(User, user_id)
        if user is None:
            request.session.clear()
            return {"ok": True, "authenticated": False}

        archived_rows = db.scalars(
            select(ArchivedLeaderboard).where(
                ArchivedLeaderboard.user_id == user.id,
            )
        ).all()
        for row in archived_rows:
            row.username = "Deleted player"
            row.avatar_url = None
            row.user_id = None

        db.delete(user)
        db.commit()

    request.session.clear()
    return {"ok": True, "authenticated": False}


# ---------------------------------------------------------
# Google login
# ---------------------------------------------------------

@app.get("/api/auth/google")
async def google_login(
    request: Request,
):
    client = oauth.create_client(
        "google"
    )

    if client is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Google OAuth "
                "is not configured"
            ),
        )

    callback = (
        f"{BACKEND_URL}"
        "/api/auth/google/callback"
    )

    return await client.authorize_redirect(
        request,
        callback,
    )


@app.get(
    "/api/auth/google/callback"
)
async def google_callback(
    request: Request,
):
    client = oauth.create_client(
        "google"
    )

    if client is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Google OAuth "
                "is not configured"
            ),
        )

    try:
        token = (
            await client
            .authorize_access_token(
                request
            )
        )
    except OAuthError as error:
        raise HTTPException(
            status_code=400,
            detail="Google sign-in could not be completed",
        ) from error

    profile = token.get(
        "userinfo"
    )

    if not profile:
        profile = (
            await client.userinfo(
                token=token
            )
        )

    if not isinstance(profile, dict) or not profile.get("sub"):
        raise HTTPException(
            status_code=400,
            detail="Google did not return a valid user profile",
        )

    google_name = clean_display_name(str(profile.get("name") or ""))
    user = upsert_user(
        google_sub=str(
            profile["sub"]
        ),

        username=google_name or "Google user",

        avatar_url=profile.get(
            "picture"
        ),
    )

    request.session[
        "user_id"
    ] = user.id

    return RedirectResponse(
        FRONTEND_URL
    )


@app.post("/api/logout")
def logout(request: Request):
    request.session.clear()

    return {
        "ok": True
    }


# ---------------------------------------------------------
# Submit score
# ---------------------------------------------------------

@app.post(
    "/api/challenge/today/submit"
)
def submit_today(
    submission:
        SubmissionRequest,

    request: Request,
):
    with SessionLocal() as db:
        user_id = request.session.get(
            "user_id"
        )
        user = (
            db.get(User, user_id)
            if user_id is not None
            else None
        )

        if user is None:
            raise HTTPException(
                status_code=401,
                detail="Login required",
            )

        enforce_submission_rate_limit(request, user.id)

        try:
            expression, player_function = (
                compile_player(
                    submission.equation,
                    submission.mode,
                )
            )
            cost = expression_cost(expression)
        except (
            TypeError,
            ValueError,
            OverflowError,
            ZeroDivisionError,
        ) as error:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            ) from error

        challenge = (
            get_today_challenge(db)
        )

        error = calculate_error(
            challenge.target_expr,
            player_function,
            challenge.domain_min,
            challenge.domain_max,
        )

        if not math.isfinite(error):
            raise HTTPException(
                status_code=400,
                detail="Expression produces non-finite values",
            )

        existing = db.scalars(
            select(Submission).where(
                Submission.user_id
                == user_id,

                Submission.challenge_id
                == challenge.id,

                Submission.equation
                == submission.equation,

                Submission.input_mode
                == submission.mode,
            )
        ).first()

        if existing is None:
            saved_submission = Submission(
                user_id=user_id,
                challenge_id=challenge.id,
                equation=submission.equation,
                input_mode=submission.mode,
                error=error,
                cost=cost,
            )

            db.add(saved_submission)
        else:
            saved_submission = existing

        db.commit()
        FRONTIER_CACHE.pop(challenge.id, None)

        all_rows = db.scalars(
            select(Submission)
            .where(
                Submission.challenge_id
                == challenge.id,
            )
        ).all()

        frontier = pareto_frontier(all_rows)
        display_position = next(
            (
                index
                for index, row in enumerate(
                    frontier,
                    start=1,
                )
                if row.id == saved_submission.id
            ),
            None,
        )

        return {
            "error": error,

            "cost": cost,

            "on_pareto_frontier":
                display_position is not None,

            "display_position":
                display_position,
        }


# ---------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------

@app.get(
    "/api/challenge/today/leaderboard"
)
def leaderboard(
    limit: int = Query(100, ge=1, le=5000),
    offset: int = Query(0, ge=0),
):
    with SessionLocal() as db:
        challenge = (
            get_today_challenge(db)
        )
        return leaderboard_payload(db, challenge, limit, offset)


@app.get("/api/challenge/{challenge_date}/leaderboard")
def dated_leaderboard(
    challenge_date: str,
    limit: int = Query(100, ge=1, le=5000),
    offset: int = Query(0, ge=0),
):
    try:
        requested_date = datetime.strptime(
            challenge_date,
            "%Y-%m-%d",
        ).date()
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail="Date must be YYYY-MM-DD",
        ) from error

    with SessionLocal() as db:
        if requested_date > datetime.now(timezone.utc).date():
            raise HTTPException(
                status_code=404,
                detail="Future challenges are not available",
            )

        challenge = db.scalar(
            select(Challenge).where(
                Challenge.challenge_date == requested_date,
            )
        )
        if challenge is None:
            raise HTTPException(
                status_code=404,
                detail="No challenge for requested date",
            )
        return leaderboard_payload(db, challenge, limit, offset)


@app.get("/api/challenge/yesterday")
def yesterday_challenge():
    yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)

    with SessionLocal() as db:
        challenge = db.scalar(
            select(Challenge).where(
                Challenge.challenge_date == yesterday,
                Challenge.archived_at.is_not(None),
            )
        )

        if challenge is None:
            raise HTTPException(
                status_code=404,
                detail="Yesterday's challenge is not archived",
            )

        entries = db.scalars(
            select(ArchivedLeaderboard)
            .where(ArchivedLeaderboard.challenge_id == challenge.id)
            .order_by(ArchivedLeaderboard.final_position)
            .limit(100)
        ).all()

        return {
            **public_challenge(challenge, include_target=True),
            "leaderboard": [
                {
                    "rank": entry.final_position,
                    "username": entry.username,
                    "avatar_url": entry.avatar_url,
                    "equation": entry.equation,
                    "mode": entry.input_mode,
                    "cost": entry.cost,
                    "error": entry.error,
                    "submitted_at": entry.submitted_at,
                }
                for entry in entries
            ],
        }
