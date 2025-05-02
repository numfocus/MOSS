"""
backend.services.doi_processing_service
---------------------------------------
Handles the extraction, resolution, and storage of Digital Object Identifiers (DOIs)
found within repository files. Interacts with external services like OpenAlex
and manages related database entities (Work, DOIReference, DiscoveryChain).
"""

import logging
import re
import time # Ensure time is imported for sleep
from typing import Optional, TYPE_CHECKING, List, Set, Dict, Any, Tuple

from sqlalchemy.orm import Session, make_transient
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

# Import models and repositories
from backend.data.models import Repository, Work, DOIReference, DiscoveryChain, WorkCitation # Added WorkCitation
from backend.data.repositories import WorkRepository, DOIReferenceRepository
from backend.external import OpenAlexClient, ApiClientError
from backend.utils import doi_utils

# Import other services and helpers
from .base_service import BaseService
from .discovery_chain_service import DiscoveryChainService
from .scholarly_processing_service import ScholarlyProcessingService
# Import SessionLocal for creating isolated sessions in specific failure handling scenarios
from backend.data.database import SessionLocal

logger = logging.getLogger(__name__)

class DOIProcessingService(BaseService):
    """
    Service for processing DOIs discovered in source files.

    Core responsibilities include:
    1. Extracting potential DOIs from text content.
    2. Resolving valid DOIs against the OpenAlex API to retrieve Work metadata.
    3. Creating or updating corresponding Work records in the local database.
    4. Creating DOIReference records linking the discovered DOI to its source
       (Repository, file) and the resolved Work (if found).
    5. Managing DiscoveryChain records to track the provenance of DOI references
       and resolved Works.
    6. Invoking ScholarlyProcessingService to fetch and store detailed metadata
       (authors, affiliations, topics, citations) for the resolved Work.
    7. Enqueuing background tasks (with delay) to further process works
       referenced by, and citing, the primary resolved Work, enabling deeper
       graph traversal.

    Operates within a database session provided by the caller, using savepoints
    to isolate processing for individual DOIs within a single file. Commits
    occur strategically, particularly before enqueueing background tasks to ensure
    data consistency.
    """

    def __init__(self):
        """Initializes the service and its dependencies."""
        super().__init__()
        # Instantiate external clients and dependent services needed
        self.openalex_client = OpenAlexClient()
        self.discovery_chain_service = DiscoveryChainService()
        self.scholarly_processor = ScholarlyProcessingService()
        self.logger.debug(f"{self.__class__.__name__} initialized with its own service instances.")

    def _get_id_from_oa_url(self, url: Optional[str]) -> Optional[str]:
        """
        Extracts a relevant identifier from various scholarly ID URLs.

        Supports extracting IDs from OpenAlex work/author/institution URLs,
        ORCID URLs, ROR URLs, and DOI URLs (as normalized strings). Also handles
        cases where a bare OpenAlex ID (e.g., 'W12345') is provided directly.

        Args:
            url: The URL string or potential bare ID string.

        Returns:
            The extracted identifier string, or None if parsing fails or the URL
            format is unrecognized/invalid.
        """
        if not url or not isinstance(url, str): return None
        try:
            id_part: Optional[str] = None
            # Extract based on URL prefix
            if url.startswith("https://orcid.org/"):
                 match = re.search(r'(\d{4}-\d{4}-\d{4}-\d{3}[0-9X])', url)
                 id_part = match.group(1) if match else None
            elif url.startswith("https://ror.org/"):
                 id_part = url.split('/')[-1]
            elif url.startswith("https://openalex.org/"):
                 id_part = url.split('/')[-1]
            elif url.startswith("https://doi.org/"):
                 # Return the DOI itself, normalized (without the prefix)
                 id_part = url[len("https://doi.org/"):]
            # Check for bare OpenAlex ID pattern (e.g., W123, A456, I789)
            elif url and url[0].isalpha() and url[1:].isdigit():
                id_part = url
            else:
                 id_part = None # Unrecognized format

            # Basic validation of extracted ID format (can be extended)
            is_valid = False
            if id_part:
                if url.startswith("https://openalex.org/") and id_part[0].isalpha() and id_part[1:].isdigit(): is_valid = True
                elif url.startswith("https://orcid.org/") and match: is_valid = True
                elif url.startswith("https://ror.org/") and id_part.startswith('0') and len(id_part) == 9: is_valid = True
                elif url.startswith("https://doi.org/"): is_valid = True # Assume valid DOI string if extracted
                elif id_part == url and url[0].isalpha() and url[1:].isdigit(): is_valid = True # Valid bare OA ID

            return id_part if is_valid else None

        except Exception as e:
             # Log parsing errors but don't crash the whole process
             logger.error(f"Error parsing ID/URL {url}: {e}", exc_info=False)
        return None

    def extract_resolve_and_store_dois(
        self,
        db: Session,
        parent_chain: DiscoveryChain,
        repository: Repository,
        file_content: Optional[str],
        source_file: str
    ) -> None:
        """
        Orchestrates the main DOI processing workflow for a given file's content.

        Extracts DOIs, resolves them via OpenAlex, stores Work and DOIReference records,
        triggers detailed scholarly data processing for the primary work using
        ScholarlyProcessingService, commits the main transaction periodically,
        and enqueues background tasks for further exploration of referenced and
        citing works (with a delay to allow the main transaction to fully commit).

        Uses nested transactions (savepoints) to isolate failures related to a single
        DOI, allowing the processing of other DOIs in the same file to continue.

        Args:
            db: The active SQLAlchemy database session.
            parent_chain: The parent DiscoveryChain representing the file processing step.
            repository: The Repository database object the file belongs to.
            file_content: The text content of the file to scan for DOIs.
            source_file: The path or name of the file being processed.

        Returns:
            None. Changes are persisted to the database via the provided session,
            and background tasks are enqueued.
        """
        if not file_content:
            logger.debug(f"No file content provided for {source_file} in repo {repository.id}. Skipping DOI extraction.")
            return

        try:
            # Extract unique potential DOIs from the text
            extracted_dois = doi_utils.extract_dois_from_text(file_content)
        except Exception as e:
            # Log critical error during extraction phase
            logger.error(f"Error extracting DOIs from {source_file} for repo {repository.id}: {e}", exc_info=True)
            raise # Re-raise to indicate failure at this stage

        if not extracted_dois:
            logger.debug(f"No potential DOIs found in {source_file} for repo {repository.id}.")
            return

        logger.info(f"Found {len(extracted_dois)} unique potential DOIs in {source_file} for repo {repository.id}.")

        # Instantiate repositories using the provided session
        work_repo = WorkRepository(db)
        doi_ref_repo = DOIReferenceRepository(db)
        any_doi_failed = False # Track if any DOI within the file failed processing
        TASK_DELAY_SECONDS = 5 # Delay before background tasks start (allows commit propagation)

        # Process each extracted DOI individually
        for doi in extracted_dois:
            logger.debug(f"DOI Loop: Processing DOI '{doi}' from {source_file}")

            # Start a nested transaction (SAVEPOINT) for this specific DOI.
            # This allows rollback of only this DOI's changes if an error occurs,
            # without affecting the overall transaction for the file.
            nested_transaction = db.begin_nested()
            doi_ref_chain: Optional[DiscoveryChain] = None
            resolved_work: Optional[Work] = None
            work_chain: Optional[DiscoveryChain] = None
            referenced_oa_ids: List[str] = [] # OpenAlex IDs of works cited by this DOI's work
            related_oa_ids: List[str] = [] # OpenAlex IDs of works related to this DOI's work
            cited_by_url_for_tasks: Optional[str] = None # URL to fetch citing works from OpenAlex
            doi_reference_id: Optional[int] = None # DB ID of the created DOIReference
            primary_work_oa_id_for_tasks: Optional[str] = None # OpenAlex ID of the resolved work
            commit_main_transaction_successful = False # Flag to control task enqueueing

            try:
                # --- 1. Check if this exact DOIReference already exists ---
                # Avoid redundant processing if this specific DOI in this file was already processed.
                existing_ref = doi_ref_repo.find_by_repository_and_doi_and_source(
                    repository_id=repository.id, doi=doi, source_file=source_file
                )
                if existing_ref:
                    self.logger.debug(f"DOI Loop: DOIReference exists for '{doi}' in {source_file}, committing savepoint and skipping.")
                    nested_transaction.commit() # Commit the savepoint (effectively does nothing if no changes)
                    continue # Move to the next DOI in the file

                # --- 2. Create Discovery Chain for this DOI Reference ---
                # Tracks the discovery of this specific DOI mention.
                doi_ref_chain = self.discovery_chain_service.create_child_chain(
                    db=db,
                    parent_chain=parent_chain, # Linked to the file processing chain
                    discovery_type='REL_DOI_REFERENCE',
                    parameters={'repository_id': repository.id, 'source_file': source_file, 'doi': doi}
                )
                self.discovery_chain_service.start_chain(db, doi_ref_chain)
                logger.debug(f"DOI Loop: Created DOI ref chain {doi_ref_chain.id} for '{doi}'.")

                # --- 3. Resolve DOI via OpenAlex ---
                # Attempt to find the corresponding scholarly Work using the DOI.
                work_data = self.openalex_client.resolve_doi_to_work(doi)
                logger.debug(f"DOI Loop: OpenAlex resolution result for '{doi}': {'Data found' if work_data else 'Not found (None)'}")

                # --- 4. Process Resolved Work (if found) ---
                if work_data:
                    # Prepare data for creating/updating the Work record
                    work_input_data = {
                        "openalex_id": self._get_id_from_oa_url(work_data.get("id")),
                        "doi": self._get_id_from_oa_url(work_data.get("doi")), # Normalize DOI
                        "title": work_data.get("title"),
                        "publication_year": work_data.get("publication_year"),
                        "type": work_data.get("type"),
                        "cited_by_count": work_data.get("cited_by_count"),
                        "host_venue_display_name": work_data.get("host_venue", {}).get("display_name"),
                        "openalex_url": work_data.get("id")
                    }
                    # Remove keys with None values to avoid overriding existing data with None
                    work_input_data = {k: v for k, v in work_input_data.items() if v is not None}

                    # Validate essential identifiers obtained from OpenAlex
                    if "doi" not in work_input_data or "openalex_id" not in work_input_data:
                        # This indicates an issue with the OpenAlex data or parsing
                        raise ValueError(f"Missing essential info (DOI/OA ID) for Work from DOI {doi}")

                    # --- 4a. Get or Create Work Record ---
                    # Finds existing Work by DOI or creates a new one.
                    resolved_work = work_repo.get_or_create_by_doi(
                        doi=work_input_data["doi"], obj_in_data=work_input_data
                    )
                    # Store the OpenAlex ID for potential background task arguments
                    primary_work_oa_id_for_tasks = resolved_work.openalex_id
                    logger.debug(f"DOI Loop: Got/Created Work ID {resolved_work.id}, OA_ID '{primary_work_oa_id_for_tasks}' for DOI '{doi}'.")

                    # --- 4b. Create Work Discovery Chain ---
                    # Tracks the discovery of this Work specifically from this DOI.
                    work_chain = self.discovery_chain_service.create_child_chain(
                        db=db,
                        parent_chain=doi_ref_chain, # Linked to the DOI reference chain
                        discovery_type='REL_WORK_FROM_DOI',
                        parameters={'doi': doi, 'openalex_id': resolved_work.openalex_id}
                    )
                    # Link the Work record to its discovery chain
                    self.discovery_chain_service.associate_entity(db, work_chain, resolved_work, is_direct=True)

                    # --- 4c. Fetch Full Details & Process Scholarly Data ---
                    # If the work was successfully resolved, fetch and process its detailed metadata.
                    if resolved_work and resolved_work.openalex_id and work_chain:
                        full_work_data = None
                        try:
                            # Retrieve comprehensive data including authorships, topics, etc.
                            full_work_data = self.openalex_client.get_work_details(resolved_work.openalex_id)
                        except Exception as fetch_err:
                            # Log error but don't necessarily fail the entire DOI processing
                            logger.error(f"Error fetching full details for Work OA ID {resolved_work.openalex_id}: {fetch_err}", exc_info=True)

                        if full_work_data:
                            logger.debug(f"DOI Loop: Processing scholarly data for Work ID {resolved_work.id}...")
                            try:
                                # Delegate detailed processing (authors, institutions, topics, citations)
                                # This returns IDs needed for background task enqueueing.
                                referenced_oa_ids, related_oa_ids, cited_by_url_for_tasks = \
                                    self.scholarly_processor.process_openalex_work_data(
                                        db=db,
                                        work_db=resolved_work,
                                        work_api_data=full_work_data,
                                        parent_chain=work_chain # Pass the specific work chain
                                    )
                                logger.debug(f"DOI Loop: Scholarly processing returned: Refs={len(referenced_oa_ids)}, Related={len(related_oa_ids)}, CitedByURL={'Present' if cited_by_url_for_tasks else 'Absent'}")
                            except Exception as scholarly_err:
                                # Log error during detailed processing, but allow the DOI reference to be saved
                                logger.error(f"Error during scholarly processing for Work OA ID {resolved_work.openalex_id}: {scholarly_err}", exc_info=True)
                                # Potentially mark the work_chain as failed or partial here?
                        else:
                            logger.warning(f"DOI Loop: Could not fetch full details for Work ID {resolved_work.id}. Skipping detailed scholarly processing.")

                    # Complete the work discovery chain (regardless of detailed processing outcome)
                    if work_chain:
                        self.discovery_chain_service.complete_chain(db, work_chain)
                else:
                     # Case where the DOI did not resolve to a known Work in OpenAlex
                     logger.info(f"DOI Loop: DOI '{doi}' did not resolve via OpenAlex.")

                # --- 5. Create DOI Reference Record ---
                # Link the Repository, source file, and the resolved Work (if any)
                doi_ref_input_data = {
                    "repository_id": repository.id,
                    "doi": doi,
                    "work_id": resolved_work.id if resolved_work else None, # Link to Work if resolved
                    "source_file": source_file
                }
                doi_reference = DOIReference(**doi_ref_input_data)
                db.add(doi_reference)
                db.flush() # Flush to get the doi_reference.id assigned by the database
                doi_reference_id = doi_reference.id
                logger.debug(f"DOI Loop: Created DOIReference ID {doi_reference_id} for '{doi}'.")

                # Associate the DOIReference record with its discovery chain
                self.discovery_chain_service.associate_entity(db, doi_ref_chain, doi_reference, is_direct=True)

                # --- 6. Finalize DOI Reference Chain Status ---
                if resolved_work:
                    # Mark as completed if the DOI led to a Work
                    self.discovery_chain_service.complete_chain(db, doi_ref_chain)
                else:
                    # Mark as failed if the DOI could not be resolved
                    self.discovery_chain_service.fail_chain(db, doi_ref_chain, error_message="DOI not resolved in OpenAlex")

                # --- 7. Commit Savepoint ---
                # Persist changes made within this loop for this specific DOI.
                logger.debug(f"DOI Loop: Attempting commit for savepoint related to DOI '{doi}'...")
                nested_transaction.commit()
                logger.info(f"DOI Loop: Successfully committed savepoint for DOI '{doi}' (Ref ID: {doi_reference_id}).")

                # --- 8. Commit Main Transaction (IMPORTANT!) ---
                # Before enqueueing background tasks, commit the main transaction
                # to ensure the created Work, DOIReference, etc., are visible to the tasks.
                try:
                    db.commit()
                    commit_main_transaction_successful = True # Mark success
                    logger.info(f"DOI Loop: Committed main transaction after processing DOI '{doi}' before enqueueing.")
                except Exception as main_commit_err:
                    # This is a critical failure; the state might be inconsistent.
                    logger.error(f"DOI Loop: FAILED to commit main transaction for DOI '{doi}': {main_commit_err}", exc_info=True)
                    db.rollback() # Roll back the entire transaction for safety
                    primary_work_oa_id_for_tasks = None # Prevent enqueueing based on failed commit
                    any_doi_failed = True
                    # Attempt to mark the related discovery chain as failed using a separate session
                    # This is best-effort as the primary transaction failed.
                    if doi_ref_chain and doi_ref_chain.id:
                        try:
                            # Use a new, independent session for this update
                            temp_db = SessionLocal()
                            try:
                                chain_to_fail = self.discovery_chain_service.get_by_uuid(temp_db, doi_ref_chain.id)
                                if chain_to_fail:
                                    self.discovery_chain_service.fail_chain(temp_db, chain_to_fail, error_message=f"Main commit failed: {str(main_commit_err)[:100]}")
                                    temp_db.commit() # Commit this specific status update
                                    logger.info(f"Marked DOI Ref Chain {chain_to_fail.id} as FAILED after main commit failure.")
                                else:
                                    logger.error(f"Could not find DOI Ref Chain {doi_ref_chain.id} to mark as failed after main commit failure.")
                            except Exception as fail_e:
                                logger.error(f"Failed to mark DOI Ref Chain {doi_ref_chain.id} as FAILED after main commit failure: {fail_e}")
                                temp_db.rollback()
                            finally:
                                temp_db.close()
                        except Exception as session_err:
                            logger.error(f"Failed to create temp session for failure update: {session_err}")

            # --- Error Handling for Single DOI Processing (within the loop) ---
            except Exception as e:
                 any_doi_failed = True
                 logger.error(f"DOI Loop: FAILED processing DOI '{doi}' from {source_file} (before main commit attempt). Rolling back savepoint. Error: {e}", exc_info=True)
                 try:
                     # Roll back only the changes made since the last savepoint (for this DOI)
                     nested_transaction.rollback()
                 except Exception as rb_err:
                     logger.error(f"Error rolling back savepoint for failed DOI {doi}: {rb_err}", exc_info=True)

                 # Attempt to mark the discovery chain as failed (best-effort)
                 if doi_ref_chain and doi_ref_chain.id:
                     try:
                         # Use a new, independent session
                         temp_db = SessionLocal()
                         try:
                             chain_to_fail = self.discovery_chain_service.get_by_uuid(temp_db, doi_ref_chain.id)
                             if chain_to_fail:
                                  self.discovery_chain_service.fail_chain(temp_db, chain_to_fail, error_message=f"Savepoint rolled back: {str(e)[:100]}")
                                  temp_db.commit()
                                  logger.info(f"Marked DOI Ref Chain {chain_to_fail.id} as FAILED after rollback.")
                             else:
                                 logger.error(f"Could not re-fetch DOI Ref Chain {doi_ref_chain.id} to mark as failed after rollback.")
                         except Exception as fail_e:
                             logger.error(f"Failed to mark DOI Ref Chain {doi_ref_chain.id} as FAILED after rollback: {fail_e}")
                             temp_db.rollback()
                         finally:
                              temp_db.close()
                     except Exception as session_err:
                         logger.error(f"Failed to create temp session for failure update after rollback: {session_err}")

                 # Prevent task enqueueing if the initial processing within the savepoint failed
                 primary_work_oa_id_for_tasks = None

            # --- 9. Background Task Enqueueing ---
            # Only proceed if the main transaction for this DOI was committed successfully
            # and a primary work was resolved.
            if commit_main_transaction_successful and primary_work_oa_id_for_tasks:
                logger.info(
                    f"DOI Loop: Enqueueing tasks for committed Work OA ID '{primary_work_oa_id_for_tasks}' "
                    f"(DOI: '{doi}', Ref ID: {doi_reference_id}, CitedByURL: {'Present' if cited_by_url_for_tasks else 'Absent'}, "
                    f"Refs: {len(referenced_oa_ids)}, Related: {len(related_oa_ids)}) with {TASK_DELAY_SECONDS}s countdown..."
                )

                # Import task functions locally to avoid potential circular dependencies at module level
                from backend.tasks.scholarly_tasks import process_work_deeply_task, process_citing_works_list_task

                # --- Enqueue Task 1: Process Citing Works ---
                # If OpenAlex provided a URL to fetch works citing the primary work.
                if cited_by_url_for_tasks:
                    try:
                        process_citing_works_list_task.apply_async(
                            args=[
                                primary_work_oa_id_for_tasks, # The work being cited (W1)
                                cited_by_url_for_tasks,       # API endpoint to get citing works (Wc)
                                doi_reference_id              # Link back to the original DOI discovery context
                            ],
                            countdown=TASK_DELAY_SECONDS # Delay execution slightly
                        )
                        logger.debug(f"DOI Loop: Enqueued citing works task for {primary_work_oa_id_for_tasks}.")
                    except Exception as enqueue_err_citing:
                         logger.error(f"DOI Loop: Failed enqueueing citing works task for {primary_work_oa_id_for_tasks}: {enqueue_err_citing}")
                else:
                    logger.debug(f"DOI Loop: No cited_by_api_url for {primary_work_oa_id_for_tasks}, skipping citing task.")

                # --- Enqueue Task 2: Process Referenced Works ---
                # If the primary work references other works.
                if referenced_oa_ids:
                    # Initialize the list of visited nodes for cycle detection in the task
                    initial_visited_list: List[str] = [primary_work_oa_id_for_tasks]
                    logger.info(f"DOI Loop: Enqueueing deep processing for {len(referenced_oa_ids)} referenced works (W1 cites Wr)...")
                    for ref_oa_id in referenced_oa_ids:
                        # Avoid enqueueing a task for the work to process itself (self-citation handled within task)
                        # Also ensure the referenced ID is valid.
                        if ref_oa_id and ref_oa_id != primary_work_oa_id_for_tasks:
                            try:
                                process_work_deeply_task.apply_async(
                                    args=[
                                        ref_oa_id,                     # The work to process deeply (Wr)
                                        primary_work_oa_id_for_tasks,  # The citing work (W1)
                                        'citation',                    # Relationship type: W1 -> Wr
                                        doi_reference_id,              # Link back to original context
                                        1,                             # Initial depth for this branch
                                        initial_visited_list           # Pass initial visited list
                                    ],
                                    countdown=TASK_DELAY_SECONDS
                                )
                                logger.debug(f"DOI Loop: Enqueued referenced work task: {ref_oa_id} from {primary_work_oa_id_for_tasks}")
                            except Exception as enqueue_err_ref:
                                 logger.error(f"DOI Loop: Failed to enqueue referenced work {ref_oa_id}: {enqueue_err_ref}")
                else:
                     logger.debug(f"DOI Loop: No referenced works to enqueue for {primary_work_oa_id_for_tasks}.")

                # Optional: Enqueue tasks for related works if needed (currently not standard)
                # if related_oa_ids:
                #     logger.debug(f"DOI Loop: Enqueueing deep processing for {len(related_oa_ids)} related works...")
                #     # ... similar enqueue logic using 'relation' type ...

            elif not commit_main_transaction_successful:
                logger.warning(f"DOI Loop: Skipping task enqueueing for DOI '{doi}' due to main transaction commit failure.")
            elif not primary_work_oa_id_for_tasks:
                # Handles cases where DOI didn't resolve or essential info was missing
                logger.info(f"DOI Loop: Skipping task enqueueing for DOI '{doi}' as primary work OA ID was not resolved/set.")
            # --- End Task Enqueueing Section ---

        # --- End of loop for processing individual DOIs ---
        logger.info(f"DOI Processing END for: Repo {repository.id}, File {source_file}. Any DOI failures: {any_doi_failed}")