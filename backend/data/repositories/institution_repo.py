# institution_repo.py

"""
backend.data.repositories.institution_repo
------------------------------------------
Provides data access operations for the Institution model, representing
research institutions, universities, etc., often identified by OpenAlex IDs or ROR IDs.
"""

import logging
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError # General SQLAlchemy exception

from .base_repository import BaseRepository
from backend.data.models import Institution # The specific SQLAlchemy model

logger = logging.getLogger(__name__)

class InstitutionRepository(BaseRepository[Institution]):
    """
    Repository managing CRUD and specific queries for Institution entities.

    Handles complexities arising from multiple potential identifiers (OpenAlex ID, ROR ID)
    and provides robust get-or-create methods to manage these, including conflict checks.
    """

    def __init__(self, db: Session):
        """
        Initializes the InstitutionRepository.

        Args:
            db: The SQLAlchemy Session for database interactions.
        """
        # Initialize the base repository with the Institution model.
        super().__init__(Institution, db)

    def get_by_openalex_id(self, *, openalex_id: str) -> Optional[Institution]:
        """
        Retrieves an Institution entity by its unique OpenAlex ID.

        Args:
            openalex_id: The OpenAlex ID string (e.g., 'https://openalex.org/I12345')
                         of the institution.

        Returns:
            The Institution model instance if found, otherwise None.

        Raises:
            SQLAlchemyError: If a database error occurs during the query.
        """
        logger.debug(f"Getting Institution by openalex_id: {openalex_id}")
        if not self.db.is_active:
            logger.warning(f"Session is inactive in get_by_openalex_id for OA ID {openalex_id}")
            return None
        try:
            # Query based on the OpenAlex ID.
            return self.db.query(self.model).filter(self.model.openalex_id == openalex_id).first()
        except SQLAlchemyError as e:
             logger.error(f"SQLAlchemyError during get_by_openalex_id for {openalex_id}: {e}", exc_info=True)
             raise

    def get_by_ror(self, *, ror: str) -> Optional[Institution]:
        """
        Retrieves an Institution entity by its unique ROR ID.

        Args:
            ror: The ROR ID string (e.g., 'https://ror.org/012abcde34') of the institution.

        Returns:
            The Institution model instance if found, otherwise None.

        Raises:
            SQLAlchemyError: If a database error occurs during the query.
        """
        logger.debug(f"Getting Institution by ROR: {ror}")
        if not self.db.is_active:
             logger.warning(f"Session is inactive in get_by_ror for ROR {ror}")
             return None
        try:
            # Query based on the ROR ID.
            return self.db.query(self.model).filter(self.model.ror == ror).first()
        except SQLAlchemyError as e:
             logger.error(f"SQLAlchemyError during get_by_ror for {ror}: {e}", exc_info=True)
             raise

    def get_or_create_by_openalex_id(
        self, *, openalex_id: str, obj_in_data: Dict[str, Any]
    ) -> Institution:
        """
        Retrieves or creates an Institution, prioritizing the OpenAlex ID.

        Handles complex cases involving multiple identifiers (OpenAlex ID, ROR ID):
        1. Attempts to fetch by `openalex_id`.
        2. If found (by OA ID): Updates fields (like ROR, name) if they differ,
           checking for ROR conflicts (i.e., if the new ROR belongs to another existing institution).
        3. If not found by OA ID: Checks if a `ror` is provided in `obj_in_data`.
        4. If ROR provided: Attempts to fetch by `ror`.
        5. If found (by ROR): Updates the existing record, primarily adding the
           `openalex_id` if it was missing, and potentially filling other missing fields.
        6. If not found by OA ID or ROR: Creates a new Institution record using
           `obj_in_data` (ensuring `openalex_id` is set).

        Important:
        - Does NOT commit the transaction; caller is responsible.
        - Uses `db.flush()` and `db.refresh()` after add/update operations.

        Args:
            openalex_id: The primary OpenAlex ID to search for or use for creation.
            obj_in_data: Dictionary with institution data. May include 'ror',
                         'display_name', etc.

        Returns:
            The existing (potentially updated) or newly created Institution instance,
            managed within the session and flushed.

        Raises:
            ValueError: If `openalex_id` is missing.
            RuntimeError: If the session is inactive.
            SQLAlchemyError: If any database operation fails.
        """
        if not openalex_id:
            raise ValueError("openalex_id cannot be empty for Institution get_or_create")
        if not self.db.is_active:
             logger.error("Session is inactive at start of get_or_create_by_openalex_id for Institution.")
             raise RuntimeError("Database session is inactive, cannot perform get_or_create.")

        try:
            # --- Step 1: Query First by OpenAlex ID ---
            db_obj = self.get_by_openalex_id(openalex_id=openalex_id)

            if db_obj:
                 # --- Step 2a: Found by OA ID - Update Check ---
                logger.debug(f"Found existing Institution by OA ID {openalex_id} (DB ID: {db_obj.id}). Checking for updates.")
                updated = False
                new_ror = obj_in_data.get("ror")

                # Update ROR if provided and different, checking for conflicts.
                if new_ror and db_obj.ror != new_ror:
                    if not self.db.is_active: # Re-check session before dependent query
                         raise RuntimeError("Session became inactive before ROR conflict check.")
                    existing_ror_inst = self.get_by_ror(ror=new_ror)
                    if existing_ror_inst and existing_ror_inst.id != db_obj.id:
                        # Log conflict but don't update ROR to avoid unique constraint error.
                        logger.warning(
                            f"Cannot update ROR for Institution OA ID {openalex_id} (DB ID {db_obj.id}) to '{new_ror}' "
                            f"because it is already assigned to Institution DB ID {existing_ror_inst.id}. Skipping ROR update."
                        )
                    else:
                        logger.info(f"Updating ROR for Institution {db_obj.id} from '{db_obj.ror}' to '{new_ror}'")
                        db_obj.ror = new_ror
                        updated = True

                # Update other fields if provided and different.
                if obj_in_data.get('display_name') is not None and db_obj.display_name != obj_in_data.get('display_name'):
                    db_obj.display_name = obj_in_data['display_name']
                    updated = True
                if obj_in_data.get('github_organization_logins') is not None and db_obj.github_organization_logins != obj_in_data.get('github_organization_logins'):
                     db_obj.github_organization_logins = obj_in_data['github_organization_logins']
                     updated = True
                # Add other updatable fields...

                if updated:
                    self.db.add(db_obj) # Mark as dirty.
                    logger.info(f"Institution {db_obj.id} (found by OA ID) marked for update.")
                    # Optional: Flush and refresh.
                    # self.db.flush()
                    # self.db.refresh(db_obj)
                return db_obj # Return the instance found by OA ID.

            else:
                 # --- Step 2b: Not Found by OA ID - Check ROR ---
                ror_to_check = obj_in_data.get("ror")
                if ror_to_check:
                    # --- Step 3: Query by ROR ---
                    db_obj_ror = self.get_by_ror(ror=ror_to_check)
                    if db_obj_ror:
                        # --- Step 4: Found by ROR - Update with OA ID ---
                        logger.warning(f"Institution not found by OA ID {openalex_id}, but found existing "
                                       f"Institution DB ID {db_obj_ror.id} by ROR {ror_to_check}. Attempting to merge/update.")
                        updated = False
                        # Add the OpenAlex ID if it was missing on the record found by ROR.
                        if not db_obj_ror.openalex_id:
                            logger.info(f"Updating missing OA ID for Institution {db_obj_ror.id} (found by ROR {ror_to_check}) to {openalex_id}")
                            db_obj_ror.openalex_id = openalex_id
                            updated = True
                        # Potentially update other fields if they were missing on the ROR-found record.
                        if obj_in_data.get('display_name') is not None and db_obj_ror.display_name is None:
                            db_obj_ror.display_name = obj_in_data['display_name']
                            updated = True
                        if obj_in_data.get('github_organization_logins') is not None and db_obj_ror.github_organization_logins is None:
                            db_obj_ror.github_organization_logins = obj_in_data['github_organization_logins']
                            updated = True
                        # Add other fields...

                        if updated:
                            self.db.add(db_obj_ror) # Mark for update.
                            logger.info(f"Institution {db_obj_ror.id} (found by ROR) marked for update with OA ID {openalex_id}.")
                            # Optional: Flush and refresh.
                            # self.db.flush()
                            # self.db.refresh(db_obj_ror)
                        return db_obj_ror # Return the instance found by ROR.

                # --- Step 5: Not Found by OA ID or ROR - Create New ---
                logger.debug(f"Institution OA ID {openalex_id} (and ROR {ror_to_check or 'N/A'}) not found. Creating new.")
                obj_in_data["openalex_id"] = openalex_id # Ensure OA ID is set.
                new_obj = self.model(**obj_in_data) # Create instance.
                self.db.add(new_obj) # Add to session.
                self.db.flush() # Send INSERT.
                self.db.refresh(new_obj) # Load DB defaults.
                logger.info(f"Successfully created and flushed new Institution OA ID {openalex_id} (DB ID: {new_obj.id})")
                return new_obj # Return the new instance.

        except SQLAlchemyError as e:
            logger.error(f"SQLAlchemyError during get_or_create_by_openalex_id for Inst OA ID {openalex_id}: {e}", exc_info=True)
            # Caller handles rollback.
            raise


    def get_or_create_by_ror(
        self, *, ror: str, obj_in_data: Dict[str, Any]
    ) -> Institution:
        """
        Retrieves or creates an Institution, prioritizing the ROR ID.

        Symmetrical logic to `get_or_create_by_openalex_id`:
        1. Attempts to fetch by `ror`.
        2. If found (by ROR): Updates fields (like OA ID, name) if they differ,
           checking for OpenAlex ID conflicts.
        3. If not found by ROR: Checks if an `openalex_id` is provided.
        4. If OA ID provided: Attempts to fetch by `openalex_id`.
        5. If found (by OA ID): Updates the existing record, primarily adding the
           `ror` if it was missing, and potentially filling other missing fields.
        6. If not found by ROR or OA ID: Creates a new Institution record using
           `obj_in_data` (ensuring `ror` is set).

        Important:
        - Does NOT commit the transaction.
        - Uses `db.flush()` and `db.refresh()`.

        Args:
            ror: The primary ROR ID to search for or use for creation.
            obj_in_data: Dictionary with institution data. May include 'openalex_id',
                         'display_name', etc.

        Returns:
            The existing (potentially updated) or newly created Institution instance,
            managed within the session and flushed.

        Raises:
            ValueError: If `ror` is missing.
            RuntimeError: If the session is inactive.
            SQLAlchemyError: If any database operation fails.
        """
        if not ror:
             raise ValueError("ROR must be provided for get_or_create_by_ror")
        if not self.db.is_active:
             logger.error("Session is inactive at start of get_or_create_by_ror for Institution.")
             raise RuntimeError("Database session is inactive, cannot perform get_or_create.")

        try:
            # --- Step 1: Query First by ROR ---
            db_obj = self.get_by_ror(ror=ror)

            if db_obj:
                 # --- Step 2a: Found by ROR - Update Check ---
                logger.debug(f"Found existing Institution by ROR {ror} (DB ID: {db_obj.id}). Checking for updates.")
                updated = False
                new_oa_id = obj_in_data.get("openalex_id")

                # Update OpenAlex ID if provided and different, checking for conflicts.
                if new_oa_id and db_obj.openalex_id != new_oa_id:
                    if not self.db.is_active: # Re-check session
                         raise RuntimeError("Session inactive before OA ID check during ROR-based update.")
                    existing_oa_inst = self.get_by_openalex_id(openalex_id=new_oa_id)
                    if existing_oa_inst and existing_oa_inst.id != db_obj.id:
                         # Log conflict, skip OA ID update.
                         logger.warning(f"Cannot update OA ID for Institution ROR {ror} (DB ID {db_obj.id}) to {new_oa_id} "
                                        f"because it's already assigned to Institution DB ID {existing_oa_inst.id}. Skipping OA ID update.")
                    else:
                         logger.info(f"Updating OA ID for Institution {db_obj.id} from '{db_obj.openalex_id}' to '{new_oa_id}'")
                         db_obj.openalex_id = new_oa_id
                         updated = True

                # Update other fields if provided and different.
                if obj_in_data.get('display_name') is not None and db_obj.display_name != obj_in_data.get('display_name'):
                    db_obj.display_name = obj_in_data['display_name']
                    updated = True
                if obj_in_data.get('github_organization_logins') is not None and db_obj.github_organization_logins != obj_in_data.get('github_organization_logins'):
                     db_obj.github_organization_logins = obj_in_data['github_organization_logins']
                     updated = True
                # Add other updatable fields ...

                if updated:
                    self.db.add(db_obj) # Mark as dirty.
                    logger.info(f"Institution {db_obj.id} (found by ROR) marked for update.")
                    # Optional: Flush and refresh.
                    # self.db.flush()
                    # self.db.refresh(db_obj)
                return db_obj # Return instance found by ROR.
            else:
                 # --- Step 2b: Not Found by ROR - Check OpenAlex ID ---
                oa_id_to_check = obj_in_data.get("openalex_id")
                if oa_id_to_check:
                    # --- Step 3: Query by OpenAlex ID ---
                    db_obj_oa = self.get_by_openalex_id(openalex_id=oa_id_to_check)
                    if db_obj_oa:
                        # --- Step 4: Found by OA ID - Update with ROR ---
                        logger.warning(f"Institution not found by ROR {ror}, but found existing "
                                       f"Institution DB ID {db_obj_oa.id} by OA ID {oa_id_to_check}. Attempting to merge/update.")
                        updated = False
                        # Add the ROR ID if it was missing.
                        if not db_obj_oa.ror:
                            logger.info(f"Updating missing ROR for Institution {db_obj_oa.id} (found by OA ID {oa_id_to_check}) to {ror}")
                            db_obj_oa.ror = ror
                            updated = True
                        # Potentially update other fields if missing.
                        if obj_in_data.get('display_name') is not None and db_obj_oa.display_name is None:
                            db_obj_oa.display_name = obj_in_data['display_name']
                            updated = True
                        if obj_in_data.get('github_organization_logins') is not None and db_obj_oa.github_organization_logins is None:
                            db_obj_oa.github_organization_logins = obj_in_data['github_organization_logins']
                            updated = True
                        # Add other fields ...

                        if updated:
                            self.db.add(db_obj_oa) # Mark for update.
                            logger.info(f"Institution {db_obj_oa.id} (found by OA ID) marked for update with ROR {ror}.")
                            # Optional: Flush and refresh.
                            # self.db.flush()
                            # self.db.refresh(db_obj_oa)
                        return db_obj_oa # Return instance found by OA ID.

                # --- Step 5: Not Found by ROR or OA ID - Create New ---
                logger.debug(f"Institution ROR {ror} (and OA ID {oa_id_to_check or 'N/A'}) not found. Creating new.")
                obj_in_data["ror"] = ror # Ensure ROR ID is set.
                new_obj = self.model(**obj_in_data) # Create instance.
                self.db.add(new_obj) # Add to session.
                self.db.flush() # Send INSERT.
                self.db.refresh(new_obj) # Load DB defaults.
                logger.info(f"Successfully created and flushed new Institution ROR {ror} (DB ID: {new_obj.id})")
                return new_obj # Return new instance.

        except SQLAlchemyError as e:
            logger.error(f"SQLAlchemyError during get_or_create_by_ror for Inst ROR {ror}: {e}", exc_info=True)
            # Caller handles rollback.
            raise