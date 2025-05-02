"""
backend.api.v1.endpoints.shared_recipes
---------------------------------------
Defines API endpoints for discovering and executing shared analysis "recipes".
Recipes are contributed Python scripts designed to perform specific data analysis
tasks or queries against the application's database.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException, status, Depends, Body, Path as FastApiPath
from sqlalchemy.orm import Session

# Internal dependencies for recipe discovery, execution, configuration, schemas, and DB access
from backend.utils.recipe_utils import discover_recipes, CONTRIB_QUERIES_DIR, RecipeMetadata, RecipeParameterMetadata # Import utility and constants
from backend.utils.recipe_executor import execute_recipe # Utility to run scripts safely
from backend.config.settings import settings # Access to application settings (e.g., DB URL)
from backend.schemas.requests import RecipeExecutionRequest # Standard request body for execution
from backend.schemas.responses import RecipeMetadataResponse, RecipeExecutionResponse # Standard response models
from backend.api.deps import get_db_session # Database session dependency (though not directly used here)

# Logger setup for this module
logger = logging.getLogger(__name__)

# API Router instance for shared recipe endpoints
router = APIRouter()

# --- Recipe Discovery Endpoint ---
@router.get(
    "/",
    response_model=List[RecipeMetadataResponse],
    summary="Discover Available Analysis Recipes",
)
def get_available_analysis_recipes():
    """
    Scans the designated directory (`contrib/queries/`) for analysis recipe
    scripts (Python files following naming convention like `name_vX.py`).

    Parses metadata (name, version, description, parameters) from the docstring
    of the required `run_analysis` function within each valid script.

    Returns:
        List[RecipeMetadataResponse]: A list containing the metadata for each
                                      discoverable analysis recipe. Returns an empty
                                      list if the directory doesn't exist or no valid
                                      recipes are found.

    Raises:
        HTTPException: 500 Internal Server Error if scanning or parsing fails unexpectedly.
    """
    logger.info(f"Request received: Discover analysis recipes from {CONTRIB_QUERIES_DIR}")
    try:
        # Use the shared discovery utility, targeting the 'queries' directory
        # and the specific function name expected in analysis recipes.
        discovered_recipes = discover_recipes(
            recipes_base_dir=CONTRIB_QUERIES_DIR,
            target_function_name="run_analysis" # Target function for analysis scripts
        )
        # Convert internal metadata objects to the standardized response model
        response_data = [RecipeMetadataResponse(**recipe.to_dict()) for recipe in discovered_recipes]
        return response_data
    except Exception as e:
        # Log and raise generic error if discovery fails
        logger.exception("Error occurred during analysis recipe discovery.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to discover analysis recipes."
        )

# --- Recipe Execution Endpoint ---
@router.post(
    "/execute/{recipe_name}/{recipe_version}",
    response_model=RecipeExecutionResponse, # Expected response structure after execution
    summary="Execute an Analysis Recipe",
    status_code=status.HTTP_200_OK # Use 200 OK for successful execution initiation and result return
)
def execute_analysis_recipe(
    recipe_name: str = FastApiPath(..., description="Name of the recipe script (without .py or version)."),
    recipe_version: str = FastApiPath(..., description="Version identifier of the recipe (e.g., 'v1')."),
    request_body: RecipeExecutionRequest = Body(...), # Contains recipe-specific parameters
    # Note: get_db_session is not directly used here as the connection string is passed
    # to the executor, but it ensures DB is accessible if needed.
    # db: Session = Depends(get_db_session)
):
    """
    Executes a specific analysis recipe script identified by its name and version.

    Workflow:
    1. Locates the recipe script within the `contrib/queries/` directory.
    2. Parses the script's metadata (including expected parameters) from its docstring.
    3. Validates that all parameters marked as required in the docstring (and not flagged
       as optional via type hints like `Optional[...]` or `... | None`) are present
       in the `request_body.parameters` dictionary.
       - Special handling: If `repository_ids` is provided in the request, the requirement
         for a singular `repository_id` (if defined by the script) is ignored.
       - The `db_conn_str` parameter is managed internally and not expected from the user.
    4. Retrieves the database connection string from application settings.
    5. Invokes the `execute_recipe` utility to run the recipe's `run_analysis` function
       in a sandboxed environment, passing the validated parameters and the DB connection string.
    6. Returns the result object provided by the `execute_recipe` utility, which includes
       success status, data payload, or error details.

    Args:
        recipe_name (str): The unique name of the recipe.
        recipe_version (str): The specific version of the recipe.
        request_body (RecipeExecutionRequest): The request payload containing recipe-specific
                                                `parameters`.
        # db (Session): The SQLAlchemy database session (dependency available but not directly used).

    Returns:
        RecipeExecutionResponse: An object summarizing the execution outcome, including
                                 success status, data (if successful), or error details.

    Raises:
        HTTPException:
            - 404 Not Found: If the specified recipe name/version doesn't exist.
            - 422 Unprocessable Entity: If required parameters are missing from the request body.
            - 500 Internal Server Error: If database connection is missing, script execution fails,
                                        or an unexpected error occurs during the process.
    """
    logger.info(f"Request received: Execute recipe '{recipe_name}' version '{recipe_version}' with params: {list(request_body.parameters.keys())}")

    # 1. Find Recipe Metadata (Rescan directory for execution context)
    # (Consider caching this discovery result in production)
    try:
        discovered_recipes = discover_recipes(
            recipes_base_dir=CONTRIB_QUERIES_DIR,
            target_function_name="run_analysis"
        )
        recipe_meta: RecipeMetadata | None = None
        # Find the specific recipe matching the request path parameters
        for recipe in discovered_recipes:
            if recipe.name == recipe_name and recipe.version == recipe_version:
                recipe_meta = recipe
                break
    except Exception as discovery_err:
         # Handle errors during the lookup process itself
         logger.exception("Error during recipe lookup for execution.")
         raise HTTPException(
             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
             detail="Failed to look up recipe for execution."
         )

    # Handle case where the recipe is not found
    if not recipe_meta:
        logger.warning(f"Recipe not found: {recipe_name} v{recipe_version}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipe '{recipe_name}' version '{recipe_version}' not found."
        )

    # --- 2. FIXED Parameter validation against discovered metadata ---
    provided_params = set(request_body.parameters.keys())
    missing_required_params = set()
    # Check if the user is providing a list of repository IDs, which might affect
    # whether a single 'repository_id' parameter is still required.
    providing_multiple_repos = 'repository_ids' in provided_params

    # Iterate through parameters defined in the recipe's docstring metadata
    for param_meta in recipe_meta.parameters:
        # Ignore parameters managed internally by the execution environment
        if param_meta.name == 'db_conn_str':
            continue

        # If the user provides 'repository_ids', skip checking requirement for 'repository_id'
        # This allows recipes to accept either a single ID or a list.
        if param_meta.name == 'repository_id' and providing_multiple_repos:
            logger.debug(f"Ignoring requirement check for '{param_meta.name}' because 'repository_ids' was provided.")
            continue
        # Also skip requirement check for 'repository_ids' itself if provided (handled above)
        if param_meta.name == 'repository_ids' and providing_multiple_repos:
             continue

        # Determine if the parameter is optional based on its type hint in the docstring metadata.
        # Checks for standard 'Optional[...]' syntax or '... | None'.
        is_optional = param_meta.type.startswith('Optional[') or ' | None' in param_meta.type or 'Optional' in param_meta.type

        # If the parameter is NOT optional AND it was NOT provided in the request body, mark it as missing.
        if not is_optional and param_meta.name not in provided_params:
            missing_required_params.add(param_meta.name)
            logger.debug(f"Parameter '{param_meta.name}' (Type: {param_meta.type}) identified as required but missing. Optional: {is_optional}, Provided: {provided_params}")


    # If any required parameters were found missing, raise a validation error.
    if missing_required_params:
        missing_params_str = ', '.join(sorted(list(missing_required_params)))
        logger.warning(f"Missing required parameters for recipe {recipe_name} v{recipe_version}: {missing_params_str}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Missing required parameters: {missing_params_str}"
        )
    # --- END FIXED VALIDATION ---

    # 3. Get Database Connection String from application settings
    db_connection_string = settings.DATABASE_URL
    if not db_connection_string:
         # DB connection is essential for recipes interacting with data
         logger.error("DATABASE_URL is not configured in settings.")
         raise HTTPException(
             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
             detail="Database connection string is not configured."
         )

    # 4. Prepare final parameters for the executor
    # Start with the parameters provided by the user
    final_params = request_body.parameters.copy()
    # Note: 'db_conn_str' is passed separately to the executor, not usually included in the 'recipe_params' dict
    # unless the recipe script *explicitly* defines 'db_conn_str' as one of its function arguments.

    # 5. Execute the recipe script via the executor utility
    logger.info(f"Calling recipe executor for: {recipe_meta.file_path} with params keys: {list(final_params.keys())}")
    try:
        # The executor handles running the script's 'run_analysis' function
        execution_result = execute_recipe(
            recipe_path_relative=recipe_meta.file_path, # Path to the script
            recipe_params=final_params,                 # User-provided parameters
            db_conn_str=db_connection_string,           # DB connection string for the script
            script_type='analysis',                     # Type indicator for the executor
            function_name='run_analysis'                # Target function within the script
            # secrets={} # Pass secrets dictionary if analysis recipes need them
        )
        # Log the outcome reported by the executor
        logger.info(f"Recipe executor finished for: {recipe_meta.file_path}. Reported success: {execution_result.get('success')}")
        # Return the entire result object from the executor (contains success, data/error)
        return execution_result
    except Exception as exec_err:
        # Catch unexpected errors during the API endpoint's attempt to call the executor
        logger.exception(f"Unexpected error in API endpoint while trying to execute recipe {recipe_name} v{recipe_version}: {exec_err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected server error occurred during recipe execution: {exec_err}"
        )