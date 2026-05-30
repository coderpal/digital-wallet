"""
Database Configuration
----------------------
Sets up the SQLAlchemy engine, session factory, and base model class.

Architecture decisions:
- Connection pooling: reuses existing DB connections instead of opening
  a new one per request, which is expensive. Pool size of 10 handles
  moderate traffic; max_overflow adds 20 more under peak load.
- autocommit=False: we manage transactions explicitly. This is critical
  in a fintech app — money transfers must be atomic (all or nothing).
- autoflush=False: prevents SQLAlchemy from issuing unexpected SQL during
  a transaction, giving us full control over when data is written.
- pool_pre_ping=True: tests the connection before using it, preventing
  "connection already closed" errors after the DB restarts or times out.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.logger import setup_logger

logger = setup_logger(__name__)

# The engine manages the connection pool to PostgreSQL.
# It is created once at module load time and shared across all requests.
engine = create_engine(
    settings.DATABASE_URL,

    # Validates connections before use — prevents stale connection errors
    # that occur when PostgreSQL closes idle connections after a timeout.
    pool_pre_ping=True,

    # Number of persistent connections kept open in the pool.
    # Each FastAPI worker thread can hold one connection simultaneously.
    pool_size=10,

    # Additional connections allowed beyond pool_size during traffic spikes.
    # These are closed when the spike subsides, unlike pool connections.
    max_overflow=20,

    # Log all SQL statements in development to help debug query issues.
    # MUST be False in production — SQL logs can expose sensitive financial data.
    echo=settings.DEBUG
)

# Session factory — call SessionLocal() to get a new database session.
# Sessions are not thread-safe and must not be shared between requests.
SessionLocal = sessionmaker(
    # We commit transactions manually after confirming all operations succeed.
    # In a transfer: debit + credit must both succeed before we commit.
    autocommit=False,

    # Prevent automatic SQL emission during a transaction.
    # We want explicit control over when data hits the database.
    autoflush=False,

    bind=engine
)

# Base class for all SQLAlchemy ORM models.
# Every model (User, Wallet, Transaction) inherits from this.
# It provides the metadata registry that Alembic uses for migrations.
Base = declarative_base()


def get_db():
    """
    FastAPI dependency that provides a database session for each request.

    Yields a session, then guarantees cleanup regardless of what happens:
    - On success: the route handler commits, session closes cleanly.
    - On error: rolls back any uncommitted changes, then closes the session.
      This prevents partial writes — critical for financial transactions.

    Usage in route handlers:
        from fastapi import Depends
        from app.database import get_db

        @router.post("/transfer")
        def transfer(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        # Roll back any uncommitted transaction to maintain data integrity.
        # Example: if a transfer debited account A but crashed before
        # crediting account B, this rollback ensures A is not debited.
        logger.error(f"Database session error, rolling back transaction: {e}")
        db.rollback()
        raise
    finally:
        # Always close the session to return the connection to the pool.
        # Without this, the pool would exhaust under moderate traffic.
        db.close()