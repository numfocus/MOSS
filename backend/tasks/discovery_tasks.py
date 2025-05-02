# --- START OF FILE discovery_tasks.py ---
"""
backend.tasks.discovery_tasks
-----------------------------

Defines Celery background tasks related to the discovery and ingestion
of data based on keyword searches, primarily targeting GitHub repositories.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from celery.exceptions import Ignore # Used to gracefully stop task processing without failure.

# Import the configured Celery application instance.
from backend.celery_app import celery_app
# Import the database session factory for creating task-specific sessions.
from backend.data.database import SessionLocal
# Import data models and repository classes required for database operations.
from backend.data.models import KeywordSearchSession
from backend.data.repositories import KeywordSearchSessionRepository
# Import application services and external API clients.
from backend.services import KeywordDiscoveryService, IngestionService
from backend.external import GitHubClient, ApiClientError

# Setup logger for this module.
logger = logging.getLogger(__name__)

@celery_app.task(
    bind=True,                          # Makes 'self' (the task instance) available inside the function.
    autoretry_for=(ApiClientError, Exception), # Automatically retry on GitHub API errors or unexpected exceptions.
    retry_backoff=True,                 # Apply exponential backoff between retries.
    max_retries=3,                      # Limit the number of automatic retries.
    acks_late=True,                     # Acknowledge task message only after task success/failure (ensures retry if worker crashes).
    task_reject_on_worker_lost=True     # Requeue task if the worker process executing it is lost.
)
def keyword_discovery_celery_task(self, session_id: int, keywords: str):
    """
    Celery task to perform keyword-based discovery of GitHub repositories,
    ingest relevant data (metadata, README, DOIs), and update the status
    of the corresponding KeywordSearchSession.

    This task manages its own database session lifecycle and ensures the final
    status (COMPLETED or FAILED) of the KeywordSearchSession is recorded,
    even if errors occur during processing.

    Args:
        self: The Celery task instance (available due to bind=True).
        session_id: The primary key of the KeywordSearchSession record associated
                    with this discovery process.
        keywords: The string of keywords used for the GitHub search.
    """
    # Extract task ID for correlated logging.
    task_id = self.request.id if hasattr(self, 'request') and self.request.id else 'UNKNOWN_TASK_ID'
    log_prefix = f"CELERY TASK {task_id} (Session: {session_id})"
    logger.info(f"{log_prefix}: STARTING Keyword Discovery Task for keywords: '{keywords}'.")

    db: Session | None = None                       # Database session for this task run.
    search_session: KeywordSearchSession | None = None # The session record being processed.
    processed_count = 0                             # Counter for successfully processed items.
    ingestion_errors = 0                            # Counter for errors during data ingestion.
    association_errors = 0                          # Counter for errors during association logic.
    task_exception: Optional[Exception] = None      # Stores any exception caught in the main try block.

    try:
        # Create a new database session for this task invocation.
        db = SessionLocal()
        logger.info(f"{log_prefix}: Database session established.")

        # Instantiate dependencies required for the discovery process.
        # Catch configuration errors (e.g., missing API keys) during initialization.
        try:
            github_client = GitHubClient()
            ingestion_service = IngestionService() # Assumes DB session not needed at init.
            keyword_discovery_service = KeywordDiscoveryService(
                github_client=github_client,
                ingestion_service=ingestion_service
            )
            logger.info(f"{log_prefix}: Core services initialized.")
        except ValueError as config_err: # Catch potential issues like missing API keys.
            logger.error(f"{log_prefix}: CONFIGURATION ERROR during service initialization: {config_err}", exc_info=True)
            task_exception = config_err
            # Re-raise to let Celery handle retries or mark as failed based on task config.
            raise task_exception

        logger.info(f"{log_prefix}: Invoking keyword_discovery_service.discover_and_ingest_by_keywords...")
        # --- Execute the core discovery and ingestion logic ---
        # The service method is responsible for:
        # 1. Updating the KeywordSearchSession status to 'RUNNING'.
        # 2. Performing the GitHub search and processing results.
        # 3. Ingesting data for discovered repositories.
        # 4. Returning counts of processed items and any errors encountered.
        processed_count, ingestion_errors, association_errors = keyword_discovery_service.discover_and_ingest_by_keywords(
            db=db, # Pass the task-managed database session.
            session_id=session_id,
            keywords=keywords
        )
        logger.info(f"{log_prefix}: Service call completed. Results: Processed={processed_count}, IngestErrors={ingestion_errors}, AssocErrors={association_errors}")

    except Exception as e:
        # Catch exceptions occurring *before* or *during* the main service call.
        # This includes configuration errors raised above or errors within the service itself.
        logger.exception(f"{log_prefix}: EXCEPTION caught during task execution.")
        task_exception = e # Store the exception for the finally block.

        # Re-raise the exception to trigger Celery's retry/failure mechanisms
        # as defined in the task decorator (`autoretry_for`).
        # Using self.retry allows for custom backoff or error handling if needed,
        # but here we rely on autoretry_for.
        # Note: A manual retry could look like:
        # try:
        #     if hasattr(self, 'request') and hasattr(self, 'retry'):
        #          logger.warning(f"{log_prefix}: Initiating Celery retry mechanism due to exception.")
        #          # Calculate countdown based on retry number for custom backoff.
        #          countdown = int(self.request.retries * 5) + 5
        #          raise self.retry(exc=e, countdown=countdown)
        #     else:
        #          logger.error(f"{log_prefix}: Task instance not available for manual retry, re-raising.")
        #          raise e
        # except Exception as retry_e:
        #     logger.error(f"{log_prefix}: Error during explicit retry attempt: {retry_e}. Raising original exception.")
        #     raise e
        raise e # Let Celery handle the retry based on `autoretry_for`

    finally:
        # This block executes regardless of whether an exception occurred or not.
        # Its primary purpose is to ensure the final status of the KeywordSearchSession
        # is correctly updated in the database.
        logger.info(f"{log_prefix}: Entering FINALLY block for final status update.")
        final_status = "UNKNOWN" # Default status if logic fails.

        # Determine the final status based on exceptions or reported errors.
        if task_exception:
            # An exception was caught in the main try block.
            logger.warning(f"{log_prefix}: FINALLY: Task exception detected ({type(task_exception).__name__}). Setting final status to FAILED.")
            final_status = "FAILED"
        elif ingestion_errors > 0 or association_errors > 0:
            # The service call completed but reported errors during processing.
            logger.warning(f"{log_prefix}: FINALLY: Service reported errors (Ingest:{ingestion_errors}, Assoc:{association_errors}). Setting final status to FAILED.")
            final_status = "FAILED"
        else:
            # No exceptions occurred, and the service reported no errors.
            logger.info(f"{log_prefix}: FINALLY: Task completed without exceptions or reported errors. Setting final status to COMPLETED.")
            final_status = "COMPLETED"

        # --- Safely update the database record ---
        # Use a separate, new database session for this final update to ensure
        # atomicity and avoid potential issues with the state of the original 'db' session
        # (which might be rolled back or in an error state).
        update_db: Session | None = None
        try:
            logger.info(f"{log_prefix}: FINALLY: Attempting to establish NEW session for final status update.")
            update_db = SessionLocal()

            session_repo = KeywordSearchSessionRepository(update_db)
            # Retrieve the specific session record to update.
            session_to_update = session_repo.get(id=session_id)

            if session_to_update:
                logger.info(f"{log_prefix}: FINALLY: Found session {session_id}. Current status: '{session_to_update.status}'. Attempting update to '{final_status}'.")
                # Update status, completion timestamp, and results count.
                session_to_update.status = final_status
                session_to_update.completed_at = datetime.now(timezone.utc)
                session_to_update.results_count = processed_count # Reflects count from service.
                update_db.add(session_to_update)
                logger.info(f"{log_prefix}: FINALLY: Committing final status update...")
                update_db.commit()
                logger.info(f"{log_prefix}: FINALLY: Final status commit successful. DB status should now be '{final_status}'.")
            else:
                # This scenario is unlikely but possible if the initial record creation failed.
                logger.error(f"{log_prefix}: FINALLY: CRITICAL - KeywordSearchSession record ID {session_id} not found in database for final status update.")

        except Exception as final_upd_err:
            # Log critical errors during the final update but prevent crashing the finally block.
            logger.exception(f"{log_prefix}: FINALLY: CRITICAL - Exception during final status update commit: {final_upd_err}")
            if update_db:
                try:
                    # Attempt to rollback any changes made in the failed update transaction.
                    update_db.rollback()
                    logger.warning(f"{log_prefix}: FINALLY: Rolled back final status update transaction due to error.")
                except Exception as rb_err:
                    logger.error(f"{log_prefix}: FINALLY: Exception during rollback of failed status update: {rb_err}")
        finally:
            # Ensure the database session used for the final update is closed.
            if update_db:
                logger.info(f"{log_prefix}: FINALLY: Closing the DB session used for final status update.")
                try:
                    update_db.close()
                except Exception as close_err:
                     logger.error(f"{log_prefix}: FINALLY: Exception closing final update DB session: {close_err}")

            # Also ensure the original task session ('db') is closed if it was created.
            # Avoid double-closing if 'update_db' somehow ended up being the same instance.
            if db and (update_db is None or db is not update_db):
                 logger.info(f"{log_prefix}: FINALLY: Closing original task DB session.")
                 try:
                     db.close()
                 except Exception as close_err:
                      logger.error(f"{log_prefix}: FINALLY: Exception closing original task DB session: {close_err}")

        logger.info(f"{log_prefix}: ENDING Keyword Discovery Task.")
# --- END OF FILE discovery_tasks.py ---