# --- START OF FILE scholarly_tasks.py ---
"""
backend.tasks.scholarly_tasks
-----------------------------

Defines Celery background tasks for processing scholarly information,
primarily interacting with the OpenAlex API and the application's database.

Tasks include:
- Fetching detailed information for individual works (publications).
- Processing citations and references recursively up to a defined depth.
- Fetching lists of works that cite a given work.
- Creating and managing database records for works, citations, and discovery chains.
- Handling API errors, database concurrency issues (like deadlocks), and ensuring
  robust task execution with retries.
"""

import logging
import time  # For implementing delays in retry logic.
import uuid
import re # For parsing IDs from URLs.
from typing import Set, Optional, List, Dict, Any, Tuple

from sqlalchemy.orm import Session
# Import specific database and ORM exceptions for targeted handling.
from sqlalchemy.exc import IntegrityError, SQLAlchemyError, OperationalError
# Import Celery-specific exceptions for flow control (Ignore) and retries (Retry).
from celery.exceptions import Ignore, Retry

# Import the configured Celery application instance.
from backend.celery_app import celery_app
# Import the database session factory.
from backend.data.database import SessionLocal
# Import external API clients (OpenAlex).
from backend.external import OpenAlexClient, ApiClientError
# Import database models relevant to scholarly data.
from backend.data.models import Work, WorkCitation, DiscoveryChain
# Import repository classes for database interactions.
from backend.data.repositories import WorkRepository
# Import application services used by the tasks.
from backend.services import ScholarlyProcessingService, DiscoveryChainService

# Configuration: Maximum depth for recursive processing of references/citations.
MAX_RECURSION_DEPTH = 1 # Limits processing to direct citations/references only (depth 0 and 1).

# Setup logger for this module.
logger = logging.getLogger(__name__)


# --- Helper Functions ---

def _get_id_from_oa_url(url: Optional[str]) -> Optional[str]:
    """
    Extracts a unique identifier from various scholarly ID URLs.

    Supports URLs from OpenAlex, ORCID, ROR, and DOI. Also handles
    bare OpenAlex IDs (e.g., 'W12345678'). Performs basic validation
    based on expected patterns for each ID type.

    Args:
        url: The URL string or potentially a bare ID string.

    Returns:
        The extracted ID string (e.g., 'W12345678', '0000-0002-1825-0097',
        '01ggx4157', '10.1000/xyz123') if parsing and validation succeed,
        otherwise None.
    """
    if not url or not isinstance(url, str): return None
    try:
        id_part: Optional[str] = None
        # Extract ID based on URL prefix or structure.
        if url.startswith("https://orcid.org/"): match = re.search(r'(\d{4}-\d{4}-\d{4}-\d{3}[0-9X])', url); id_part = match.group(1) if match else None
        elif url.startswith("https://ror.org/"): id_part = url.split('/')[-1]
        elif url.startswith("https://openalex.org/"): id_part = url.split('/')[-1]
        elif url.startswith("https://doi.org/"): id_part = url[len("https://doi.org/"):] # Get part after prefix
        # Check for bare OpenAlex ID format (e.g., W followed by digits)
        elif url and url[0].isalpha() and url[1:].isdigit(): id_part = url
        else: id_part = None # Does not match known patterns

        # Basic format validation for extracted IDs.
        if id_part:
            # OpenAlex ID: Starts with letter, followed by digits.
            is_oa = url.startswith("https://openalex.org/") or (id_part == url and url[0].isalpha() and url[1:].isdigit())
            if is_oa and id_part[0].isalpha() and id_part[1:].isdigit(): return id_part
            # ORCID: Matched the regex pattern.
            if url.startswith("https://orcid.org/") and match: return id_part
            # ROR ID: Starts with '0', has 9 characters total.
            if url.startswith("https://ror.org/") and id_part.startswith('0') and len(id_part) == 9: return id_part
            # DOI: Check if extracted part is non-empty (basic check).
            if url.startswith("https://doi.org/") and id_part: return id_part

    except Exception as e:
        # Log errors during parsing but don't crash the calling function.
        logger.error(f"Error parsing identifier from URL/string '{url}': {e}", exc_info=False)
    # Return None if no valid ID could be extracted and validated.
    return None


def get_work_with_retry(
    work_repo: WorkRepository, openalex_id: str, retries: int = 5, delay: float = 5.0
) -> Optional[Work]:
    """
    Attempts to retrieve a Work record by OpenAlex ID, retrying if not found.

    This addresses potential race conditions where a child task might start
    before the parent task's transaction (which created the Work record)
    is fully committed and visible. It queries the database multiple times
    with increasing delays.

    Args:
        work_repo: An instance of WorkRepository bound to the current DB session.
        openalex_id: The OpenAlex ID of the Work to retrieve.
        retries: The maximum number of retrieval attempts.
        delay: The initial delay (in seconds) between retries, often increased implicitly
               by the calling task's retry mechanism for subsequent task-level retries.

    Returns:
        The retrieved Work object if found within the allowed retries, otherwise None.
    """
    logger.debug(f"Attempting to retrieve Work OA ID {openalex_id} with {retries} retries (delay ~{delay}s).")
    for attempt in range(retries):
        logger.debug(f"get_work_with_retry: Attempt {attempt + 1}/{retries} for OA ID {openalex_id}")
        work = work_repo.get_by_openalex_id(openalex_id=openalex_id)
        if work:
            logger.debug(f"get_work_with_retry: Found Work OA ID {openalex_id} (DB ID: {work.id}) on attempt {attempt + 1}.")
            return work
        # Log a warning and wait before the next attempt.
        wait_time = delay * (attempt + 1) # Simple linear backoff for logging clarity
        logger.warning(
            f"get_work_with_retry: Work OA ID {openalex_id} not found (Attempt {attempt + 1}/{retries}). "
            f"Waiting {wait_time:.1f}s before next attempt..."
        )
        time.sleep(wait_time)
    # If the loop completes without finding the work.
    logger.error(f"get_work_with_retry: Failed to find Work OA ID {openalex_id} after {retries} attempts.")
    return None


