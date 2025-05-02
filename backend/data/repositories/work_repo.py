# work_repo.py

"""
backend.data.repositories.work_repo
-----------------------------------
Provides data access operations for the Work model, representing academic works
(e.g., papers, datasets) often identified by DOIs or OpenAlex IDs.
"""

import logging
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError # General SQLAlchemy exception

from .base_repository import BaseRepository
from backend.data.models import Work # The specific SQLAlchemy model

logger = logging.getLogger(__name__)

class WorkRepository(BaseRepository[Work]):
    """
    Repository managing CRUD and specific queries for Work entities.

    Handles complexities arising from multiple potential identifiers (DOI, OpenAlex ID)
    and provides robust get-or-create methods to manage these, including conflict checks
    and handling of placeholder DOIs.
    """

    def __init__(self, db: Session):
        """
        Initializes the WorkRepository.

        Args:
            db: The SQLAlchemy Session for database interactions.
        """
        # Initialize the base repository with the Work model.
        super().__init__(Work, db)

    def get_by_doi(self, *, doi: str) -> Optional[Work]:
        """
        Retrieves a Work entity by its DOI.

        Comparison is typically case-insensitive at the database level if using
        appropriate collation, but the input `doi` string itself is used here.
        Consider normalizing the DOI before querying if necessary.

        Args:
            doi: The DOI string of the work.

        Returns:
            The Work model instance if found, otherwise None. Returns None if doi is empty.

        Raises:
            SQLAlchemyError: If a database error occurs during the query.
        """
        if not doi: return None # Avoid querying with empty DOI.
        logger.debug(f"Getting Work by DOI: {doi}")
        if not self.db.is_active:
            logger.warning(f"Session is inactive in get_by_doi for Work DOI {doi}")
            return None
        try:
            # Query based on the DOI.
            # Performance Note: Indexing on the 'doi' column is crucial.
            # Consider `noload('*')` or `load_only()` if only the ID is needed frequently.
            return self.db.query(self.model).filter(self.model.doi == doi).first()
        except SQLAlchemyError as e:
            logger.error(f"SQLAlchemyError during get_by_doi for Work {doi}: {e}", exc_info=True)
            raise

    def get_by_openalex_id(self, *, openalex_id: str) -> Optional[Work]:
        """
        Retrieves a Work entity by its unique OpenAlex ID.

        Args:
            openalex_id: The OpenAlex ID string (e.g., 'https://openalex.org/W12345')
                         of the work.

        Returns:
            The Work model instance if found, otherwise None. Returns None if openalex_id is empty.

        Raises:
            SQLAlchemyError: If a database error occurs during the query.
        """
        if not openalex_id: return None # Avoid querying with empty ID.
        logger.debug(f"Getting Work by OpenAlex ID: {openalex_id}")
        if not self.db.is_active:
            logger.warning(f"Session is inactive in get_by_openalex_id for Work OA ID {openalex_id}")
            return None
        try:
            # Query based on the OpenAlex ID. Indexing is essential here too.
            return self.db.query(self.model).filter(self.model.openalex_id == openalex_id).first()
        except SQLAlchemyError as e:
            logger.error(f"SQLAlchemyError during get_by_openalex_id for Work {openalex_id}: {e}", exc_info=True)
            raise

    def get_or_create_by_doi(
        self, *, doi: str, obj_in_data: Dict[str, Any]
    ) -> Work:
        """
        Retrieves or creates a Work, prioritizing the DOI.

        Handles logic for works identified by DOI or OpenAlex ID:
        1. Attempts to fetch by `doi`.
        2. If found (by DOI): Updates fields (like OpenAlex ID, title, counts) if they
           differ, checking for OpenAlex ID conflicts (if the new OA ID belongs to
           another existing work).
        3. If not found by DOI: Checks if an `openalex_id` is provided in `obj_in_data`.
        4. If OA ID provided: Attempts to fetch by `openalex_id`.
        5. If found (by OA ID): Updates the existing record, potentially adding the
           `doi` if it was missing or was a placeholder, and filling other missing fields.
        6. If not found by DOI or OA ID: Creates a new Work record using
           `obj_in_data` (ensuring `doi` is set).

        Important:
        - Does NOT commit the transaction; caller is responsible.
        - Uses `db.flush()` and `db.refresh()` after add/update operations.

        Args:
            doi: The primary DOI to search for or use for creation.
            obj_in_data: Dictionary with work data. May include 'openalex_id',
                         'title', 'cited_by_count', etc.

        Returns:
            The existing (potentially updated) or newly created Work instance,
            managed within the session and flushed.

        Raises:
            ValueError: If `doi` is missing.
            RuntimeError: If the session is inactive.
            SQLAlchemyError: If any database operation fails.
        """
        if not doi:
             raise ValueError("DOI cannot be empty for Work get_or_create_by_doi")
        if not self.db.is_active:
             logger.error("Session is inactive at start of get_or_create_by_doi for Work.")
             raise RuntimeError("Database session is inactive, cannot perform get_or_create.")

        try:
            # --- Step 1: Query First by DOI ---
            db_obj = self.get_by_doi(doi=doi)

            if db_obj:
                # --- Step 2a: Found by DOI - Update Check ---
                logger.debug(f"Found existing Work by DOI {doi} (DB ID: {db_obj.id}). Checking for updates.")
                updated = False
                new_oa_id = obj_in_data.get("openalex_id")

                # Update OpenAlex ID if provided and different, checking for conflicts.
                if new_oa_id and db_obj.openalex_id != new_oa_id:
                     if not self.db.is_active: # Re-check session
                          raise RuntimeError("Session inactive before OA ID conflict check.")
                     existing_oa_work = self.get_by_openalex_id(openalex_id=new_oa_id)
                     if existing_oa_work and existing_oa_work.id != db_obj.id:
                          # Log conflict, skip OA ID update.
                          logger.warning(
                              f"Cannot update OA ID for Work DOI {doi} (DB ID {db_obj.id}) to {new_oa_id} "
                              f"because it's already assigned to Work DB ID {existing_oa_work.id}. Skipping OA ID update."
                          )
                     else:
                          logger.info(f"Updating OA ID for Work {db_obj.id} from '{db_obj.openalex_id}' to '{new_oa_id}'")
                          db_obj.openalex_id = new_oa_id
                          updated = True

                # Update other fields if provided and different.
                if obj_in_data.get('title') is not None and db_obj.title != obj_in_data.get('title'):
                    db_obj.title = obj_in_data['title']
                    updated = True
                if obj_in_data.get('cited_by_count') is not None and db_obj.cited_by_count != obj_in_data.get('cited_by_count'):
                    db_obj.cited_by_count = obj_in_data['cited_by_count']
                    updated = True
                # Add other updatable fields (publication_year, type, etc.)...

                if updated:
                    self.db.add(db_obj) # Mark as dirty.
                    logger.info(f"Work {db_obj.id} (found by DOI) marked for update.")
                    # Optional: Flush and refresh.
                    # self.db.flush()
                    # self.db.refresh(db_obj)
                return db_obj # Return the instance found by DOI.

            else:
                # --- Step 2b: Not Found by DOI - Check OpenAlex ID ---
                openalex_id = obj_in_data.get("openalex_id")
                if openalex_id:
                    # --- Step 3: Query by OpenAlex ID ---
                    db_obj_oa = self.get_by_openalex_id(openalex_id=openalex_id)
                    if db_obj_oa:
                        # --- Step 4: Found by OA ID - Update with DOI ---
                        logger.warning(f"Work not found by DOI {doi}, but found existing "
                                       f"Work DB ID {db_obj_oa.id} by OA ID {openalex_id}. Attempting to merge/update.")
                        updated = False
                        # Update DOI if it was missing or a placeholder.
                        # Assumes placeholders start with 'placeholder/'. Adapt if needed.
                        if db_obj_oa.doi is None or db_obj_oa.doi.startswith('placeholder/'):
                            logger.info(f"Updating placeholder/missing DOI for Work {db_obj_oa.id} (found by OA ID {openalex_id}) to {doi}")
                            db_obj_oa.doi = doi
                            updated = True
                        # Potentially update other fields if they were missing on the OA-found record.
                        if obj_in_data.get('title') is not None and db_obj_oa.title is None:
                            db_obj_oa.title = obj_in_data['title']
                            updated = True
                        if obj_in_data.get('cited_by_count') is not None and db_obj_oa.cited_by_count is None:
                            db_obj_oa.cited_by_count = obj_in_data['cited_by_count']
                            updated = True
                        # Add other fields...

                        if updated:
                            self.db.add(db_obj_oa) # Mark for update.
                            logger.info(f"Work {db_obj_oa.id} (found by OA ID) marked for update with DOI {doi}.")
                            # Optional: Flush and refresh.
                            # self.db.flush()
                            # self.db.refresh(db_obj_oa)
                        return db_obj_oa # Return the instance found by OA ID.

                # --- Step 5: Not Found by DOI or OA ID - Create New ---
                logger.debug(f"Work DOI {doi} (and OA ID {openalex_id or 'N/A'}) not found. Creating new.")
                obj_in_data["doi"] = doi # Ensure DOI is set.
                new_obj = self.model(**obj_in_data) # Create instance.
                self.db.add(new_obj) # Add to session.
                self.db.flush() # Send INSERT.
                self.db.refresh(new_obj) # Load DB defaults.
                logger.info(f"Successfully created and flushed new Work DOI {doi} (DB ID: {new_obj.id})")
                return new_obj # Return the new instance.

        except SQLAlchemyError as e:
            logger.error(f"SQLAlchemyError during get_or_create_by_doi for Work DOI {doi}: {e}", exc_info=True)
            # Caller handles rollback.
            raise

    def get_or_create_by_openalex_id(
        self, *, openalex_id: str, obj_in_data: Dict[str, Any]
    ) -> Work:
        """
        Retrieves or creates a Work, prioritizing the OpenAlex ID.

        Handles logic for works identified by OpenAlex ID or DOI:
        1. Attempts to fetch by `openalex_id`.
        2. If found (by OA ID): Updates fields (like DOI, title, counts) if they differ,
           checking for DOI conflicts (if the new DOI belongs to another existing work).
           Handles updates from placeholder DOIs.
        3. If not found by OA ID: Checks if a non-placeholder `doi` is provided.
        4. If DOI provided: Attempts to fetch by `doi`.
        5. If found (by DOI): Updates the existing record, primarily adding the
           `openalex_id` if it was missing, and potentially filling other missing fields.
        6. If not found by OA ID or DOI: Creates a new Work record using `obj_in_data`,
           assigning a placeholder DOI if a real one isn't provided.

        Important:
        - Does NOT commit the transaction.
        - Uses `db.flush()` and `db.refresh()`.
        - Handles placeholder DOIs starting with `placeholder/oa_`.

        Args:
            openalex_id: The primary OpenAlex ID to search for or use for creation.
            obj_in_data: Dictionary with work data. May include 'doi', 'title', etc.

        Returns:
            The existing (potentially updated) or newly created Work instance,
            managed within the session and flushed.

        Raises:
            ValueError: If `openalex_id` is missing.
            RuntimeError: If the session is inactive.
            SQLAlchemyError: If any database operation fails.
        """
        if not openalex_id:
            raise ValueError("OpenAlex ID cannot be empty for Work get_or_create_by_openalex_id")
        if not self.db.is_active:
             logger.error("Session is inactive at start of get_or_create_by_openalex_id for Work.")
             raise RuntimeError("Database session is inactive, cannot perform get_or_create.")

        try:
            # --- Step 1: Query First by OpenAlex ID ---
            db_obj = self.get_by_openalex_id(openalex_id=openalex_id)

            if db_obj:
                # --- Step 2a: Found by OA ID - Update Check ---
                logger.debug(f"Found existing Work by OA ID {openalex_id} (DB ID: {db_obj.id}). Checking for updates.")
                updated = False
                new_doi = obj_in_data.get("doi")

                # Update DOI if provided and different (or if current is placeholder).
                # Also checks for conflicts if the new DOI exists elsewhere.
                needs_doi_update = new_doi and (db_obj.doi is None or db_obj.doi.startswith('placeholder/') or db_obj.doi != new_doi)
                if needs_doi_update:
                    if not self.db.is_active: # Re-check session
                         raise RuntimeError("Session inactive before DOI conflict check.")
                    existing_doi_work = self.get_by_doi(doi=new_doi) if new_doi else None # Check only if new_doi is not None
                    if existing_doi_work and existing_doi_work.id != db_obj.id:
                        # Log conflict, skip DOI update.
                        logger.warning(
                            f"Cannot update DOI for Work OA ID {openalex_id} (DB ID {db_obj.id}) to {new_doi} "
                            f"because it's already assigned to Work DB ID {existing_doi_work.id}. Skipping DOI update."
                        )
                    else:
                         logger.info(f"Updating DOI for Work {db_obj.id} from '{db_obj.doi}' to '{new_doi}'")
                         db_obj.doi = new_doi
                         updated = True

                # Update other fields if provided and different.
                if obj_in_data.get('title') is not None and db_obj.title != obj_in_data.get('title'):
                    db_obj.title = obj_in_data['title']
                    updated = True
                if obj_in_data.get('cited_by_count') is not None and db_obj.cited_by_count != obj_in_data.get('cited_by_count'):
                    db_obj.cited_by_count = obj_in_data['cited_by_count']
                    updated = True
                # Add other updatable fields ...

                if updated:
                    self.db.add(db_obj) # Mark as dirty.
                    logger.info(f"Work {db_obj.id} (found by OA ID) marked for update.")
                    # Optional: Flush and refresh.
                    # self.db.flush()
                    # self.db.refresh(db_obj)
                return db_obj # Return instance found by OA ID.
            else:
                # --- Step 2b: Not Found by OA ID - Check DOI ---
                doi_to_check = obj_in_data.get("doi")
                # Only check by DOI if it's provided and isn't a placeholder itself.
                if doi_to_check and not doi_to_check.startswith('placeholder/'):
                    # --- Step 3: Query by DOI ---
                    db_obj_doi = self.get_by_doi(doi=doi_to_check)
                    if db_obj_doi:
                        # --- Step 4: Found by DOI - Update with OA ID ---
                        logger.warning(f"Work not found by OA ID {openalex_id}, but found existing "
                                       f"Work DB ID {db_obj_doi.id} by DOI {doi_to_check}. Attempting to merge/update.")
                        updated = False
                        # Add the OpenAlex ID if it was missing.
                        if not db_obj_doi.openalex_id:
                            logger.info(f"Updating missing OA ID for Work {db_obj_doi.id} (found by DOI {doi_to_check}) to {openalex_id}")
                            db_obj_doi.openalex_id = openalex_id
                            updated = True
                        # Potentially update other fields if missing.
                        if obj_in_data.get('title') is not None and db_obj_doi.title is None:
                            db_obj_doi.title = obj_in_data['title']
                            updated = True
                        if obj_in_data.get('cited_by_count') is not None and db_obj_doi.cited_by_count is None:
                            db_obj_doi.cited_by_count = obj_in_data['cited_by_count']
                            updated = True
                        # Add other fields ...

                        if updated:
                            self.db.add(db_obj_doi) # Mark for update.
                            logger.info(f"Work {db_obj_doi.id} (found by DOI) marked for update with OA ID {openalex_id}.")
                            # Optional: Flush and refresh.
                            # self.db.flush()
                            # self.db.refresh(db_obj_doi)
                        return db_obj_doi # Return instance found by DOI.

                # --- Step 5: Not Found by OA ID or valid DOI - Create New ---
                logger.debug(f"Work OA ID {openalex_id} (and DOI {doi_to_check or 'N/A'}) not found. Creating new.")
                obj_in_data["openalex_id"] = openalex_id # Ensure OA ID is set.
                # Assign a placeholder DOI if a real DOI wasn't provided in the input data.
                if "doi" not in obj_in_data or not obj_in_data["doi"]:
                    # Generate a predictable placeholder based on the OpenAlex ID.
                    placeholder_doi = f"placeholder/oa_{openalex_id}"
                    obj_in_data["doi"] = placeholder_doi
                    logger.info(f"Assigning placeholder DOI '{placeholder_doi}' for new Work OA ID {openalex_id}")

                new_obj = self.model(**obj_in_data) # Create instance.
                self.db.add(new_obj) # Add to session.
                self.db.flush() # Send INSERT.
                self.db.refresh(new_obj) # Load DB defaults.
                logger.info(f"Successfully created and flushed new Work OA ID {openalex_id} (DB ID: {new_obj.id}) with DOI '{new_obj.doi}'")
                return new_obj # Return new instance.

        except SQLAlchemyError as e:
            logger.error(f"SQLAlchemyError during get_or_create_by_openalex_id for Work OA ID {openalex_id}: {e}", exc_info=True)
            # Caller handles rollback.
            raise