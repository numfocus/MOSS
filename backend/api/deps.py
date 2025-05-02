"""
backend.api.v1.deps
-------------------
Defines common dependencies for FastAPI endpoints in API version 1.

This module centralizes the creation of dependencies used across multiple
API routes, primarily focusing on providing database sessions managed within
the request lifecycle.
"""

import logging
from typing import Generator
from sqlalchemy.orm import Session

# Import the actual database session generator and SessionLocal factory
# from the data layer.
from backend.data.database import SessionLocal, get_db

# Logger for this module
logger = logging.getLogger(__name__)

# --- Database Session Dependency ---
def get_db_session() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a SQLAlchemy database session.

    This function acts as a dependency provider for FastAPI routes. It utilizes
    the `get_db` generator from `backend.data.database`, which handles the
    creation of a new session for each request, manages the transaction
    (commit or rollback), and ensures the session is closed properly, even
    if errors occur during the request handling.

    Yields:
        Generator[Session, None, None]: A generator yielding a SQLAlchemy Session.
                                        FastAPI uses this to inject the session
                                        into path operation functions.
    """
    # logger.debug("Dependency get_db_session invoked, yielding from database.get_db")
    # Delegate the actual session lifecycle management (try/finally/close)
    # to the imported `get_db` generator function.
    yield from get_db()

# --- Example Usage in an Endpoint ---
#
# from fastapi import Depends, APIRouter
# from sqlalchemy.orm import Session
# from .deps import get_db_session # Assuming relative import works
# # Or: from backend.api.v1.deps import get_db_session
#
# router = APIRouter()
#
# @router.get("/items/")
# async def read_items(db: Session = Depends(get_db_session)):
#     """
#     Example endpoint demonstrating the use of the get_db_session dependency.
#     FastAPI will inject the database session into the 'db' parameter.
#     """
#     # The 'db' session can be used here to interact with the database.
#     # For example:
#     # items = db.query(YourModel).filter(...).all()
#     # The session's lifecycle (commit, rollback, close) is automatically
#     # handled by the dependency mechanism thanks to the context manager
#     # or generator structure in `database.get_db`.
#     logger.info(f"Received database session: {db}")
#     return {"message": "Items would be read here using the db session"}