# --- Celery Tasks ---

@celery_app.task(
    bind=True,                          # Make 'self' (task instance) available.
    autoretry_for=(ApiClientError,),    # Automatically retry OpenAlex API client errors.
    retry_backoff=True,                 # Use exponential backoff for retries.
    max_retries=5,                      # Limit automatic retries for API errors. Retries for deadlocks are handled manually.
    acks_late=True,                     # Acknowledge task only after completion/failure (for reliability).
    task_reject_on_worker_lost=True     # Requeue task if the worker processing it dies.
)
def process_work_deeply_task(
    self,
    openalex_id: str,                   # The OpenAlex ID of the Work to process in this task.
    primary_work_oa_id: str,            # The OpenAlex ID of the 'parent' work that led to this one.
    relationship_type: str,             # How this work relates to the primary ('citation' or 'reference').
    initiating_doi_ref_id: Optional[int] = None, # Optional DB ID of the initiating DoiReference.
    depth: int = 0,                     # Current recursion depth (0 is the initial work).
    visited_ids: Optional[List[str]] = None, # List of OA IDs already processed in this chain to prevent cycles.
):
    """
    Celery task to fetch, process, and store details for a specific scholarly work
    identified by its OpenAlex ID, including its relationships (citations/references).

    This task is typically called recursively for related works, up to MAX_RECURSION_DEPTH.
    It handles:
    - Preventing cycles using `visited_ids`.
    - Checking recursion depth.
    - Managing database sessions and transactions.
    - Using `DiscoveryChainService` to track the processing flow.
    - Retrieving/creating Work records using `WorkRepository`.
    - Handling potential race conditions using `get_work_with_retry`.
    - Creating `WorkCitation` links between works.
    - Fetching full work details from OpenAlex API.
    - Calling `ScholarlyProcessingService` to process the detailed data.
    - Handling database deadlocks (`OperationalError` with pgcode '40P01') with manual retries.
    - Handling other database errors and API errors gracefully.
    - Enqueuing child tasks for related works if depth allows.

    Args:
        self: The Celery task instance.
        openalex_id: The OpenAlex ID of the work this task instance should process.
        primary_work_oa_id: The OpenAlex ID of the work that cited/referenced this one.
        relationship_type: 'citation' (primary cites this one) or 'reference' (this one cites primary).
        initiating_doi_ref_id: Optional DB ID of the DoiReference that started the chain.
        depth: The current recursion depth.
        visited_ids: A list of OpenAlex IDs already visited in the current processing chain.
    """
    task_id = self.request.id if hasattr(self, 'request') and self.request.id else 'UNKNOWN_TASK_ID'
    # Use a set for efficient 'in' checks for visited IDs.
    visited_set: Set[str] = set(visited_ids) if visited_ids is not None else set()
    log_prefix = f"Task {task_id} (Work OA:{openalex_id}, Depth:{depth}, Rel:{relationship_type}, PrimOA:{primary_work_oa_id})"

    logger.info(f"{log_prefix}: Starting processing.")

    # --- Pre-checks ---
    # Check if this work has already been processed in this chain.
    if openalex_id in visited_set:
        logger.warning(f"{log_prefix}: Skipping, already visited in this chain.")
        # Use Ignore() to stop processing without marking the task as failed.
        raise Ignore()

    # Check if the maximum recursion depth has been exceeded.
    if depth > MAX_RECURSION_DEPTH:
        logger.warning(f"{log_prefix}: Skipping, maximum recursion depth ({MAX_RECURSION_DEPTH}) reached.")
        raise Ignore()

    # Add the current work ID to the set for this task and potential children.
    visited_set.add(openalex_id)

    # --- Initialization ---
    db: Session | None = None               # Database session for this task.
    root_chain: Optional[DiscoveryChain] = None # Discovery chain tracker for this task.
    current_work_db: Optional[Work] = None  # DB record for the work being processed (openalex_id).
    primary_work_db: Optional[Work] = None  # DB record for the parent work (primary_work_oa_id).
    discovery_chain_service: DiscoveryChainService | None = None # Service instance.

    try:
        # --- Setup Database Session and Services ---
        db = SessionLocal()
        logger.debug(f"{log_prefix}: Database session created.")
        # Instantiate services and repositories within the session context.
        openalex_client = OpenAlexClient()
        work_repo = WorkRepository(db)
        scholarly_processor = ScholarlyProcessingService()
        discovery_chain_service = DiscoveryChainService()

        # --- Track Progress with DiscoveryChain ---
        chain_params = {
            "task_name": self.name, "openalex_id": openalex_id, "primary_oa_id": primary_work_oa_id,
            "type": relationship_type, "depth": depth, "initiating_doi_ref_id": initiating_doi_ref_id,
        }
        root_chain = discovery_chain_service.create_root_chain(db, "CELERY_LINKED_WORK_PROCESS", chain_params)
        discovery_chain_service.start_chain(db, root_chain)
        logger.info(f"{log_prefix}: Discovery chain {root_chain.id} created and started.")

        # --- Get or Create the Database Record for the Current Work ---
        logger.debug(f"{log_prefix}: Retrieving/creating database record for current work...")
        # Use repository method that handles potential race conditions during creation.
        current_work_db = work_repo.get_or_create_by_openalex_id(
            openalex_id=openalex_id,
            obj_in_data={"openalex_id": openalex_id} # Provide minimal data for creation if needed.
        )
        # The repo method ensures the object has an ID after returning.
        if current_work_db.id is None:
             # This case should ideally not happen if get_or_create works correctly.
             error_msg = f"Critical: Work ID is None after get_or_create for OA ID {openalex_id}"
             logger.error(f"{log_prefix}: {error_msg}")
             discovery_chain_service.fail_chain(db, root_chain, error_msg)
             db.commit()
             raise RuntimeError(error_msg) # Fail the task deterministically.
        logger.debug(f"{log_prefix}: Current work DB record obtained/created (ID: {current_work_db.id}).")
        # Associate the work record with the discovery chain.
        discovery_chain_service.associate_entity(db, root_chain, current_work_db, is_direct=True)

        # --- Retrieve the Database Record for the Primary Work ---
        logger.debug(f"{log_prefix}: Retrieving primary work DB record ({primary_work_oa_id}) with retry...")
        # Use the helper function to handle potential delays in visibility.
        primary_work_db = get_work_with_retry(work_repo, primary_work_oa_id, retries=5, delay=5.0)
        if not primary_work_db:
            # If the primary work cannot be found after retries, the task cannot proceed.
            error_msg = f"Primary work {primary_work_oa_id} not found in DB after retries."
            logger.error(f"{log_prefix}: {error_msg}")
            discovery_chain_service.fail_chain(db, root_chain, error_msg)
            db.commit() # Commit the failure status of the chain.
            raise Ignore() # Ignore the task; retrying won't help if the primary is missing.
        logger.debug(f"{log_prefix}: Primary work DB record found (ID: {primary_work_db.id}).")
        discovery_chain_service.associate_entity(db, root_chain, primary_work_db, is_direct=False)

        # --- Create Citation Link if Applicable ---
        # Ensure both work records have database IDs before creating the relationship.
        if current_work_db.id is not None and primary_work_db.id is not None:
            citing_id, cited_id = None, None
            rel_desc = ""
            # Determine which work is citing and which is cited based on relationship_type.
            if relationship_type == "citation":
                # 'citation' means the primary work cited the current work.
                citing_id, cited_id = primary_work_db.id, current_work_db.id
                rel_desc = f"Primary(ID:{citing_id}) cites Current(ID:{cited_id})"
            elif relationship_type == "reference":
                # 'reference' means the current work cited the primary work.
                citing_id, cited_id = current_work_db.id, primary_work_db.id
                rel_desc = f"Current(ID:{citing_id}) cites Primary(ID:{cited_id})"
            else:
                logger.warning(f"{log_prefix}: Invalid relationship_type '{relationship_type}'. Cannot create citation link.")

            # If IDs were determined, attempt to create the WorkCitation record.
            if citing_id is not None and cited_id is not None:
                 logger.debug(f"{log_prefix}: Checking/creating citation link: {rel_desc}")
                 try:
                     # Check if the citation relationship already exists.
                     existing_citation = db.query(WorkCitation).filter_by(citing_work_id=citing_id, cited_work_id=cited_id).first()
                     if not existing_citation:
                         # Create and add the new citation record.
                         citation_input_data = {"citing_work_id": citing_id, "cited_work_id": cited_id}
                         citation_db = WorkCitation(**citation_input_data)
                         db.add(citation_db)
                         # Flush to assign an ID to citation_db, required for association.
                         db.flush()
                         logger.info(f"{log_prefix}: Created WorkCitation link: {rel_desc} (ID: {citation_db.id})")
                         discovery_chain_service.associate_entity(db, root_chain, citation_db, is_direct=False)
                     else:
                         logger.debug(f"{log_prefix}: WorkCitation link already exists: {rel_desc}")
                 except IntegrityError as ie:
                     # Catch potential unique constraint violations if created concurrently.
                     logger.warning(f"{log_prefix}: IntegrityError creating WorkCitation ({rel_desc}), likely created concurrently. Rolling back flush and proceeding. Details: {ie}")
                     db.rollback() # Rollback the flush attempt.
                 except Exception as e_citation:
                     # Log other errors during citation creation but proceed with work processing.
                     logger.error(f"{log_prefix}: Error creating/flushing WorkCitation ({rel_desc}): {e_citation}", exc_info=True)
                     db.rollback() # Rollback potential partial changes.
        else:
            # This should not happen if previous checks passed.
            logger.error(f"{log_prefix}: Missing DB ID for current ({current_work_db.id}) or primary ({primary_work_db.id}) work. Cannot create citation link.")

        # --- Fetch and Process Full Work Details from OpenAlex ---
        logger.debug(f"{log_prefix}: Fetching full work details from OpenAlex API...")
        full_work_data = None
        try:
            # Call the OpenAlex client to get detailed work data.
            full_work_data = openalex_client.get_work_details(openalex_id)
            if full_work_data:
                 logger.debug(f"{log_prefix}: Successfully fetched full details from OpenAlex.")
            else:
                 logger.warning(f"{log_prefix}: No detailed data returned from OpenAlex API.")
        except ApiClientError as api_details_err:
            # Let Celery's autoretry handle API client errors.
            logger.warning(f"{log_prefix}: API error fetching details: {api_details_err}. Task will retry.")
            raise api_details_err
        except Exception as api_err:
             # Catch other unexpected errors during API call.
             logger.error(f"{log_prefix}: Unexpected error fetching details from OpenAlex: {api_err}", exc_info=True)
             # Raise to allow potential Celery retry based on general Exception handling, or fail.
             raise api_err

        # If no data was fetched (even after potential retries), stop processing this work.
        if not full_work_data:
            logger.warning(f"{log_prefix}: Could not fetch full details for work. Stopping further processing for this work.")
            discovery_chain_service.complete_chain(db, root_chain, status_message="Completed - No detailed data from API")
            db.commit()
            raise Ignore() # Stop processing this task instance.

        # --- Process the Fetched Data using ScholarlyProcessingService ---
        logger.debug(f"{log_prefix}: Calling scholarly_processor.process_openalex_work_data...")
        try:
            # Pass the DB session, the existing Work DB record, the fetched API data, and the parent chain.
            # The service will update the work_db object with details and handle related entities.
            referenced_oa_ids, _, cited_by_url_for_tasks = scholarly_processor.process_openalex_work_data(
                db=db,
                work_db=current_work_db,    # Pass the existing DB object to be updated.
                work_api_data=full_work_data,
                parent_chain=root_chain     # Pass the chain for detailed tracking within the service.
            )
            logger.debug(f"{log_prefix}: scholarly_processor.process_openalex_work_data completed.")
        except OperationalError as op_err:
             # Specifically check for deadlocks (PostgreSQL error code '40P01').
             pgcode = getattr(op_err.orig, 'pgcode', None)
             if pgcode == '40P01':
                  logger.warning(f"{log_prefix}: DEADLOCK detected during scholarly processing. Raising OperationalError for Celery retry.")
                  # Re-raise the OperationalError; manual retry logic is below in the main except block.
                  raise op_err
             else:
                  # Handle other database operational errors.
                  logger.error(f"{log_prefix}: Database OperationalError during scholarly processing (Code: {pgcode}): {op_err}", exc_info=True)
                  discovery_chain_service.fail_chain(db, root_chain, f"DB OperationalError: {str(op_err)[:150]}")
                  db.commit()
                  raise Ignore() # Do not retry non-deadlock operational errors automatically.
        except Exception as scholarly_err:
             # Catch other unexpected errors during the processing service call.
             logger.error(f"{log_prefix}: EXCEPTION during scholarly processing: {scholarly_err}", exc_info=True)
             # Fail the chain and ignore the task for most processing errors.
             error_msg = f"Scholarly processing error: {str(scholarly_err)[:150]}"
             discovery_chain_service.fail_chain(db, root_chain, error_msg)
             db.commit()
             raise Ignore()

        logger.info(f"{log_prefix}: Scholarly data processed. Found {len(referenced_oa_ids)} referenced works to potentially enqueue.")

        # --- Commit Main Transaction and Finalize Chain ---
        # Commit all changes made so far (work creation/update, citation link, associated entities via service).
        discovery_chain_service.complete_chain(db, root_chain)
        db.commit()
        logger.info(f"{log_prefix}: Main transaction committed. Discovery chain {root_chain.id} completed.")

        # --- Enqueue Child Tasks for Related Works ---
        next_depth = depth + 1
        # Pass the updated list of visited IDs to children.
        next_visited_list = list(visited_set)
        if next_depth <= MAX_RECURSION_DEPTH:
            logger.debug(f"{log_prefix}: Enqueuing child tasks for referenced works at depth {next_depth}")
            # Enqueue tasks for works referenced by the current work.
            for ref_oa_id in referenced_oa_ids:
                if ref_oa_id not in visited_set: # Avoid re-enqueuing visited works.
                    logger.debug(f"{log_prefix}: Enqueueing child task for referenced OA ID: {ref_oa_id}")
                    # Note: The 'primary' work for this child task is the *current* work.
                    # The relationship is 'citation' because the current work cited the ref_oa_id.
                    process_work_deeply_task.delay(
                        openalex_id=ref_oa_id,
                        primary_work_oa_id=openalex_id, # Current work is the primary for the child.
                        relationship_type="citation",   # Current work CITED ref_oa_id.
                        initiating_doi_ref_id=initiating_doi_ref_id,
                        depth=next_depth,
                        visited_ids=next_visited_list,
                    )
            # TODO: Consider if/how to handle cited_by works here or in a separate task pattern.
            # If `cited_by_url_for_tasks` is returned by the service, it could be used here.
            # Example:
            # if cited_by_url_for_tasks:
            #     logger.debug(f"{log_prefix}: Enqueueing task to process citing works list from {cited_by_url_for_tasks}")
            #     process_citing_works_list_task.delay(
            #         primary_work_oa_id=openalex_id,
            #         cited_by_api_url=cited_by_url_for_tasks,
            #         initiating_doi_ref_id=initiating_doi_ref_id
            #     )

        else:
            logger.info(f"{log_prefix}: Maximum depth reached, not enqueuing further child tasks.")

        logger.info(f"{log_prefix}: Task completed successfully.")

    # --- Exception Handling Block ---
    except Ignore:
        # Task was intentionally stopped (e.g., already visited, max depth, primary missing).
        logger.info(f"{log_prefix}: Task processing ignored.")
        # Chain status should have been set appropriately before Ignore was raised.
    except ApiClientError as e:
        # Handled by Celery autoretry based on task decorator.
        # Logged here for context, but re-raised implicitly by autoretry.
        logger.error(f"{log_prefix}: API Client Error occurred: {e}. Autoretry mechanism active.")
        # Attempt to mark chain as FAILED in case retries are exhausted.
        if db and root_chain and discovery_chain_service:
             try:
                 if not db.is_active: db = SessionLocal() # Ensure session is active for update.
                 chain_to_fail = discovery_chain_service.get_by_uuid(db, root_chain.id)
                 if chain_to_fail and chain_to_fail.status not in ['COMPLETED', 'FAILED']:
                     discovery_chain_service.fail_chain(db, chain_to_fail, f"API Error (final attempt?): {str(e)[:150]}")
                     db.commit()
             except Exception as e_fail: logger.error(f"{log_prefix}: Error marking chain failed after API error: {e_fail}", exc_info=False); db.rollback()
        # Autoretry decorator handles raising the retry exception.
    except OperationalError as e:
        # Catch database operational errors, specifically deadlocks.
        pgcode = getattr(e.orig, 'pgcode', None)
        if pgcode == '40P01':
            # Handle deadlock: Manually trigger a retry with a backoff.
            retry_count = self.request.retries
            # Increase countdown significantly for deadlocks.
            countdown = int((retry_count + 1) * 10) + 10
            logger.warning(f"{log_prefix}: DEADLOCK detected (Retry {retry_count + 1}/{self.max_retries}). Retrying task in {countdown}s.")
            # Manually raise the Retry exception.
            raise self.retry(exc=e, countdown=countdown)
        else:
            # Handle other operational errors (e.g., connection issues not covered by retry).
            logger.error(f"{log_prefix}: DATABASE OperationalError (non-deadlock, Code: {pgcode}): {e}", exc_info=True)
            if db and root_chain and discovery_chain_service:
                 try:
                     if not db.is_active: db = SessionLocal()
                     chain_to_fail = discovery_chain_service.get_by_uuid(db, root_chain.id)
                     if chain_to_fail and chain_to_fail.status not in ['COMPLETED', 'FAILED']:
                         discovery_chain_service.fail_chain(db, chain_to_fail, f"DB OperationalError: {str(e)[:150]}")
                         db.commit()
                 except Exception as e_fail: logger.error(f"{log_prefix}: Error marking chain failed after DB OperationalError: {e_fail}", exc_info=False); db.rollback()
            raise Ignore() # Do not retry other operational errors automatically.
    except (SQLAlchemyError, ValueError, RuntimeError) as e:
        # Catch other specific database, value, or runtime errors.
        logger.error(f"{log_prefix}: DATABASE/VALUE/RUNTIME Error: {e}", exc_info=True)
        if db and root_chain and discovery_chain_service:
             try:
                 if not db.is_active: db = SessionLocal()
                 chain_to_fail = discovery_chain_service.get_by_uuid(db, root_chain.id)
                 if chain_to_fail and chain_to_fail.status not in ['COMPLETED', 'FAILED']:
                     discovery_chain_service.fail_chain(db, chain_to_fail, f"DB/Value/Runtime Error: {str(e)[:150]}")
                     db.commit()
             except Exception as e_fail: logger.error(f"{log_prefix}: Error marking chain failed after DB/Value/Runtime error: {e_fail}", exc_info=False); db.rollback()
        logger.warning(f"{log_prefix}: Task will be ignored due to encountered DB/Value/Runtime error.")
        raise Ignore() # Stop processing for these types of errors.
    except Exception as e:
        # Catch any other unexpected errors.
        logger.exception(f"{log_prefix}: Unexpected critical error: {e}")
        if db and root_chain and discovery_chain_service:
              try:
                 if not db.is_active: db = SessionLocal()
                 chain_to_fail = discovery_chain_service.get_by_uuid(db, root_chain.id)
                 if chain_to_fail and chain_to_fail.status not in ['COMPLETED', 'FAILED']:
                     discovery_chain_service.fail_chain(db, chain_to_fail, f"Unexpected Error: {str(e)[:150]}")
                     db.commit()
              except Exception as e_fail: logger.error(f"{log_prefix}: Error marking chain failed after critical error: {e_fail}", exc_info=False); db.rollback()
        # Attempt a generic retry for unexpected errors.
        try:
             raise self.retry(exc=e, countdown=int(self.request.retries * 5) + 5)
        except Exception as retry_err:
             logger.error(f"{log_prefix}: Failed to initiate retry after unexpected error: {retry_err}. Ignoring task.")
             raise Ignore()
    finally:
        # --- Cleanup ---
        # Ensure the database session is always closed.
        if db:
            try:
                db.close()
                logger.debug(f"{log_prefix}: Database session closed.")
            except Exception as close_err:
                 logger.error(f"{log_prefix}: Error closing database session: {close_err}")


