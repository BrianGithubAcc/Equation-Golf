import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


configured_database_url = os.getenv("DATABASE_URL")
if not configured_database_url and (
    os.getenv("APP_ENV", "development").lower() == "production"
    or os.getenv("VERCEL") == "1"
):
    raise RuntimeError(
        "DATABASE_URL must be set in production deployments"
    )

DATABASE_URL = configured_database_url or (
    "postgresql+psycopg://"
    "equationgolf:equationgolf"
    "@127.0.0.1:5432/equationgolf"
    # Development-only fallback; production requires DATABASE_URL above.
)

# Neon provides postgresql:// URLs. Explicitly use Psycopg 3.
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgresql://",
        "postgresql+psycopg://",
        1,
    )


engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)
