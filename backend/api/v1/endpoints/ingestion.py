"""
backend.api.v1.endpoints.ingestion
----------------------------------
Defines API endpoints for triggering and monitoring data ingestion processes.
Includes endpoints for ingesting data based on a repository URL (synchronously)
and based on keywords (asynchronously via Celery).
"""

import logging
from datetime import datetime, timezone
from typing import Optional
# BackgroundTasks is no longer used as keyword ingestion is handled by Celery
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

# Import the Celery application instance for task queuing
from backend.celery_app import celery_app

# Internal dependencies for database session, models, schemas, services, and task definitions
from backend.api.deps import get_db_session
# Import SessionLocal directly for creating isolated sessions in error handling
from backend.data.database import SessionLocal
from backend.schemas.requests import IngestionRequest, KeywordIngestionRequest
from backend.schemas.responses import DiscoveryChainSummary, KeywordSearchSessionResponse
from backend.data.repositories import KeywordSearchSessionRepository
from backend.data.models import KeywordSearchSession
# Import IngestionService, primarily used by the synchronous URL endpoint
from backend.services.ingestion_service import IngestionService
# Ensure task module is implicitly loaded if not explicitly imported elsewhere,
# although direct task import isn't needed here as we use send_task by name.
# from backend.tasks import discovery_tasks # Example if needed

# Logger setup for this module
logger = logging.getLogger(__name__)

# API Router instance for ingestion endpoints
router = APIRouter()


# --- Endpoint for URL Ingestion (Synchronous Core Logic) ---
@router.post(
    "/url",
    response_model=DiscoveryChainSummary,
    summary="Trigger ingestion by Repository URL",
    # 202 Accepted is appropriate as the request is accepted, and while the main
    # URL processing might be synchronous, subsequent background tasks (like DOI processing)
    # might still occur. It signals initiation rather than immediate completion of *all* work.
    status_code=status.HTTP_202_ACCEPTED
)
def ingest_by_url(
    request: IngestionRequest,
    db: Session = Depends(get_db_session) # Database session dependency
):
    """
    Accepts a GitHub repository URL and triggers the core ingestion process *synchronously*
    within the request lifecycle via the `IngestionService`.

    While the primary repository data fetching and initial processing happen synchronously,
    the service itself might launch asynchronous Celery tasks for deeper analysis like
    DOI resolution.

    This endpoint immediately attempts the ingestion and returns a summary of the
    root `DiscoveryChain` created for tracking this specific ingestion event. The status
    within the returned summary reflects the outcome of the synchronous part.

    Args:
        request (IngestionRequest): Request body containing the 'url' of the repository.
        db (Session): The SQLAlchemy database session.

    Returns:
        DiscoveryChainSummary: A summary of the root discovery chain, including its ID
                               and status (e.g., 'COMPLETED', 'FAILED').

    Raises:
        HTTPException:
            - 400 Bad Request: If the URL is invalid or cannot be parsed.
            - 500 Internal Server Error: If the ingestion service encounters a critical error
                                        during the synchronous processing phase.
    """
    logger.info(f"Received ingestion request for URL: {request.url}")
    # Instantiate the service responsible for the ingestion logic
    ingestion_service = IngestionService()
    try:
        # Ensure the URL is treated as a string
        url_str = str(request.url)
        # Call the synchronous service method to handle the ingestion
        root_chain = ingestion_service.ingest_repository_by_url(db=db, repo_url=url_str)

        # Check if the service method indicated failure to even start (e.g., invalid URL format)
        if root_chain is None:
            # This indicates an early failure within the service, likely validation.
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid repository URL format or unable to initiate ingestion.")

        # Re-fetch the state from the database. While less critical in a purely sync flow,
        # it's good practice if the service *could* have modified it commit/flush happened.
        db.refresh(root_chain)

        # Explicitly check the final status recorded in the database after the service call returns.
        if root_chain.status == "FAILED":
             logger.error(f"Synchronous part of ingestion failed for URL {url_str}. Root chain ID: {root_chain.id}. Check service logs for details.")
             # Return the summary of the failed chain. The HTTP status remains 202 (Accepted),
             # but the response body indicates the failure outcome.
             return root_chain
        elif root_chain.status != "COMPLETED":
              # Log if the synchronous part finished with an unexpected status (e.g., PENDING if workflow changed)
              logger.warning(f"Synchronous part of ingestion for URL {url_str} finished with unexpected status '{root_chain.status}'. Chain ID: {root_chain.id}.")
              return root_chain # Return the chain summary with its current status

        # Log successful completion of the synchronous part
        logger.info(f"Synchronous part of ingestion completed successfully for {url_str}, root chain ID: {root_chain.id}")
        # Return the summary of the successfully completed root chain
        return root_chain

    except ValueError as ve:
         # Catch specific validation errors raised potentially by Pydantic or service logic
         logger.error(f"Value error during ingestion request for {request.url}: {ve}", exc_info=True)
         # Ensure transaction rollback on error
         try: db.rollback()
         except Exception: logger.error("Failed to rollback transaction after ValueError.")
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except RuntimeError as re:
        # Catch runtime errors that might indicate deeper issues in the service
        logger.error(f"Runtime error during ingestion for {request.url}: {re}", exc_info=True)
        try: db.rollback()
        except Exception: logger.error("Failed to rollback transaction after RuntimeError.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Ingestion process encountered a runtime error for URL {request.url}. Check server logs.")
    except Exception as e:
        # Catch any other unexpected exceptions during the endpoint execution
        logger.exception(f"Unexpected error during /ingest/url endpoint for {request.url}")
        try: db.rollback()
        except Exception: logger.error("Failed to rollback transaction after unexpected exception.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred during URL ingestion.")


