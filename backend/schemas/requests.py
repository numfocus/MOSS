"""
backend.schemas.requests
------------------------

Pydantic models defining the structure of expected data in API request bodies.

These models are used by FastAPI endpoints to validate incoming data, ensuring
that required fields are present and conform to the expected types and formats
before processing begins.
"""
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, HttpUrl, Field

# --- Ingestion ---
class IngestionRequest(BaseModel):
    """
    Specifies the data required to initiate ingestion from a direct URL.
    Typically used for adding a specific repository or resource.
    """
    url: HttpUrl = Field(..., description="The URL of the resource to ingest (e.g., a GitHub repository URL). Must be a valid HTTP/HTTPS URL.")

class KeywordIngestionRequest(BaseModel):
    """
    Specifies the data required to initiate ingestion based on keywords.
    Used for discovering resources via external search APIs (e.g., GitHub search).
    """
    keywords: str = Field(..., description="A string of keywords to use for searching and subsequent ingestion.")

# --- Shared Recipes / Algorithms ---
class RecipeExecutionRequest(BaseModel):
    """
    Defines the structure for requesting the execution of a generic recipe or algorithm.
    Requires specifying the parameters needed by the target script.
    """
    parameters: Dict[str, Any] = Field(..., description="A dictionary of parameters required by the specific recipe script being executed. Keys are parameter names, values are the corresponding parameter values.")

# --- Affiliation Algorithms ---
class AffiliationExecutionRequest(BaseModel):
    """
    Specifies the data required to execute a repository-institution affiliation algorithm.
    Targets a specific institution and allows for algorithm-specific parameters.
    """
    institution_id: int = Field(..., description="The internal database ID of the institution for which to run the affiliation algorithm.")
    parameters: Dict[str, Any] = Field({}, description="Optional dictionary of additional parameters required by the specific affiliation algorithm being executed. Structure depends on the algorithm.")