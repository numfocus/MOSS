"""
backend.api.v1.endpoints.history
--------------------------------
Defines API endpoints for retrieving historical context about ingestion events.
Allows querying the last time data relevant to a specific keyword or URL pattern
was ingested.
"""

import logging
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
# Import necessary SQLAlchemy functions for querying
from sqlalchemy import desc, or_, func # Import desc (ordering), or_ (conditional logic), func (database functions)

# Internal dependencies for database access and data models/schemas
from backend.api.deps import get_db_session
from backend.data.models import DiscoveryChain, KeywordSearchSession
from backend.schemas.responses import IngestionHistoryContextResponse

# Logger setup for this module
logger = logging.getLogger(__name__)

# API Router instance for history endpoints
router = APIRouter()

@router.get(
    "/context",
    response_model=IngestionHistoryContextResponse,
    summary="Get Context on Last Relevant Ingestion"
)
def get_ingestion_history_context(
    param_type: str = Query(..., description="Type of parameter to match (e.g., 'keyword', 'url_pattern'). Indicates which table and field to search."),
    param_value: str = Query(..., description="Value of the parameter to match (e.g., a specific keyword or a URL pattern)."),
    db: Session = Depends(get_db_session) # Database session dependency
):
    """
    Finds the timestamp and type of the most recently *completed* ingestion event
    that is relevant to the provided parameter type and value. It serves as a way
    to understand when data related to a specific search term or URL might have
    last been successfully processed.

    Logic based on `param_type`:
    - **'keyword'**: Searches the `KeywordSearchSession` table for completed sessions
      where `keywords_raw` contains the `param_value` (case-insensitive). It prioritizes
      the `completed_at` timestamp of the most recent match. If no completed match
      is found, it falls back to the `created_at` timestamp of the most recent session
      (regardless of status) matching the keyword, indicating when it was last initiated.
    - **'url_pattern'**: Searches the `DiscoveryChain` table for *root* chains
      (no parent) of type `DIRECT_URL` where the `parameters` JSONB field contains a 'url' key
      whose value contains the `param_value` (case-insensitive). It prioritizes the
      `completed_at` timestamp. If no completed match exists, it falls back to the
      `created_at` timestamp of the most recent root `DIRECT_URL` chain matching the pattern.

    Args:
        param_type (str): The type of parameter ('keyword' or 'url_pattern').
        param_value (str): The value to search for within the relevant field.
        db (Session): The SQLAlchemy database session.

    Returns:
        IngestionHistoryContextResponse: An object containing the input parameters,
                                         the timestamp of the last relevant ingestion
                                         (`last_ingested_at`), and the type of that
                                         ingestion event (`ingestion_type`). Timestamps
                                         and type may be None if no relevant event is found.

    Raises:
        HTTPException:
            - 400 Bad Request: If an unsupported `param_type` is provided.
            - 500 Internal Server Error: If a database query or other processing fails.
    """
    logger.info(f"Fetching ingestion history context for type '{param_type}' value '{param_value}'")

    # Initialize variables to store the result
    last_ingested_at: Optional[datetime] = None
    ingestion_type: Optional[str] = None # Describes the source of the timestamp (e.g., KEYWORD_SEARCH, DIRECT_URL)

    try:
        # --- Keyword Search History ---
        if param_type == 'keyword':
            # Primary Query: Find the most recent *completed* keyword search session matching the value.
            # Uses case-insensitive matching (`ilike`) on the raw keywords string.
            primary_keyword_query = (
                db.query(KeywordSearchSession.completed_at) # Select only the completion timestamp
                .filter(KeywordSearchSession.keywords_raw.ilike(f"%{param_value}%")) # Case-insensitive substring match
                .filter(KeywordSearchSession.status == 'COMPLETED') # Must be completed
                .order_by(desc(KeywordSearchSession.completed_at)) # Get the most recent first
            )
            completed_result = primary_keyword_query.first() # Fetch the first result (most recent)

            if completed_result and completed_result.completed_at:
                last_ingested_at = completed_result.completed_at
                ingestion_type = 'KEYWORD_SEARCH' # Indicates a completed keyword search session
            else:
                 # Fallback Query: If no completed session found, find the most recent session
                 # matching the keyword, regardless of status, and use its creation time.
                 # This indicates when such a search was last *initiated*.
                 fallback_keyword_query = (
                     db.query(KeywordSearchSession.created_at) # Select creation timestamp
                     .filter(KeywordSearchSession.keywords_raw.ilike(f"%{param_value}%")) # Match keyword
                     .order_by(desc(KeywordSearchSession.created_at)) # Most recent created first
                 )
                 fallback_result = fallback_keyword_query.first()
                 if fallback_result and fallback_result.created_at:
                      last_ingested_at = fallback_result.created_at
                      # Use a distinct type to indicate it wasn't necessarily completed
                      ingestion_type = 'KEYWORD_SEARCH_INITIATED'

        # --- URL Pattern Search History ---
        elif param_type == 'url_pattern':
            # Primary Query: Find the most recent *completed* root DiscoveryChain
            # of type DIRECT_URL where the 'url' parameter matches the pattern.
            # Uses JSONB operators (`->>`) for text extraction and `ilike`.
            primary_url_query = (
                db.query(DiscoveryChain.completed_at) # Select completion timestamp
                .filter(DiscoveryChain.parent_chain_id.is_(None)) # Must be a root chain (no parent)
                .filter(DiscoveryChain.discovery_type == 'DIRECT_URL') # Must be a direct URL ingestion
                # Access the 'url' key within the JSONB 'parameters' field, cast to text, and perform case-insensitive match
                .filter(DiscoveryChain.parameters['url'].astext.ilike(f"%{param_value}%"))
                .filter(DiscoveryChain.status == 'COMPLETED') # Must be completed
                .order_by(desc(DiscoveryChain.completed_at)) # Most recent completed first
            )
            completed_result = primary_url_query.first()

            if completed_result and completed_result.completed_at:
                last_ingested_at = completed_result.completed_at
                ingestion_type = 'DIRECT_URL' # Indicates a completed direct URL ingestion
            else:
                # Fallback Query: If no completed chain found, find the most recent root DIRECT_URL chain
                # matching the pattern, regardless of status, and use its creation time.
                fallback_url_query = (
                     db.query(DiscoveryChain.created_at) # Select creation timestamp
                     .filter(DiscoveryChain.parent_chain_id.is_(None)) # Root chain
                     .filter(DiscoveryChain.discovery_type == 'DIRECT_URL') # Direct URL type
                     .filter(DiscoveryChain.parameters['url'].astext.ilike(f"%{param_value}%")) # Match pattern
                     .order_by(desc(DiscoveryChain.created_at)) # Most recent created first
                 )
                fallback_result = fallback_url_query.first()
                if fallback_result and fallback_result.created_at:
                     last_ingested_at = fallback_result.created_at
                     # Use distinct type for initiated but not necessarily completed
                     ingestion_type = 'DIRECT_URL_INITIATED'

        # --- Unsupported Parameter Type ---
        else:
            # Raise an error if the provided param_type is not recognized
            logger.warning(f"Unsupported param_type requested: '{param_type}'")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported param_type: '{param_type}'. Valid types are 'keyword' or 'url_pattern'."
            )

        # Construct and return the response object
        return IngestionHistoryContextResponse(
            param_type=param_type,
            param_value=param_value,
            last_ingested_at=last_ingested_at, # Will be None if no match found
            ingestion_type=ingestion_type     # Will be None if no match found
        )

    except Exception as e:
        # Catch any unexpected database or processing errors
        logger.exception(f"Error fetching ingestion history context for type '{param_type}' value '{param_value}'")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving ingestion history context."
        )