# --- Endpoint for Keyword Ingestion (Asynchronous via Celery) ---
@router.post(
    "/keywords",
    response_model=KeywordSearchSessionResponse,
    summary="Trigger discovery and ingestion by Keywords (Async via Celery)",
    status_code=status.HTTP_202_ACCEPTED # 202 Accepted indicates the task is queued, not completed
)
def ingest_by_keywords(
    request: KeywordIngestionRequest,
    db: Session = Depends(get_db_session) # Database session dependency
):
    """
    Accepts keywords, initiates a keyword search session, and queues an asynchronous
    Celery task (`keyword_discovery_celery_task`) to perform the actual discovery
    and subsequent ingestion of found repositories.

    Workflow:
    1. Validates that keywords are provided.
    2. Creates a `KeywordSearchSession` record in the database with an initial
       status of 'QUEUED'.
    3. **Crucially, commits the database transaction** to ensure the session record
       exists with its ID before the Celery task attempts to access it.
    4. Sends the task to the Celery queue, passing the newly created session ID
       and the keywords.
    5. Returns the details of the newly created `KeywordSearchSession` record
       (with status 'QUEUED') immediately to the client.

    The client should use the returned `session_id` to poll the
    `/ingest/keywords/status/{session_id}` endpoint to monitor the progress
    of the asynchronous task.

    Args:
        request (KeywordIngestionRequest): Request body containing the 'keywords' string.
        db (Session): The SQLAlchemy database session.

    Returns:
        KeywordSearchSessionResponse: Details of the search session just created,
                                      with status 'QUEUED'.

    Raises:
        HTTPException:
            - 400 Bad Request: If the 'keywords' field is empty.
            - 500 Internal Server Error: If the initial session record cannot be created
                                        in the database, or if the task fails to be
                                        enqueued in Celery.
    """
    logger.info(f"Received keyword ingestion request for: '{request.keywords}'")

    # Basic validation
    if not request.keywords:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Keywords cannot be empty."
        )

    session_repo = KeywordSearchSessionRepository(db)
    search_session: KeywordSearchSession | None = None # Initialize for potential use in error handling

    try:
        # 1. Create the initial KeywordSearchSession record in the database
        search_session = KeywordSearchSession(
            keywords_raw=request.keywords,
            status="QUEUED", # Set initial status
            started_at=None, # Task will set this when it starts
            # completed_at=None, # Task will set this on completion/failure
            # created_at is handled by the model default timestamp
        )
        db.add(search_session)

        # --- IMPORTANT: Commit *before* sending the task ---
        # This ensures the session record (and its generated ID) is visible
        # in the database for the Celery worker when it picks up the task.
        db.commit()
        # Refresh the object to load the generated ID and any default values
        db.refresh(search_session)
        session_id = search_session.id
        # --- End Commit ---

        logger.info(f"Created KeywordSearchSession {session_id} with status QUEUED for keywords: '{request.keywords}'.")

        # 2. Enqueue the Celery task to perform the discovery and ingestion
        try:
            # Send the task to the Celery queue by its registered name.
            # Pass necessary arguments (session ID, keywords) for the task function.
            # Note: The task name format is typically 'module.path.to.function'.
            celery_app.send_task(
                'backend.tasks.discovery_tasks.keyword_discovery_celery_task',
                args=[session_id, request.keywords]
                # Optionally add kwargs={}, countdown=, eta=, etc.
            )
            logger.info(f"Successfully enqueued Celery task 'keyword_discovery_celery_task' for session {session_id}.")
        except Exception as celery_err:
             # Handle potential errors during communication with the Celery broker (e.g., connection refused)
             logger.exception(f"Failed to send task to Celery for session {session_id}. Attempting to mark session as FAILED.")

             # --- Best-effort attempt to mark the session as FAILED ---
             # Use a new, independent database session for this update to avoid interfering
             # with the main request's session state, especially in error scenarios.
             try:
                 # Create a new session scope using SessionLocal factory
                 with SessionLocal() as temp_db:
                     # Retrieve the session record within the new session
                     failed_session = temp_db.get(KeywordSearchSession, session_id)
                     if failed_session:
                         # Update status and completion time
                         failed_session.status = "FAILED"
                         failed_session.completed_at = datetime.now(timezone.utc)
                         # Add and commit within the temporary session
                         temp_db.add(failed_session)
                         temp_db.commit()
                         logger.warning(f"Successfully marked session {session_id} as FAILED in DB due to Celery enqueue error.")
                     else:
                         # This case should be rare if commit succeeded earlier, but log if it happens
                         logger.error(f"Could not find session {session_id} in temporary session to mark as FAILED after Celery error.")
             except Exception as fail_update_err:
                 # Log errors during the failure update attempt itself
                 logger.error(f"Error occurred while trying to mark session {session_id} as FAILED via temporary session: {fail_update_err}")
                 # Note: We don't rollback temp_db here as context manager handles it.

             # Raise an HTTP exception to signal the failure to the client
             raise HTTPException(status_code=500, detail="Failed to enqueue the background discovery task. The process could not be started.")

        # 3. Return the initially created session details (status is 'QUEUED')
        # The client now knows the task is accepted and has the ID to track it.
        return search_session

    except Exception as e:
        # Catch errors during the initial database interaction (session creation/commit)
        logger.exception(f"Error creating initial KeywordSearchSession or committing for keywords: '{request.keywords}'")
        # Rollback the main transaction if session creation failed before commit
        try:
            db.rollback()
        except Exception as rb_err:
            logger.error(f"Error during rollback after failing to create session: {rb_err}")
        # Signal internal server error
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate the keyword search session due to a database error.",
        )


