"""
backend.api.v1.endpoints.search
-------------------------------
Defines API endpoints for performing searches across various data entities
(Repositories, Works, People, Institutions) based on a query string.
Provides basic text search capabilities with pagination.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
# Import necessary SQLAlchemy functions for searching and ordering
from sqlalchemy import or_, func

# Internal dependencies for database access, models, and response schemas
from backend.api.deps import get_db_session
from backend.data.models import Repository, Work, Person, Institution
from backend.schemas.responses import (
    RepositorySummary, WorkSummary, PersonSummary, InstitutionSummary # Use summary schemas for search results
)

# Logger setup for this module
logger = logging.getLogger(__name__)

# API Router instance for search endpoints
router = APIRouter()

# Default pagination parameters for search results
DEFAULT_SEARCH_SKIP = 0
DEFAULT_SEARCH_LIMIT = 100
MAX_SEARCH_LIMIT = 200 # Define a maximum limit for safety/performance


@router.get(
    "/repositories",
    response_model=List[RepositorySummary], # Return a list of summaries
    summary="Search Repositories"
)
def search_repositories(
    q: str = Query(..., min_length=1, description="Search query string used to match repository name or description."),
    skip: int = Query(DEFAULT_SEARCH_SKIP, ge=0, description="Number of results to skip (for pagination)."),
    limit: int = Query(DEFAULT_SEARCH_LIMIT, ge=1, le=MAX_SEARCH_LIMIT, description="Maximum number of results to return."),
    db: Session = Depends(get_db_session) # Database session dependency
):
    """
    Searches for repositories where the query string `q` appears in the
    repository's full name or description (case-insensitive).

    Results are ordered by stargazer count (descending) and paginated.

    Args:
        q (str): The search term.
        skip (int): Offset for pagination.
        limit (int): Maximum number of results.
        db (Session): The SQLAlchemy database session.

    Returns:
        List[RepositorySummary]: A list of repositories matching the query.

    Raises:
        HTTPException: 500 Internal Server Error if the search query fails.
    """
    logger.info(f"Searching repositories with query: '{q}', skip: {skip}, limit: {limit}")
    # Prepare the search term for use with ILIKE (case-insensitive LIKE)
    search_term = f"%{q}%"

    try:
        # Construct the SQLAlchemy query
        query = (
            db.query(Repository)
            .filter(
                # Use 'or_' to match the search term in either field
                or_(
                    Repository.full_name.ilike(search_term), # Case-insensitive match on full name
                    Repository.description.ilike(search_term) # Case-insensitive match on description
                )
            )
            # Order results: repositories with more stars appear first.
            # `nullslast()` ensures repositories without star counts appear at the end.
            .order_by(Repository.stargazers_count.desc().nullslast())
            .offset(skip) # Apply pagination offset
            .limit(limit) # Apply pagination limit
        )
        # Execute the query and get results
        results = query.all()
        # FastAPI handles mapping the results to the response model (List[RepositorySummary])
        return results
    except Exception as e:
        # Log unexpected errors during the search
        logger.exception(f"Error during repository search for query '{q}'")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while searching for repositories."
        )


@router.get(
    "/works",
    response_model=List[WorkSummary], # Return a list of summaries
    summary="Search Works"
)
def search_works(
    q: str = Query(..., min_length=1, description="Search query string used to match work title or DOI."),
    skip: int = Query(DEFAULT_SEARCH_SKIP, ge=0, description="Number of results to skip."),
    limit: int = Query(DEFAULT_SEARCH_LIMIT, ge=1, le=MAX_SEARCH_LIMIT, description="Maximum number of results to return."),
    db: Session = Depends(get_db_session) # Database session dependency
):
    """
    Searches for scholarly works where the query string `q` appears in the
    work's title or DOI (case-insensitive).

    Results are ordered by citation count (descending) and paginated.

    Args:
        q (str): The search term.
        skip (int): Offset for pagination.
        limit (int): Maximum number of results.
        db (Session): The SQLAlchemy database session.

    Returns:
        List[WorkSummary]: A list of works matching the query.

    Raises:
        HTTPException: 500 Internal Server Error if the search query fails.
    """
    logger.info(f"Searching works with query: '{q}', skip: {skip}, limit: {limit}")
    search_term = f"%{q}%" # Prepare term for ILIKE

    try:
        query = (
            db.query(Work)
            .filter(
                # Match the search term in either title or DOI
                or_(
                    Work.title.ilike(search_term), # Case-insensitive match on title
                    Work.doi.ilike(search_term)    # Case-insensitive match on DOI
                )
            )
            # Order results: more cited works appear first.
            .order_by(Work.cited_by_count.desc().nullslast())
            .offset(skip)
            .limit(limit)
        )
        results = query.all()
        return results
    except Exception as e:
        logger.exception(f"Error during work search for query '{q}'")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while searching for works."
        )


@router.get(
    "/people",
    response_model=List[PersonSummary], # Return a list of summaries
    summary="Search People"
)
def search_people(
    q: str = Query(..., min_length=1, description="Search query string used to match person display name or ORCID."),
    skip: int = Query(DEFAULT_SEARCH_SKIP, ge=0, description="Number of results to skip."),
    limit: int = Query(DEFAULT_SEARCH_LIMIT, ge=1, le=MAX_SEARCH_LIMIT, description="Maximum number of results to return."),
    db: Session = Depends(get_db_session) # Database session dependency
):
    """
    Searches for people (authors/researchers) where the query string `q`
    appears in the person's display name or ORCID (case-insensitive).

    Note: Currently does not search within alternative names stored in JSON.
    Results are ordered alphabetically by display name and paginated.

    Args:
        q (str): The search term.
        skip (int): Offset for pagination.
        limit (int): Maximum number of results.
        db (Session): The SQLAlchemy database session.

    Returns:
        List[PersonSummary]: A list of people matching the query.

    Raises:
        HTTPException: 500 Internal Server Error if the search query fails.
    """
    logger.info(f"Searching people with query: '{q}', skip: {skip}, limit: {limit}")
    search_term = f"%{q}%" # Prepare term for ILIKE

    try:
        query = (
            db.query(Person)
            .filter(
                # Match the search term in either display name or ORCID
                or_(
                    Person.display_name.ilike(search_term), # Case-insensitive match on display name
                    Person.orcid.ilike(search_term)         # Case-insensitive match on ORCID
                    # Future enhancement: Add search on Person.display_name_alternatives (JSONB array)
                    # This would require database-specific JSON functions, e.g., for PostgreSQL:
                    # func.lower(Person.display_name_alternatives::text).contains(q.lower())
                )
            )
            # Order results alphabetically by name
            .order_by(Person.display_name)
            .offset(skip)
            .limit(limit)
        )
        results = query.all()
        return results
    except Exception as e:
        logger.exception(f"Error during people search for query '{q}'")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while searching for people."
        )

@router.get(
    "/institutions",
    response_model=List[InstitutionSummary], # Return a list of summaries
    summary="Search Institutions"
)
def search_institutions(
    q: str = Query(..., min_length=1, description="Search query string used to match institution display name or ROR ID."),
    # Corrected default skip value for consistency
    skip: int = Query(DEFAULT_SEARCH_SKIP, ge=0, description="Number of results to skip."),
    limit: int = Query(DEFAULT_SEARCH_LIMIT, ge=1, le=MAX_SEARCH_LIMIT, description="Maximum number of results to return."),
    db: Session = Depends(get_db_session) # Database session dependency
):
    """
    Searches for institutions where the query string `q` appears in the
    institution's display name or ROR identifier (case-insensitive).

    Results are ordered alphabetically by display name and paginated.

    Args:
        q (str): The search term.
        skip (int): Offset for pagination.
        limit (int): Maximum number of results.
        db (Session): The SQLAlchemy database session.

    Returns:
        List[InstitutionSummary]: A list of institutions matching the query.

    Raises:
        HTTPException: 500 Internal Server Error if the search query fails.
    """
    logger.info(f"Searching institutions with query: '{q}', skip: {skip}, limit: {limit}")
    search_term = f"%{q}%" # Prepare term for ILIKE

    try:
        query = (
            db.query(Institution)
            .filter(
                # Match the search term in either display name or ROR ID
                or_(
                    Institution.display_name.ilike(search_term), # Case-insensitive match on display name
                    Institution.ror.ilike(search_term)          # Case-insensitive match on ROR ID
                )
            )
            # Order results alphabetically by name
            .order_by(Institution.display_name)
            .offset(skip)
            .limit(limit)
        )
        results = query.all()
        return results
    except Exception as e:
        logger.exception(f"Error during institution search for query '{q}'")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while searching for institutions."
        )