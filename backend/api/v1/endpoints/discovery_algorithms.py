"""
backend.api.v1.endpoints.discovery_algorithms
---------------------------------------------
Defines API endpoints for discovering and executing repository discovery algorithms.
These algorithms are contributed scripts designed to find candidate software
repository URLs based on various inputs (e.g., keywords, topics).
"""

import logging
from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException, status, Depends, Body, Path as FastApiPath
from sqlalchemy.orm import Session

# Internal dependencies for utilities, configuration, schemas, and database access
from backend.utils.recipe_utils import (
    discover_recipes, RecipeMetadata # Import RecipeMetadata class for type hinting
)
# --- Define discovery directory constant relative to project root ---
# This ensures the path is consistent regardless of where the application is run from
from backend.utils.recipe_utils import PROJECT_ROOT_UTIL
CONTRIB_DISCOVERY_ALGOS_DIR = PROJECT_ROOT_UTIL / "contrib" / "discovery_algorithms"
# --- End constant definition ---

from backend.utils.recipe_executor import execute_recipe
from backend.config.settings import settings # Import application settings instance
from backend.schemas.requests import RecipeExecutionRequest # Use generic request schema for parameters
from backend.schemas.responses import RecipeMetadataResponse, DiscoveryExecutionResponse # Import specific response schemas
# Import DB dependency; although not directly used in this endpoint's logic,
# it might be required by future algorithms or for consistency.
from backend.api.deps import get_db_session

# Logger setup for this module
logger = logging.getLogger(__name__)

# API Router instance for discovery algorithms
router = APIRouter()

# --- Discovery Algorithm Discovery Endpoint ---
@router.get(
    "/",
    response_model=List[RecipeMetadataResponse],
    summary="Discover Available Discovery Algorithms",
)
def get_available_discovery_algorithms():
    """
    Scans the designated directory (`contrib/discovery_algorithms/`) for discovery
    algorithm scripts (Python files following naming convention like `name_vX.py`).

    Parses metadata (name, version, description, parameters) from the docstring
    of the required `find_candidate_repos` function within each valid script.

    Returns:
        List[RecipeMetadataResponse]: A list detailing the metadata of each found
                                      discovery algorithm. Returns an empty list if the
                                      directory is missing or no valid algorithms are found.

    Raises:
        HTTPException: 500 Internal Server Error if the discovery process fails unexpectedly.
    """
    logger.info(f"Request received: Discover discovery algorithms from {CONTRIB_DISCOVERY_ALGOS_DIR}")
    # Check if the designated directory actually exists
    if not CONTRIB_DISCOVERY_ALGOS_DIR.is_dir():
        logger.warning(f"Discovery algorithms directory not found: {CONTRIB_DISCOVERY_ALGOS_DIR}")
        return [] # Return empty list as per the spec if directory doesn't exist

    try:
        # Use the generalized recipe discovery function, pointing it to the correct directory
        # and specifying the target function name expected within discovery scripts.
        discovered_algorithms = discover_recipes(
            recipes_base_dir=CONTRIB_DISCOVERY_ALGOS_DIR,
            target_function_name="find_candidate_repos" # Function name specific to discovery algorithms
        )
        # Convert internal metadata objects to the standard response format
        response_data = [RecipeMetadataResponse(**algo.to_dict()) for algo in discovered_algorithms]
        return response_data
    except Exception as e:
        logger.exception("Error occurred during discovery algorithm discovery.")
        # Raise a generic server error if discovery fails
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to discover discovery algorithms."
        )