@celery_app.task(
    bind=True,
    autoretry_for=(ApiClientError,),    # Retry on API client errors.
    retry_backoff=True,
    max_retries=5,                      # Increased retries for API/deadlock potential.
    acks_late=True,
    task_reject_on_worker_lost=True,
)
def process_citing_works_list_task(
    self,
    primary_work_oa_id: str,            # The OpenAlex ID of the work *being cited*.
    cited_by_api_url: str,              # The OpenAlex API URL to fetch the list of citing works.
    initiating_doi_ref_id: Optional[int] = None # Optional DB ID of the initiating DoiReference.
):
    """
    Celery task to fetch and process a list of works that cite a given primary work.

    This task retrieves a paginated list of citing works from the OpenAlex
    'cited_by_api_url'. For each citing work found, it:
    - Creates/retrieves the Work record in the database.
    - Creates the corresponding WorkCitation record (citing_work -> primary_work).
    - Uses database savepoints (nested transactions) to handle errors for individual
      citing works without necessarily failing the entire task.
    - Manages discovery chains for tracking.
    - Includes retry logic for API errors and database deadlocks.

    Args:
        self: The Celery task instance.
        primary_work_oa_id: The OpenAlex ID of the work whose citing works are being processed.
        cited_by_api_url: The specific OpenAlex API endpoint URL to fetch the citing works list.
        initiating_doi_ref_id: Optional DB ID of the DoiReference that started the chain.
    """
    task_id = self.request.id if hasattr(self, 'request') and self.request.id else 'UNKNOWN_TASK_ID'
    log_prefix = f"Task {task_id} (CitedBy List for PrimOA:{primary_work_oa_id})"
    logger.info(f"{log_prefix}: Starting processing of citing works list from URL: {cited_by_api_url}")

    # --- Initialization ---
    db: Session | None = None
    root_chain: Optional[DiscoveryChain] = None
    primary_work_db: Optional[Work] = None
    discovery_chain_service: DiscoveryChainService | None = None

    try:
        # --- Setup ---
        db = SessionLocal()
        logger.debug(f"{log_prefix}: Database session created.")
        openalex_client = OpenAlexClient()
        work_repo = WorkRepository(db)
        discovery_chain_service = DiscoveryChainService()

        # --- Create Root Discovery Chain ---
        chain_params = {
            "task_name": self.name, "primary_oa_id": primary_work_oa_id,
            "cited_by_url": cited_by_api_url, "initiating_doi_ref_id": initiating_doi_ref_id
        }
        root_chain = discovery_chain_service.create_root_chain(db, "CELERY_CITING_WORKS_LIST", chain_params)
        discovery_chain_service.start_chain(db, root_chain)
        logger.info(f"{log_prefix}: Discovery chain {root_chain.id} created and started.")

        # --- Get Primary Work (the one being cited) ---
        logger.debug(f"{log_prefix}: Retrieving primary work DB record ({primary_work_oa_id}) with retry...")
        primary_work_db = get_work_with_retry(work_repo, primary_work_oa_id, retries=5, delay=5.0)
        if not primary_work_db:
            error_msg = f"Primary work {primary_work_oa_id} (being cited) not found after retries."
            logger.error(f"{log_prefix}: {error_msg}")
            discovery_chain_service.fail_chain(db, root_chain, error_msg)
            db.commit()
            raise Ignore() # Cannot proceed without the primary work record.
        logger.debug(f"{log_prefix}: Primary work DB record found (ID: {primary_work_db.id}).")
        discovery_chain_service.associate_entity(db, root_chain, primary_work_db, is_direct=False)

        # --- Fetch Citing Works List from OpenAlex API ---
        logger.debug(f"{log_prefix}: Fetching citing works list from API...")
        citing_works_data: Optional[List[Dict[str, Any]]] = None
        try:
            # This likely involves pagination handling within the client.
            citing_works_data = openalex_client.get_citing_works(citing_works_url=cited_by_api_url)
            logger.debug(f"{log_prefix}: API call for citing works completed. Received {len(citing_works_data) if citing_works_data is not None else 'None'} items.")
        except ApiClientError as api_citing_err:
            logger.warning(f"{log_prefix}: API error fetching citing works list: {api_citing_err}. Task will retry.")
            raise api_citing_err # Let Celery autoretry handle this.
        except Exception as api_err:
             logger.error(f"{log_prefix}: Unexpected error fetching citing works from OpenAlex: {api_err}", exc_info=True)
             raise api_err # Raise for potential generic retry or failure.

        # Handle case where API call succeeded but returned None (e.g., client internal error).
        if citing_works_data is None:
            error_msg = "API client returned None fetching citing works list."
            logger.error(f"{log_prefix}: {error_msg}")
            discovery_chain_service.fail_chain(db, root_chain, error_msg)
            db.commit()
            # Use RuntimeError to indicate a failure state that shouldn't be retried by API handler.
            raise RuntimeError(f"API failed to return citing works data from {cited_by_api_url}")

        # Handle case where API returned an empty list.
        if not citing_works_data:
            logger.info(f"{log_prefix}: No citing works found for primary work {primary_work_oa_id}.")
            discovery_chain_service.complete_chain(db, root_chain, status_message="Completed - No citing works found")
            db.commit()
            return # Task is successfully completed.

        # --- Process Each Citing Work Item ---
        logger.info(f"{log_prefix}: Found {len(citing_works_data)} citing works. Processing each...")
        processed_count = 0
        error_count = 0

        for citing_work_item in citing_works_data:
            # Extract key identifiers from the citing work data.
            citing_work_oa_id = _get_id_from_oa_url(citing_work_item.get("id"))
            citing_work_doi = _get_id_from_oa_url(citing_work_item.get("doi"))

            # Skip if essential ID is missing.
            if not citing_work_oa_id:
                logger.warning(f"{log_prefix}: Skipping citing item due to missing/invalid OpenAlex ID: {citing_work_item.get('id')}")
                error_count += 1 # Count as an error for reporting.
                continue

            logger.debug(f"{log_prefix}: Processing citing work OA ID: {citing_work_oa_id}")
            # Use a database savepoint for processing each citing work individually.
            # This allows committing successful items even if others fail.
            nested_transaction = db.begin_nested()
            citing_work_chain: Optional[DiscoveryChain] = None # Chain for this specific citing work.
            wc_db: Optional[Work] = None # DB record for the citing work.

            try:
                 # Create a child chain for this specific citing work.
                 citing_work_chain = discovery_chain_service.create_child_chain(
                     db, root_chain, "REL_CITING_WORK_FROM_LIST", {"citing_oa_id": citing_work_oa_id}
                 )
                 # Prepare minimal data for creating the citing work record if it doesn't exist.
                 wc_input_data: Dict[str, Any] = {"openalex_id": citing_work_oa_id}
                 if citing_work_doi: wc_input_data["doi"] = citing_work_doi
                 if citing_work_item.get("title"): wc_input_data["title"] = citing_work_item.get("title")[:1024] # Truncate title if needed
                 if citing_work_item.get("publication_year"): wc_input_data["publication_year"] = citing_work_item.get("publication_year")

                 logger.debug(f"{log_prefix}: Getting/creating citing work OA ID {citing_work_oa_id}...")
                 # Get or create the citing work record.
                 wc_db = work_repo.get_or_create_by_openalex_id(openalex_id=citing_work_oa_id, obj_in_data=wc_input_data)
                 if wc_db.id is None:
                      raise RuntimeError(f"Citing Work ID is None after get_or_create for OA ID {citing_work_oa_id}")
                 logger.debug(f"{log_prefix}: Got/created citing work DB record (ID: {wc_db.id}).")
                 discovery_chain_service.associate_entity(db, citing_work_chain, wc_db, is_direct=True)

                 # Create the citation link (Citing Work -> Primary Work).
                 if wc_db.id is not None and primary_work_db.id is not None:
                     citing_id, cited_id = wc_db.id, primary_work_db.id # Wc cites W1
                     rel_desc = f"CitingWork(ID:{citing_id}) cites PrimaryWork(ID:{cited_id})"
                     logger.debug(f"{log_prefix}: Checking/creating citation link: {rel_desc}")
                     try:
                         existing_citation = db.query(WorkCitation).filter_by(citing_work_id=citing_id, cited_work_id=cited_id).first()
                         if not existing_citation:
                             citation_db = WorkCitation(citing_work_id=citing_id, cited_work_id=cited_id)
                             db.add(citation_db)
                             db.flush() # Flush to get ID for association.
                             logger.info(f"{log_prefix}: Created WorkCitation link: {rel_desc} (ID: {citation_db.id})")
                             discovery_chain_service.associate_entity(db, citing_work_chain, citation_db, is_direct=False)
                         else:
                             logger.debug(f"{log_prefix}: WorkCitation link already exists: {rel_desc}")
                     except IntegrityError as ie_cite:
                          logger.warning(f"{log_prefix}: IntegrityError creating WorkCitation ({rel_desc}), likely created concurrently. Rolling back flush. Details: {ie_cite}")
                          db.rollback() # Rollback the specific flush.
                     except Exception as e_citation:
                          logger.error(f"{log_prefix}: Error creating/flushing WorkCitation ({rel_desc}): {e_citation}", exc_info=True)
                          db.rollback() # Rollback the specific flush.

                 # Mark the child chain as complete and commit the savepoint.
                 discovery_chain_service.complete_chain(db, citing_work_chain)
                 nested_transaction.commit() # Commit changes for *this* citing work.
                 processed_count += 1
                 logger.debug(f"{log_prefix}: Successfully processed and committed citing work {citing_work_oa_id}")

            except Exception as e_wc:
                 # An error occurred processing this specific citing work.
                 error_count += 1
                 logger.error(f"{log_prefix}: Failed processing citing work OA ID {citing_work_oa_id}: {e_wc}", exc_info=True)
                 # Rollback the savepoint for the failed item.
                 try:
                     logger.warning(f"{log_prefix}: Rolling back savepoint for failed citing work {citing_work_oa_id}.")
                     nested_transaction.rollback()
                 except Exception as rb_err:
                     # Log error during rollback itself, but continue.
                     logger.error(f"{log_prefix}: Error rolling back savepoint for failed citing work {citing_work_oa_id}: {rb_err}")

                 # Attempt to mark the specific child chain as FAILED in a separate session/transaction.
                 if citing_work_chain:
                      try:
                           # Use a temporary session to avoid interference with main session state.
                           temp_db_fail = SessionLocal()
                           try:
                               # Re-fetch the chain in the new session.
                               chain_to_fail = discovery_chain_service.get_by_uuid(temp_db_fail, citing_work_chain.id)
                               if chain_to_fail:
                                    discovery_chain_service.fail_chain(temp_db_fail, chain_to_fail, error_message=f"Savepoint failed: {str(e_wc)[:100]}")
                                    temp_db_fail.commit()
                                    logger.info(f"{log_prefix}: Marked child chain {citing_work_chain.id} as FAILED.")
                               else:
                                    logger.error(f"{log_prefix}: Could not find child chain {citing_work_chain.id} in temp session to mark as FAILED.")
                           except Exception as fail_e:
                                logger.error(f"{log_prefix}: Failed to mark citing work chain {citing_work_chain.id} as FAILED: {fail_e}", exc_info=False)
                                temp_db_fail.rollback()
                           finally:
                                temp_db_fail.close()
                      except Exception as session_err:
                           logger.error(f"{log_prefix}: Failed to create temp session for child chain failure update: {session_err}")

                 # Re-raise specific exceptions that should trigger a task retry (like deadlocks).
                 if isinstance(e_wc, OperationalError) and getattr(e_wc.orig, 'pgcode', None) == '40P01':
                      logger.warning(f"{log_prefix}: Deadlock detected within savepoint for {citing_work_oa_id}. Re-raising for task retry.")
                      # Re-raise the deadlock error to be caught by the main task exception handler.
                      raise e_wc
                 # Otherwise, the loop continues to the next citing work.

        # --- Finalize Root Chain Status ---
        # After processing all items, set the final status of the root chain based on errors.
        if error_count > 0:
            final_msg = f"Completed with {error_count} errors out of {len(citing_works_data)} citing works processed."
            logger.warning(f"{log_prefix}: {final_msg}")
            discovery_chain_service.fail_chain(db, root_chain, final_msg)
        else:
            final_msg = f"Successfully processed all {processed_count} citing works."
            logger.info(f"{log_prefix}: {final_msg}")
            discovery_chain_service.complete_chain(db, root_chain, final_msg)

        # Commit the main transaction (including successful savepoints and final root chain status).
        db.commit()
        logger.info(f"{log_prefix}: Main transaction committed. Processed: {processed_count}, Errors: {error_count}.")

    # --- Exception Handling for the Entire Task ---
    except Ignore:
         logger.info(f"{log_prefix}: Task processing ignored (e.g., primary work missing).")
         # Attempt to mark chain as COMPLETED if it was left PROCESSING during an Ignore scenario.
         if db and root_chain and discovery_chain_service:
             try:
                 if not db.is_active: db = SessionLocal()
                 chain_to_update = discovery_chain_service.get_by_uuid(db, root_chain.id)
                 if chain_to_update and chain_to_update.status == 'PROCESSING':
                     logger.info(f"{log_prefix}: Marking root chain {chain_to_update.id} as COMPLETED (due to Ignore).")
                     discovery_chain_service.complete_chain(db, chain_to_update, status_message="Ignored")
                     db.commit()
             except Exception as e_complete: logger.error(f"{log_prefix}: Error updating chain status after Ignore: {e_complete}", exc_info=False); db.rollback()
    except (ApiClientError, RuntimeError) as e:
         # Handle API errors (caught by autoretry) or RuntimeErrors (e.g., failed API fetch).
         logger.error(f"{log_prefix}: API Client or Runtime Error during task execution: {e}", exc_info=isinstance(e, RuntimeError))
         if db and root_chain and discovery_chain_service:
             try:
                 if not db.is_active: db = SessionLocal()
                 chain_to_fail = discovery_chain_service.get_by_uuid(db, root_chain.id)
                 if chain_to_fail and chain_to_fail.status not in ['COMPLETED', 'FAILED']:
                     discovery_chain_service.fail_chain(db, chain_to_fail, f"API/Runtime Error: {str(e)[:150]}")
                     db.commit()
             except Exception as e_fail: logger.error(f"{log_prefix}: Error marking chain failed after API/Runtime error: {e_fail}", exc_info=False); db.rollback()
         # Re-raise API errors for autoretry; treat RuntimeErrors as non-retryable here.
         if isinstance(e, ApiClientError):
             logger.info(f"{log_prefix}: Raising ApiClientError for Celery autoretry.")
             raise e # Let autoretry handle it.
         else: # For RuntimeError
              logger.warning(f"{log_prefix}: Encountered RuntimeError, task will be ignored.")
              raise Ignore()
    except OperationalError as e:
        # Catch deadlocks or other operational errors occurring outside the item loop.
        pgcode = getattr(e.orig, 'pgcode', None)
        if pgcode == '40P01':
            # Handle deadlock: Manually trigger a retry.
            retry_count = self.request.retries
            countdown = int((retry_count + 1) * 10) + 10
            logger.warning(f"{log_prefix}: DEADLOCK detected (Retry {retry_count + 1}/{self.max_retries}). Retrying task in {countdown}s.")
            raise self.retry(exc=e, countdown=countdown)
        else:
            # Handle other operational errors.
            logger.error(f"{log_prefix}: DATABASE OperationalError (non-deadlock, Code: {pgcode}): {e}", exc_info=True)
            if db and root_chain and discovery_chain_service:
                 try:
                     if not db.is_active: db = SessionLocal()
                     chain_to_fail = discovery_chain_service.get_by_uuid(db, root_chain.id)
                     if chain_to_fail and chain_to_fail.status not in ['COMPLETED', 'FAILED']:
                         discovery_chain_service.fail_chain(db, chain_to_fail, f"DB OperationalError: {str(e)[:150]}")
                         db.commit()
                 except Exception as e_fail: logger.error(f"{log_prefix}: Error marking chain failed after DB OperationalError: {e_fail}", exc_info=False); db.rollback()
            raise Ignore() # Do not retry other operational errors.
    except (SQLAlchemyError, ValueError) as e:
        # Catch other specific database or value errors.
        logger.error(f"{log_prefix}: DATABASE/VALUE Error: {e}", exc_info=True)
        if db and root_chain and discovery_chain_service:
             try:
                 if not db.is_active: db = SessionLocal()
                 chain_to_fail = discovery_chain_service.get_by_uuid(db, root_chain.id)
                 if chain_to_fail and chain_to_fail.status not in ['COMPLETED', 'FAILED']:
                     discovery_chain_service.fail_chain(db, chain_to_fail, f"DB/Value Error: {str(e)[:150]}")
                     db.commit()
             except Exception as e_fail: logger.error(f"{log_prefix}: Error marking chain failed after DB/Value error: {e_fail}", exc_info=False); db.rollback()
        logger.warning(f"{log_prefix}: Task will be ignored due to encountered DB/Value error.")
        raise Ignore()
    except Exception as e:
         # Catch any other unexpected errors.
         logger.exception(f"{log_prefix}: Unexpected critical error: {e}")
         if db and root_chain and discovery_chain_service:
              try:
                 if not db.is_active: db = SessionLocal()
                 chain_to_fail = discovery_chain_service.get_by_uuid(db, root_chain.id)
                 if chain_to_fail and chain_to_fail.status not in ['COMPLETED', 'FAILED']:
                     discovery_chain_service.fail_chain(db, chain_to_fail, f"Unexpected Error: {str(e)[:150]}")
                     db.commit()
              except Exception as e_fail: logger.error(f"{log_prefix}: Error marking chain failed after critical error: {e_fail}", exc_info=False); db.rollback()
         # Attempt a generic retry.
         try:
             raise self.retry(exc=e, countdown=int(self.request.retries * 5) + 5)
         except Exception as retry_err:
              logger.error(f"{log_prefix}: Failed to initiate retry after unexpected error: {retry_err}. Ignoring task.")
              raise Ignore()
    finally:
        # --- Cleanup ---
        # Ensure the database session is always closed.
        if db:
            try:
                db.close()
                logger.debug(f"{log_prefix}: Database session closed.")
            except Exception as close_err:
                 logger.error(f"{log_prefix}: Error closing database session: {close_err}")
# --- END OF FILE scholarly_tasks.py ---