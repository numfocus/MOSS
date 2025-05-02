"""
backend.api.v1.endpoints.affiliation_algorithms
-----------------------------------------------
Defines API endpoints related to the discovery and execution of
repository-institution affiliation algorithms. These algorithms are
contributed scripts designed to predict or determine affiliations
based on various data points.
"""

import logging
from typing import List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, Body, Path as FastApiPath
from sqlalchemy.orm import Session

# Internal dependencies for database session management, configuration, and utilities
from backend.api.deps import get_db_session
from backend.config.settings import settings
# Uses generalized discover_recipes and specific dir constant
from backend.utils.recipe_utils import discover_recipes, CONTRIB_AFFILIATION_ALGOS_DIR, RecipeMetadata
from backend.utils.recipe_executor import execute_recipe
# Import request/response schemas and database repository
from backend.schemas.requests import AffiliationExecutionRequest
from backend.schemas.responses import AffiliationExecutionResponse, RecipeMetadataResponse
from backend.data.repositories import RepositoryInstitutionAffiliationRepository
# Keep for constant def if needed elsewhere, though not directly used in this endpoint logic
from backend.utils.recipe_utils import PROJECT_ROOT_UTIL

# Logger setup for this module
logger = logging.getLogger(__name__)

# API Router instance for affiliation algorithms
router = APIRouter()

# --- AFFILIATION ALGORITHM DISCOVERY ENDPOINT ---
@router.get(
    "/",
    response_model=List[RecipeMetadataResponse],
    summary="Discover Available Affiliation Algorithms",
)
def get_available_affiliation_algorithms():
    """
    Scans the designated directory (`contrib/affiliation_algorithms/`) for affiliation
    algorithm scripts (Python files following naming convention like `name_vX.py`).

    It parses metadata (name, version, description, parameters) extracted from the
    docstring of the mandatory `calculate_affiliations` function within each valid script.

    Returns:
        List[RecipeMetadataResponse]: A list containing the metadata for each
                                      discoverable affiliation algorithm. Returns an empty
                                      list if the directory doesn't exist or no valid
                                      algorithms are found.

    Raises:
        HTTPException: 500 Internal Server Error if scanning or parsing fails unexpectedly.
    """
    logger.info(f"Request received: Discover affiliation algorithms from {CONTRIB_AFFILIATION_ALGOS_DIR}")
    try:
        # Utilize the shared recipe discovery utility, specifying the target directory and function name
        discovered_algorithms = discover_recipes(
            recipes_base_dir=CONTRIB_AFFILIATION_ALGOS_DIR,
            target_function_name="calculate_affiliations"  # Target function specific to affiliation logic
        )
        # Convert the internal RecipeMetadata objects to the standardized response model
        response_data = [RecipeMetadataResponse(**algo.to_dict()) for algo in discovered_algorithms]
        return response_data
    except Exception as e:
        logger.exception("Error occurred during affiliation algorithm discovery.")
        # Raise a generic server error if any part of the discovery process fails
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to discover affiliation algorithms."
        )
# --- END DISCOVERY ENDPOINT ---


