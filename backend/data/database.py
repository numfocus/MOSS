"""
backend.data.database
---------------------
This module configures and provides access to the application's database
using SQLAlchemy. It sets up the database engine, session management,
and the declarative base class for ORM models. It also includes a
dependency function (`get_db`) for use with web frameworks like FastAPI.
"""

import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
# Use declarative_base from sqlalchemy.orm as recommended in modern SQLAlchemy
from sqlalchemy.orm import declarative_base
from sqlalchemy.exc import SQLAlchemyError # Specific exception for database errors

# Import application settings, expected to contain the DATABASE_URL
from backend.config.settings import settings

logger = logging.getLogger(__name__)

# Retrieve the database connection string from application settings.
# This centralizes configuration management.
SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

# --- Database Engine Setup ---
# The engine is the starting point for any SQLAlchemy application.
# It manages database connections and dialects.
try:
    # Create the core SQLAlchemy engine instance.
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        # pool_pre_ping=True: Checks connection validity before use, helps handle stale connections.
        pool_pre_ping=True,
        # echo=False: Set to True to log all generated SQL statements (useful for debugging, noisy in production).
        echo=False,
        # --- Connection Pool Configuration ---
        # These parameters tune the connection pool behavior for performance and reliability.
        # pool_size: The target number of connections to keep readily available in the pool.
        pool_size=20,      # Increased from default (often 5) to handle more concurrent requests.
        # max_overflow: The maximum number of additional connections allowed beyond 'pool_size'
        # during peak load before requests start waiting.
        max_overflow=30,   # Allows for bursts of activity. (default often 10)
        # pool_timeout: The number of seconds to wait when trying to get a connection from the
        # pool before raising a TimeoutError.
        pool_timeout=30    # Standard timeout duration.
    )

    # --- Optional: Connection Event Logging ---
    # Uncomment these listeners to log database connection events, which can be
    # helpful for diagnosing connection pool issues or monitoring activity.
    # from sqlalchemy import event
    # @event.listens_for(engine, "connect")
    # def connect(dbapi_connection, connection_record):
    #     logger.debug("DB connection established.")
    # @event.listens_for(engine, "close")
    # def close(dbapi_connection, connection_record):
    #     logger.debug("DB connection closed.")

    # Log essential information about the engine setup for monitoring.
    # Avoid logging the full DATABASE_URL for security, show only the end part.
    log_url_display = f"{'*' * 5}{SQLALCHEMY_DATABASE_URL[-5:]}" if SQLALCHEMY_DATABASE_URL else "Not Set"
    logger.info(f"SQLAlchemy engine created for URL ending in: {log_url_display}")
    logger.info(f"SQLAlchemy pool settings: size={engine.pool.size()}, overflow={engine.pool.overflow()}, timeout={engine.pool.timeout()}")

# --- Robust Error Handling ---
# Catch specific errors during engine creation to provide informative logs and fail gracefully.
except SQLAlchemyError as e:
    # Errors related to database connection or configuration.
    logger.error(f"Error creating SQLAlchemy engine: {e}", exc_info=True)
    # Re-raise as a runtime error to prevent the application from starting
    # with a non-functional database connection.
    raise RuntimeError(f"Failed to create database engine: {e}") from e
except ImportError as e:
    # Error typically occurs if the database driver (e.g., psycopg2 for PostgreSQL) isn't installed.
    logger.error(f"Error importing database driver (psycopg2?): {e}", exc_info=True)
    raise RuntimeError(f"Database driver not found: {e}") from e


# --- Session Management ---
# Create a configured "Session" class factory. Instances of this class will
# represent individual database sessions (transactions).
SessionLocal = sessionmaker(
    # autocommit=False: Ensures operations are part of a transaction that needs explicit commit. Standard practice.
    autocommit=False,
    # autoflush=False: Prevents automatic flushing of changes before queries, giving more control.
    autoflush=False,
    # bind=engine: Associates this session factory with our configured database engine.
    bind=engine
)

# --- Declarative Base ---
# Create a base class for our ORM (Object-Relational Mapper) models.
# All application data models should inherit from this 'Base'.
Base = declarative_base()

# --- Dependency for Web Frameworks (e.g., FastAPI) ---
def get_db():
    """
    Provides a database session for dependency injection in web request handlers.

    This generator function creates a new database session for each request,
    yields it for use within the request's scope, and ensures the session
    is always closed afterwards, even if errors occur during the request handling.
    This pattern manages session lifecycles correctly and releases connections
    back to the pool.

    Yields:
        sqlalchemy.orm.Session: A database session instance.
    """
    db = SessionLocal() # Create a new session instance from the factory.
    try:
        # Yield the session to the part of the code that depends on it (e.g., a request handler).
        yield db
    finally:
        # This block executes regardless of whether an exception occurred in the 'try' block.
        # It's crucial to close the session to release the database connection back to the pool.
        db.close()

# --- Example Standalone Usage (Commented Out) ---
# This section demonstrates how to use the SessionLocal directly,
# typically needed in scripts, background tasks, or tests outside the
# request-response cycle managed by `get_db`. Remember to handle
# commits, rollbacks, and closing the session manually in such cases.
#
# from .database import SessionLocal, engine, Base
#
# # If needed outside the get_db context (e.g., for alembic migrations):
# # target_metadata = Base.metadata
#
# def some_database_operation():
#     db = SessionLocal() # Create a session manually
#     try:
#         # Perform database operations using the 'db' session object
#         # result = db.query(...)
#         # new_record = MyModel(...)
#         # db.add(new_record)
#         # If changes were made that need to be persisted:
#         # db.commit()
#         print("Simulating DB operation")
#     except Exception as e:
#         # If any error occurs, rollback the transaction to maintain data integrity.
#         db.rollback()
#         print(f"Error during DB operation: {e}")
#         raise # Re-raise the exception after rollback if necessary
#     finally:
#         # Always ensure the session is closed to free up resources.
#         db.close()