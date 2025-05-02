"""
backend.services.keyword_discovery_service
------------------------------------------
Handles the discovery of software repositories based on keyword searches
using the GitHub API and initiates their ingestion into the system.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Tuple, Optional, List # Added List

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from backend.data.models import KeywordSearchSession, Repository
# Use SessionLocal for creating isolated sessions for individual repository ingestions
from backend.data.database import SessionLocal
from backend.data.repositories import (
    KeywordSearchSessionRepository,
    KeywordRepositoryAssociationRepository,
    RepositoryRepository,
)
from backend.external import GitHubClient, ApiClientError
# Import IngestionService for dependency injection and type hinting
from backend.services.ingestion_service import IngestionService
from .base_service import BaseService

logger = logging.getLogger(__name__)

class KeywordDiscoveryService(BaseService):
    """
    Service responsible for discovering repositories via keyword search and managing the process.

    Coordinates the workflow:
    1. Updates the status of a `KeywordSearchSession`.
    2. Performs a repository search on GitHub using provided keywords.
    3. Iterates through search results.
    4. For each result, checks if the repository already exists locally.
    5. If the repository is new, initiates the ingestion process using `IngestionService`
       within an isolated database session to prevent a single ingestion failure
       from halting the entire keyword search.
    6. Creates an association (`KeywordRepositoryAssociation`) between the search session
       and the discovered/ingested repository.
    7. Tracks counts of processed repositories, ingestion errors, and association errors.
    """

    def __init__(self, github_client: GitHubClient, ingestion_service: IngestionService):
        """
        Initializes the KeywordDiscoveryService.

        Args:
            github_client: An instance of the GitHub API client.
            ingestion_service: An instance of the IngestionService to handle
                               individual repository ingestion.
        """
        super().__init__()
        self.github_client = github_client
        # Store the IngestionService instance provided by the caller (e.g., Celery task)
        self.ingestion_service = ingestion_service

    def discover_and_ingest_by_keywords(
        self, db: Session, session_id: int, keywords: str, max_repos_to_process: int = 1000
    ) -> Tuple[int, int, int]:
        """
        Executes the keyword discovery and ingestion process for a given search session.

        Uses the provided database session (`db`) for managing the `KeywordSearchSession`
        status and `KeywordRepositoryAssociation` records. Individual repository ingestions
        are handled in separate, isolated sessions created via `SessionLocal`.

        Args:
            db: The primary database session managed by the caller (e.g., Celery task).
            session_id: The ID of the `KeywordSearchSession` record to process.
            keywords: The keyword string to use for the GitHub repository search.
            max_repos_to_process: The maximum number of search results to attempt processing.

        Returns:
            A tuple containing:
            - processed_count: Number of repositories successfully processed and associated.
            - ingestion_errors: Count of errors encountered during individual repository ingestions.
            - association_errors: Count of errors encountered during association creation.
        """
        search_session: Optional[KeywordSearchSession] = None
        processed_count = 0
        association_errors = 0
        ingestion_errors = 0
        items: List[Dict[str, Any]] = [] # Initialize list for GitHub search results

        try:
            # Instantiate repository access objects using the main task's session
            session_repo = KeywordSearchSessionRepository(db)
            assoc_repo = KeywordRepositoryAssociationRepository(db)
            repo_repo = RepositoryRepository(db)

            # --- Step 1: Fetch and Update Search Session Status ---
            search_session = session_repo.get(id=session_id)
            if not search_session:
                logger.error(f"Service: KeywordSearchSession ID {session_id} not found. Cannot proceed.")
                # Indicate session not found error; caller handles final status.
                return 0, 0, 1 # (processed, ingest_err, assoc_err)

            # Avoid reprocessing sessions already in a terminal state
            if search_session.status in ["COMPLETED", "FAILED"]:
                 logger.warning(f"Service: KeywordSearchSession {session_id} already in terminal state ({search_session.status}). Exiting.")
                 return 0, 0, 0 # Nothing to process

            # Update status to RUNNING and record start time if not already set
            search_session.status = "RUNNING"
            if not search_session.started_at:
                search_session.started_at = datetime.now(timezone.utc)
            db.add(search_session)
            # Commit this status update immediately using the main session
            db.commit()
            logger.info(f"Service: Session {session_id}: Status set to RUNNING.")

            # --- Step 2: Perform GitHub Search ---
            self.logger.info(f"Service: Session {session_id}: Searching GitHub repos for session {session_id}: '{keywords}', max={max_repos_to_process}")
            search_result_tuple = self.github_client.search_repositories(
                query=keywords, max_results=max_repos_to_process
            )

            # Handle potential failures in the GitHub search itself
            if search_result_tuple is None:
                 logger.error(f"Service: Session {session_id}: GitHub search request failed.")
                 # Indicate search failure; caller handles setting session to FAILED.
                 return 0, 1, 0 # (processed, ingest_err, assoc_err)

            items, total_count_reported = search_result_tuple
            self.logger.info(f"Service: Session {session_id}: GitHub search call returned {len(items)} items (GitHub reported total: {total_count_reported}).")


            # Handle case where search returns no results
            if not items:
                 logger.info(f"Service: Session {session_id}: No repositories found/fetched.")
                 # Update results count immediately if no items found
                 if search_session:
                     search_session.results_count = 0 # Explicitly set to zero
                     db.add(search_session)
                     db.commit() # Commit the final count using the main session
                 # Return success, as no processing errors occurred
                 return 0, 0, 0
            else:
                 # If items were found, but count hasn't been set, mark as in progress (or set actual count later)
                 if search_session and search_session.results_count is None:
                    # Optionally set the fetched count here, or wait until the end.
                    # Setting it now might be slightly inaccurate if some items are skipped.
                    # Let's defer setting the final count until the end of processing.
                    pass
                    # db.add(search_session)
                    # db.commit()


            # --- Step 3: Iterate Search Results and Process Repositories ---
            logger.info(f"Service: Session {session_id}: Starting processing loop for {len(items)} items.")
            for item_index, item in enumerate(items):
                # Extract essential info from the GitHub search result item
                repo_github_id = item.get("id")
                repo_full_name = item.get("full_name")
                repo_url = item.get("html_url")
                # Consistent logging prefix for messages related to this specific item
                item_log_prefix = f"Service: Session {session_id}: Item {item_index+1}/{len(items)} ({repo_full_name or 'N/A'})"
                logger.info(f"{item_log_prefix}: --- Processing START ---")

                # Basic validation of the search result item
                if not repo_url or not repo_github_id or not repo_full_name:
                    self.logger.warning(f"{item_log_prefix}: Skipping search item due to missing URL/ID/FullName.")
                    continue # Skip to the next item

                self.logger.info(f"{item_log_prefix}: Processing search result.")
                ingestion_succeeded = False # Track if ingestion was successful for this item
                repo_exists_before_ingest = False # Track if repo existed before attempting ingest
                repository_db_for_assoc: Optional[Repository] = None # Holds the DB object for association

                try:
                    # --- Step 3a: Check if Repository Exists Locally ---
                    # Use the main task's session 'db' for this check.
                    logger.debug(f"{item_log_prefix}: Checking if repo exists (GH ID: {repo_github_id})...")
                    existing_repo = repo_repo.get_by_github_id(github_id=repo_github_id)

                    if existing_repo:
                        # Repository already in the database, no need to re-ingest.
                        logger.info(f"{item_log_prefix}: Repo already exists (DB ID: {existing_repo.id}). Skipping ingestion call.")
                        repository_db_for_assoc = existing_repo # Use existing object for association
                        ingestion_succeeded = True # Mark as success for association purposes
                        repo_exists_before_ingest = True
                    else:
                        # --- Step 3b: Ingest New Repository (in Isolated Session) ---
                        logger.info(f"{item_log_prefix}: Repo not found. Calling ingestion service for URL: {repo_url}")
                        ingestion_db_session: Optional[Session] = None # Define session variable for this block
                        try:
                            # Create a *new, separate* database session just for this ingestion.
                            ingestion_db_session = SessionLocal()
                            logger.debug(f"{item_log_prefix}: Created separate session for ingestion.")
                            # Call the IngestionService, passing the isolated session.
                            chain = self.ingestion_service.ingest_repository_by_url(
                                db=ingestion_db_session, repo_url=repo_url
                            )

                            # Check the outcome of the ingestion process via the discovery chain status
                            ingestion_status = chain.status if chain else "FAILED (None returned)"
                            logger.info(f"{item_log_prefix}: Ingestion service call returned. Chain Status: {ingestion_status}")

                            if chain and chain.status == 'COMPLETED':
                                ingestion_succeeded = True
                                self.logger.info(f"{item_log_prefix}: Successfully ingested.")
                                # After successful ingestion in the separate session,
                                # fetch the newly created repository using the *main task's session*
                                # to ensure it's available for association in that context.
                                repository_db_for_assoc = repo_repo.get_by_github_id(github_id=repo_github_id)
                                if not repository_db_for_assoc:
                                    # This would be unusual but indicates a potential timing or session issue.
                                    logger.error(f"{item_log_prefix}: Ingestion supposedly OK, but repo GH ID {repo_github_id} not found in main session immediately after.")
                                    ingestion_succeeded = False # Treat as failure if repo not found after ingest
                            elif chain:
                                # Ingestion finished but didn't complete successfully (e.g., FAILED, PARTIAL)
                                self.logger.warning(f"{item_log_prefix}: Ingestion finished with status {chain.status}.")
                                ingestion_errors += 1
                            else:
                                # Ingestion service returned None, indicating an early failure (e.g., bad URL)
                                self.logger.error(f"{item_log_prefix}: Ingestion call failed (returned None).")
                                ingestion_errors += 1
                        except Exception as ingest_exc:
                            # Catch any unexpected exceptions during the ingestion call itself
                            logger.error(f"{item_log_prefix}: EXCEPTION during ingestion service call: {ingest_exc}", exc_info=True)
                            ingestion_errors += 1
                            ingestion_succeeded = False # Ensure failure is marked
                        finally:
                             # Always close the isolated ingestion session
                             if ingestion_db_session:
                                 logger.debug(f"{item_log_prefix}: Closing separate ingestion session.")
                                 ingestion_db_session.close()

                    # --- Step 3c: Create Association (in Main Session) ---
                    logger.debug(f"{item_log_prefix}: Entering association logic. ingestion_succeeded={ingestion_succeeded}")
                    # Proceed only if ingestion succeeded (or repo existed) and we have a valid repo object and search session.
                    if ingestion_succeeded and repository_db_for_assoc and search_session:
                         try:
                              logger.debug(f"{item_log_prefix}: Attempting to create/find association for DB Repo ID {repository_db_for_assoc.id}...")
                              # Check if this specific association already exists using the main session
                              existing_assoc = assoc_repo.get_by_session_and_repo_id(
                                  session_id=search_session.id,
                                  repository_id=repository_db_for_assoc.id
                              )
                              if not existing_assoc:
                                  # Create the association link in the main session's context
                                  assoc_repo.create_association(
                                       session_id=search_session.id,
                                       repository_id=repository_db_for_assoc.id,
                                       # Store relevance score from GitHub search if available
                                       match_details={'score': item.get('score')}
                                  )
                                  # Commit the association immediately using the main task's session 'db'
                                  db.commit()
                                  processed_count += 1 # Increment count of successfully processed/associated repos
                                  logger.info(f"{item_log_prefix}: Association successful (Processed count incremented).")
                              else:
                                   # Association already existed, no action needed, don't increment processed count again.
                                   logger.debug(f"{item_log_prefix}: Association already exists.")
                                   # If the repo existed before *and* the association existed, it means this search
                                   # rediscovered an already known and associated repo.
                                   # If the repo was ingested *this run* but the association somehow existed,
                                   # that would be an anomaly. The current logic correctly handles avoiding duplicates.

                         except Exception as assoc_exc:
                              # Catch errors during association creation/commit
                              logger.error(f"{item_log_prefix}: EXCEPTION during association: {assoc_exc}", exc_info=True)
                              association_errors += 1
                              try:
                                  # Rollback the main session to undo the failed association attempt
                                  db.rollback()
                                  logger.warning(f"{item_log_prefix}: Rolled back main session after association failure.")
                              except Exception as rb_err:
                                  logger.error(f"Error rolling back main session after association failure: {rb_err}")

                    elif ingestion_succeeded and not repository_db_for_assoc:
                        # Handle the unusual case where ingestion was marked successful but the repo object wasn't found
                        association_errors += 1
                        self.logger.error(f"{item_log_prefix}: Association failed: Repo supposedly ingested/existed but not found in main session (GH ID: {repo_github_id}).")
                    elif not ingestion_succeeded:
                         # Skip association if ingestion failed
                         logger.debug(f"{item_log_prefix}: Skipping association due to ingestion failure.")

                except Exception as outer_loop_exc:
                    # Catch unexpected errors in the main loop for this item (e.g., during repo check)
                    logger.error(f"{item_log_prefix}: EXCEPTION in outer item processing loop: {outer_loop_exc}", exc_info=True)
                    ingestion_errors += 1 # Count this as an error preventing processing of this item
                    try:
                        # Attempt to rollback the main session if an outer loop error occurred
                        db.rollback()
                        logger.warning(f"{item_log_prefix}: Rolled back main session after outer loop exception.")
                    except: pass # Ignore rollback errors during exception handling
                finally:
                    logger.info(f"{item_log_prefix}: --- Processing END ---")
            # --- End of loop for processing search items ---

            logger.info(f"Service: Session {session_id}: Finished processing loop for {len(items)} items.")

            # --- Step 4: Update Final Session Counts (Optional but recommended) ---
            # It might be useful to store the final counts back into the search_session record here.
            # Requires re-fetching the session if it wasn't kept updated.
            # Example:
            # if search_session:
            #     try:
            #         # Re-fetch in case state changed
            #         db.refresh(search_session)
            #         search_session.processed_count = processed_count # Assuming such a field exists
            #         search_session.results_count = len(items) # Or total_count_reported? Choose definition.
            #         db.add(search_session)
            #         db.commit()
            #         logger.info(f"Service: Session {session_id}: Updated final counts.")
            #     except Exception as count_update_err:
            #         logger.error(f"Service: Session {session_id}: Failed to update final session counts: {count_update_err}")
            #         db.rollback()

        # --- Global Error Handling for the Service Method ---
        except ApiClientError as api_e:
            # Errors during the initial setup or the main GitHub search call
            logger.error(f"Service: API Client Error during keyword discovery task setup/search for session {session_id}: {api_e}", exc_info=True)
            ingestion_errors += 1 # Count as a general failure for the session
            # Let the task runner handle setting the final FAILED status based on return/exception
        except SQLAlchemyError as db_e:
            # Database errors during session status updates or initial checks
            logger.error(f"Service: Database Error during keyword discovery task setup/search for session {session_id}: {db_e}", exc_info=True)
            try: db.rollback() # Rollback the main session
            except: pass
            association_errors +=1 # Count as DB error likely affecting state
            # Let the task runner handle final status
        except Exception as e:
            # Catch-all for any other unexpected critical errors
            logger.exception(f"Service: Unexpected critical error during keyword discovery task for session {session_id}: {e}")
            try: db.rollback() # Rollback the main session
            except: pass
            ingestion_errors += 1 # Count as a general failure
            # Let the task runner handle final status

        # The main database session `db` is managed (committed/rolled back/closed) by the caller (Celery task).
        logger.info(f"Service: Keyword discovery processing finished for session {session_id}. Returning counts: Processed={processed_count}, IngestErrors={ingestion_errors}, AssocErrors={association_errors}")
        return processed_count, ingestion_errors, association_errors