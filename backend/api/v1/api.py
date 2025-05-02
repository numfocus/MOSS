"""
backend.api.v1.api
------------------
This module defines the main API router for version 1 of the MOSS backend API.

It aggregates various endpoint routers responsible for specific functionalities
like ingestion, retrieval, surfacing, search, etc., making them accessible
under the `/api/v1` prefix (as configured in the main application setup).
"""

from fastapi import APIRouter

# --- Import specific endpoint routers ---
# These modules contain the specific API routes for different application features.
from .endpoints import ingestion
from .endpoints import retrieval
from .endpoints import surfacing
from .endpoints import search
from .endpoints import shared_recipes
from .endpoints import affiliation_algorithms
from .endpoints import history
from .endpoints import discovery_algorithms # Handles discovery algorithm related operations


# Main router instance for API version 1.
# All routes defined in the included routers will be prefixed accordingly.
api_router = APIRouter()

# --- Include specific endpoint routers here ---
# Each `include_router` call mounts the routes from the specified module
# under the main `api_router` with a defined prefix and tags for documentation.

# Routes for data ingestion processes
api_router.include_router(ingestion.router, prefix="/ingest", tags=["Ingestion"])
# Routes for retrieving processed data or artifacts
api_router.include_router(retrieval.router, prefix="/retrieve", tags=["Retrieval"])
# Routes related to surfacing insights or results
api_router.include_router(surfacing.router, prefix="/surface", tags=["Surfacing"])
# Routes for search functionalities across the application data
api_router.include_router(search.router, prefix="/search", tags=["Search"])
# Routes for managing shared analysis recipes or configurations
api_router.include_router(shared_recipes.router, prefix="/shared-recipes", tags=["Shared Analysis Recipes"])
# Routes for managing and executing repository-institution affiliation algorithms
api_router.include_router(affiliation_algorithms.router, prefix="/affiliation-algorithms", tags=["Affiliation Algorithms"])
# Routes for accessing history of ingestion tasks
api_router.include_router(history.router, prefix="/ingestion-history", tags=["Ingestion History"])
# Routes for managing and executing discovery algorithms
api_router.include_router(discovery_algorithms.router, prefix="/discovery-algorithms", tags=["Discovery Algorithms"])