# --- Discovery Algorithm Execution Endpoint ---
@router.post(
    "/execute/{algorithm_name}/{algorithm_version}",
    response_model=DiscoveryExecutionResponse, # Expecting a list of strings (URLs)
    summary="Execute a Discovery Algorithm",
    status_code=status.HTTP_200_OK # Use 200 OK as the operation aims for completion and result reporting
)
def execute_discovery_algorithm(
    algorithm_name: str = FastApiPath(..., description="Name of the discovery algorithm to execute."),
    algorithm_version: str = FastApiPath(..., description="Version of the discovery algorithm to execute."),
    request_body: RecipeExecutionRequest = Body(...), # Contains algorithm-specific parameters
    # db: Session = Depends(get_db_session) # DB session currently unused here, keep commented for potential future use
):
    """
    Executes a specific discovery algorithm script to find candidate repository URLs.

    Workflow:
    1. Looks up the algorithm script metadata based on name and version by rescanning the
       `contrib/discovery_algorithms/` directory.
    2. Validates that all required parameters defined in the algorithm's docstring
       (excluding internally managed ones like `db_conn_str` and `github_api_token`)
       are provided in the request body's `parameters` field.
    3. Retrieves the `GITHUB_API_TOKEN` from application settings if available. Checks if the
       token is required by the algorithm signature; if required but missing, raises an error.
       If optional and missing, proceeds allowing anonymous operation if supported by the script.
    4. Retrieves the database connection string (passed to the executor even if the specific
       script doesn't use it, for consistency).
    5. Invokes the `execute_recipe` utility to run the algorithm's `find_candidate_repos` function
       in a sandboxed environment, securely passing parameters, the DB connection string, and the API token (if available).
    6. Validates that the script's return value is a list of strings (URLs).

    Args:
        algorithm_name (str): The unique name of the discovery algorithm.
        algorithm_version (str): The specific version of the algorithm.
        request_body (RecipeExecutionRequest): Contains algorithm-specific `parameters`.
        # db (Session): Database session (currently unused in this endpoint).

    Returns:
        DiscoveryExecutionResponse (List[str]): A list of candidate repository URLs found by the algorithm.

    Raises:
        HTTPException:
            - 404 Not Found: If the specified algorithm name/version doesn't exist.
            - 422 Unprocessable Entity: If required parameters are missing.
            - 500 Internal Server Error: If configuration (DB URL, required GitHub token) is missing,
                                        if script execution fails, or if the script returns
                                        data in an unexpected format.
    """
    logger.info(f"Request received: Execute discovery algorithm '{algorithm_name}' version '{algorithm_version}'")

    # 1. Find Algorithm Metadata (Rescan for execution context)
    # (Consider caching this discovery result in production)
    try:
        discovered_algorithms = discover_recipes(
            recipes_base_dir=CONTRIB_DISCOVERY_ALGOS_DIR,
            target_function_name="find_candidate_repos"
        )
        algo_meta: RecipeMetadata | None = None
        # Locate the metadata for the requested algorithm
        for algo in discovered_algorithms:
            if algo.name == algorithm_name and algo.version == algorithm_version:
                algo_meta = algo
                break
    except Exception as discovery_err:
         logger.exception("Error during discovery algorithm lookup for execution.")
         raise HTTPException(
             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
             detail="Failed to look up discovery algorithm for execution."
         )

    # Handle case where algorithm is not found
    if not algo_meta:
        logger.warning(f"Discovery algorithm not found: {algorithm_name} v{algorithm_version}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Discovery algorithm '{algorithm_name}' version '{algorithm_version}' not found."
        )

    # 2. Parameter Validation against discovered metadata
    required_params_from_docstring = {p.name for p in algo_meta.parameters}
    provided_params_in_body = set(request_body.parameters.keys())
    # Parameters that are handled internally by the executor or are optional for the *user* to provide via the body
    internal_or_optional_params = {'db_conn_str', 'github_api_token'}
    # Determine parameters the user *must* supply within the request_body.parameters field
    required_params_for_body = required_params_from_docstring - internal_or_optional_params
    missing_params_in_body = required_params_for_body - provided_params_in_body

    # Raise error if required parameters are missing from the request body
    if missing_params_in_body:
        logger.warning(f"Missing required parameters in request body 'parameters' field for discovery algorithm {algorithm_name} v{algorithm_version}: {missing_params_in_body}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Missing required parameters in request body 'parameters' field: {', '.join(missing_params_in_body)}"
        )

    # Start building the parameters dictionary for the execution context
    execution_params = request_body.parameters.copy()

    # 3. Get Secrets (GitHub Token) from application settings
    github_token = settings.GITHUB_API_TOKEN
    secrets_dict: Dict[str, str] = {} # Dictionary to pass secrets securely to the executor

    if not github_token:
         # Check if the algorithm's function signature *requires* the token (i.e., not typed as Optional)
         token_required = any(p.name == 'github_api_token' and not p.type.startswith('Optional') for p in algo_meta.parameters)
         if token_required:
             # If required by signature but not configured in settings, it's an operational error
             logger.error("GITHUB_API_TOKEN is required by this algorithm's definition but not configured in application settings.")
             raise HTTPException(
                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                 detail="GitHub API Token is required for this discovery algorithm but is not configured in the server environment."
             )
         else:
             # Token not configured, but the algorithm declares it as optional. Allow execution to proceed.
             # The script itself should handle anonymous operation if applicable.
             logger.warning("GITHUB_API_TOKEN not configured in settings. Discovery algorithm will run anonymously if it supports it.")
    else:
        # Token is available, add it to the secrets dictionary
        secrets_dict["github_api_token"] = github_token

    # 4. Get DB Connection String (pass to executor for consistency, even if unused by this specific script)
    db_connection_string = settings.DATABASE_URL
    if not db_connection_string:
         # Database connection is generally expected to be available
         logger.error("DATABASE_URL is not configured in settings.")
         raise HTTPException(
             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
             detail="Database connection is not configured."
         )

    # 5. Execute Algorithm Script via the recipe executor
    logger.info(f"Calling recipe executor for discovery algorithm: {algo_meta.file_path}")
    try:
        # Pass user parameters, DB string, secrets, and function/type info to the executor
        execution_result = execute_recipe(
            recipe_path_relative=algo_meta.file_path,
            recipe_params=execution_params,
            db_conn_str=db_connection_string,
            script_type='discovery',               # Indicate type for executor context
            function_name='find_candidate_repos',  # Target function in the script
            secrets=secrets_dict                   # Pass secrets dictionary securely
        )
    except Exception as exec_api_err:
        # Catch unexpected errors during the invocation of the executor
        logger.exception(f"Unexpected error calling recipe executor for discovery algorithm {algorithm_name} v{algorithm_version}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to invoke discovery algorithm execution: {exec_api_err}"
        )

    # 6. Process Execution Results
    # Check if the execution result indicates failure
    if not execution_result or execution_result.get("success") is not True:
        error_detail = execution_result.get("error", {"message": "Unknown execution error"})
        logger.error(f"Discovery algorithm execution failed for {algorithm_name} v{algorithm_version}. Error: {error_detail}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            # Report the error message from the script if available
            detail=f"Discovery algorithm execution failed: {error_detail.get('message', 'Unknown error')}"
        )

    # Extract the result data, expected to be a list of strings (URLs)
    candidate_urls = execution_result.get("data", [])
    # Validate the format of the returned data
    if not isinstance(candidate_urls, list) or not all(isinstance(url, str) for url in candidate_urls):
        logger.error(f"Discovery algorithm {algorithm_name} v{algorithm_version} returned unexpected data type: {type(candidate_urls)}. Expected List[str]. Data sample: {str(candidate_urls)[:500]}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Discovery algorithm returned data in an unexpected format (expected a list of URL strings)."
        )

    # Log success and return the validated list of URLs
    logger.info(f"Discovery algorithm {algorithm_name} v{algorithm_version} executed successfully, found {len(candidate_urls)} candidate URLs.")
    # FastAPI automatically uses the DiscoveryExecutionResponse (which is essentially List[str])
    return candidate_urls