# --- AFFILIATION ALGORITHM EXECUTION ENDPOINT ---
@router.post(
    "/execute/{algorithm_name}/{algorithm_version}",
    response_model=AffiliationExecutionResponse,
    summary="Execute an Affiliation Algorithm",
    status_code=status.HTTP_200_OK  # Use 200 OK as the operation aims for completion and result reporting
)
def execute_affiliation_algorithm(
    algorithm_name: str = FastApiPath(..., description="Name of the affiliation algorithm to execute."),
    algorithm_version: str = FastApiPath(..., description="Version of the affiliation algorithm to execute."),
    request_body: AffiliationExecutionRequest = Body(...), # Contains institution_id and algorithm-specific params
    db: Session = Depends(get_db_session) # Database session dependency
):
    """
    Executes a specific affiliation algorithm script identified by its name and version.

    Workflow:
    1. Locates the algorithm script within the `contrib/affiliation_algorithms/` directory.
    2. Validates that all required parameters defined in the script's docstring (excluding
       `db_conn_str` and the required `institution_id` from the request body root)
       are present in the request body's `parameters` field.
    3. Retrieves the database connection string from application settings.
    4. Invokes the `execute_recipe` utility to run the algorithm's `calculate_affiliations`
       function in a sandboxed environment, passing necessary parameters and the DB connection string.
    5. Processes the list of affiliation results (dictionaries containing `repository_id`,
       `confidence_score`, `evidence`, etc.) returned by the script.
    6. For each valid result, creates or updates the corresponding record in the
       `repository_institution_affiliations` table using the `RepositoryInstitutionAffiliationRepository`.
    7. Commits the database transaction.

    Args:
        algorithm_name (str): The unique name of the algorithm.
        algorithm_version (str): The specific version of the algorithm.
        request_body (AffiliationExecutionRequest): The request payload, including the target
                                                    `institution_id` and any algorithm-specific
                                                    `parameters`.
        db (Session): The SQLAlchemy database session.

    Returns:
        AffiliationExecutionResponse: An object summarizing the execution outcome, including status,
                                      message, and counts of processed, created, and updated affiliations.

    Raises:
        HTTPException:
            - 404 Not Found: If the specified algorithm name/version doesn't exist.
            - 422 Unprocessable Entity: If required parameters are missing in the request body.
            - 500 Internal Server Error: If database connection is missing, script execution fails,
                                        or results cannot be stored in the database.
    """
    logger.info(f"Request received: Execute affiliation algorithm '{algorithm_name}' version '{algorithm_version}' for institution {request_body.institution_id}")

    # 1. Find Algorithm Metadata by scanning the directory again
    # (Consider caching this discovery result in a production environment for performance)
    try:
        discovered_algorithms = discover_recipes(
            recipes_base_dir=CONTRIB_AFFILIATION_ALGOS_DIR,
            target_function_name="calculate_affiliations"
        )
        algo_meta: RecipeMetadata | None = None
        # Find the specific algorithm matching the request path parameters
        for algo in discovered_algorithms:
            if algo.name == algorithm_name and algo.version == algorithm_version:
                algo_meta = algo
                break
    except Exception as discovery_err:
         logger.exception("Error during affiliation algorithm lookup for execution.")
         raise HTTPException(
             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
             detail="Failed to look up affiliation algorithm for execution."
         )

    # Handle case where the algorithm is not found
    if not algo_meta:
        logger.warning(f"Affiliation algorithm not found: {algorithm_name} v{algorithm_version}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Affiliation algorithm '{algorithm_name}' version '{algorithm_version}' not found."
        )

    # 2. Parameter Validation against the discovered metadata
    required_params_from_docstring = {p.name for p in algo_meta.parameters}
    provided_params_in_body = set(request_body.parameters.keys())
    # Parameters injected by the runner or part of the main request body, not the 'parameters' dict
    internal_or_request_params = {'db_conn_str', 'institution_id'}
    # Determine which parameters expected by the script's function *must* be in the 'parameters' part of the request body
    required_params_for_body = required_params_from_docstring - internal_or_request_params
    missing_params_in_body = required_params_for_body - provided_params_in_body

    # Ensure the algorithm's docstring includes 'institution_id' as it's fundamental
    if 'institution_id' not in required_params_from_docstring:
         logger.error(f"Algorithm {algorithm_name} v{algorithm_version} docstring missing required 'institution_id' parameter definition.")
         # Note: This is a developer error in the script, raising 500 as the system can't proceed correctly.
         # Alternatively, could raise 422 if treated as a client error trying to use a badly defined script.
         # Choosing 500 as it indicates a problem with the algorithm definition itself.
         raise HTTPException(
             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
             detail=f"Algorithm definition for '{algorithm_name}' v'{algorithm_version}' is missing the 'institution_id' parameter."
         )

    # Raise error if any required parameters for the body dict are missing
    if missing_params_in_body:
        logger.warning(f"Missing required parameters in request body 'parameters' field for {algorithm_name} v{algorithm_version}: {missing_params_in_body}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Missing required parameters in request body 'parameters' field: {', '.join(missing_params_in_body)}"
        )

    # Combine institution ID with other parameters for the script execution context
    execution_params = {"institution_id": request_body.institution_id, **request_body.parameters}

    # 3. Get DB Connection String from application settings
    db_connection_string = settings.DATABASE_URL
    if not db_connection_string:
         logger.error("DATABASE_URL is not configured in settings.")
         raise HTTPException(
             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
             detail="Database connection is not configured."
         )

    # 4. Execute Algorithm Script via the recipe executor utility
    logger.info(f"Calling recipe executor for affiliation algorithm: {algo_meta.file_path}")
    try:
        # The executor handles running the script's target function in a separate process
        execution_result = execute_recipe(
            recipe_path_relative=algo_meta.file_path,      # Path to the script file
            recipe_params=execution_params,                # Parameters for the script's function
            db_conn_str=db_connection_string,              # Database connection string
            script_type='affiliation',                     # Type indicator for the executor
            function_name='calculate_affiliations'         # Target function within the script
        )
    except Exception as exec_api_err:
        # Catch unexpected errors during the invocation of the executor itself
        logger.exception(f"Unexpected error calling recipe executor for {algorithm_name} v{algorithm_version}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to invoke algorithm execution: {exec_api_err}"
        )

    # 5. Process Execution Results
    # Check if the execution itself reported failure
    if not execution_result or execution_result.get("success") is not True:
        error_detail = execution_result.get("error", {"message": "Unknown execution error"})
        logger.error(f"Affiliation algorithm execution failed for {algorithm_name} v{algorithm_version}. Error: {error_detail}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            # Provide the error message from the script if available
            detail=f"Affiliation algorithm execution failed: {error_detail.get('message', 'Unknown error')}"
        )

    # Extract the data payload, expected to be a list of dictionaries
    affiliation_results: List[Dict[str, Any]] = execution_result.get("data", [])
    # Validate the structure of the returned data
    if not isinstance(affiliation_results, list):
        logger.error(f"Affiliation algorithm {algorithm_name} v{algorithm_version} returned unexpected data type: {type(affiliation_results)}. Expected List[Dict].")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Affiliation algorithm returned data in an unexpected format."
        )

    # Initialize counters for the response summary
    processed_count = len(affiliation_results) # Total results returned by the script
    created_count = 0
    updated_count = 0

    # Handle the case where the algorithm runs successfully but finds no affiliations
    if not affiliation_results:
        logger.info(f"Affiliation algorithm {algorithm_name} v{algorithm_version} returned 0 results for institution {request_body.institution_id}.")
        return AffiliationExecutionResponse(
            status="COMPLETED",
            message="Affiliation calculation completed. Algorithm returned 0 results.",
            processed_count=0,
            created_count=0,
            updated_count=0
        )

    # 6. Store Results in Database
    affiliation_repo = RepositoryInstitutionAffiliationRepository(db)
    try:
        successful_items_stored = 0 # Count items successfully processed and prepared for commit
        # Iterate through each result dictionary returned by the algorithm
        for result_item in affiliation_results:
            # Extract required fields, handling potential missing keys gracefully
            repo_id = result_item.get("repository_id")
            confidence = result_item.get("confidence_score")
            # Evidence might be optional or structured differently depending on the algorithm
            evidence = result_item.get("evidence") # Can be None or any JSON-serializable structure

            # Basic validation of required fields
            if repo_id is None or confidence is None:
                logger.warning(f"Skipping affiliation result due to missing 'repository_id' or 'confidence_score': {result_item}")
                continue # Skip this potentially malformed result item

            # Ensure confidence score is a float
            try:
                 confidence_float = float(confidence)
            except (ValueError, TypeError):
                 logger.warning(f"Skipping affiliation result due to invalid 'confidence_score' type ({type(confidence)}): {result_item}")
                 continue # Skip item if confidence score is not convertible to float

            # Attempt to create or update the affiliation record in the database
            try:
                # The repository method handles the logic of finding existing records or creating new ones
                _, created = affiliation_repo.create_or_update_affiliation(
                    repository_id=int(repo_id), # Ensure repo_id is integer
                    institution_id=request_body.institution_id, # The target institution for this run
                    algorithm_name=algorithm_name, # Store which algorithm generated this result
                    algorithm_version=algorithm_version, # Store the specific version
                    confidence_score=confidence_float, # The calculated score
                    evidence=evidence, # Supporting evidence (JSON compatible)
                    parameters_used=request_body.parameters # Store parameters used for this run for traceability
                )
                # Update counters based on whether a new record was created or an existing one updated
                if created:
                    created_count += 1
                else:
                    updated_count += 1
                successful_items_stored += 1 # Increment count of successfully processed items

            except Exception as item_db_err:
                 # Log errors occurring during the processing of a single item, but allow the loop to continue
                 # This prevents one bad result from stopping the processing of others.
                 logger.error(f"Database error storing single affiliation result for Repo ID {repo_id}, Inst ID {request_body.institution_id}: {item_db_err}", exc_info=True)
                 # Do not increment successful_items_stored for this item

        # Commit the transaction only if at least one item was successfully processed and staged for commit
        if successful_items_stored > 0:
             db.commit()
             logger.info(f"Successfully processed and stored {successful_items_stored} affiliation results for Inst {request_body.institution_id} (Created: {created_count}, Updated: {updated_count}).")
        else:
             # If no items were successfully processed (e.g., all had validation errors or DB errors), log this.
             # A rollback might be implicitly handled by the session context manager or error handling above,
             # but explicitly rolling back ensures no partial state if individual errors occurred but weren't caught cleanly.
             logger.warning(f"No affiliation results were successfully processed for database storage for Inst {request_body.institution_id}.")
             db.rollback()


        # Return the final summary response
        return AffiliationExecutionResponse(
            status="COMPLETED",
            message=f"Affiliation calculation completed. Items returned by script: {processed_count}. Successfully stored/updated in DB: {successful_items_stored}. Created: {created_count}, Updated: {updated_count}.",
            processed_count=processed_count, # Total items the script *returned*
            created_count=created_count,     # Count of new DB records
            updated_count=updated_count      # Count of updated DB records
        )

    except Exception as db_err:
        # Catch broader errors that might occur outside the loop (e.g., during commit if not caught earlier)
        logger.exception(f"Database error storing affiliation results batch for Inst {request_body.institution_id}, Algo {algorithm_name} v{algorithm_version}")
        # Ensure any partial changes from the loop are rolled back
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store affiliation results in database: {db_err}"
        )