# --- Endpoint for Keyword Status Check ---
@router.get(
    "/keywords/status/{session_id}",
    response_model=KeywordSearchSessionResponse,
    summary="Get status of a Keyword Search Session"
)
def get_keyword_session_status(
    session_id: int,
    db: Session = Depends(get_db_session) # Database session dependency
):
    """
    Retrieves the current status and details of a specific KeywordSearchSession
    using its unique database ID.

    This endpoint is intended for clients to poll the status of an asynchronous
    keyword ingestion task previously initiated via the `/ingest/keywords` endpoint.

    Args:
        session_id (int): The database ID of the KeywordSearchSession to query.
        db (Session): The SQLAlchemy database session.

    Returns:
        KeywordSearchSessionResponse: The current details of the session, including
                                      its status ('QUEUED', 'RUNNING', 'COMPLETED', 'FAILED'),
                                      timestamps, and associated results count if completed.

    Raises:
        HTTPException: 404 Not Found if no session exists with the provided ID.
    """
    logger.info(f"Received status request for KeywordSearchSession ID: {session_id}")
    session_repo = KeywordSearchSessionRepository(db=db)
    # Fetch the session directly using the repository's 'get' method
    search_session = session_repo.get(id=session_id)

    # Handle case where the session ID does not exist
    if not search_session:
        logger.warning(f"KeywordSearchSession with id {session_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"KeywordSearchSession with id {session_id} not found.",
        )

    # Log the status being returned for debugging/monitoring
    logger.debug(f"Returning status '{search_session.status}' for session {session_id}")
    # Return the full session details matching the response model
    return search_session
# --- END ---