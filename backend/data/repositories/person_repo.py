# person_repo.py

"""
backend.data.repositories.person_repo
-------------------------------------
Provides data access operations for the Person model, representing individuals,
often identified through academic identifiers like OpenAlex IDs or ORCIDs.
"""

import logging
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError # General SQLAlchemy exception

from .base_repository import BaseRepository
from backend.data.models import Person # The specific SQLAlchemy model

logger = logging.getLogger(__name__)

class PersonRepository(BaseRepository[Person]):
    """
    Repository for managing Person entities, including CRUD and specific queries.

    Handles complexities arising from multiple potential identifiers (OpenAlex ID, ORCID)
    and provides robust get-or-create methods to manage these, including conflict checks.
    """

    def __init__(self, db: Session):
        """
        Initializes the PersonRepository.

        Args:
            db: The SQLAlchemy Session for database interactions.
        """
        # Pass the Person model and session to the base repository.
        super().__init__(Person, db)

    def get_by_openalex_id(self, *, openalex_id: str) -> Optional[Person]:
        """
        Retrieves a Person entity by their unique OpenAlex ID.

        Args:
            openalex_id: The OpenAlex ID string (e.g., 'https://openalex.org/A12345')
                         of the person.

        Returns:
            The Person model instance if found, otherwise None.

        Raises:
            SQLAlchemyError: If a database error occurs during the query.
        """
        logger.debug(f"Getting Person by openalex_id: {openalex_id}")
        if not self.db.is_active:
            logger.warning(f"Session is inactive in get_by_openalex_id for Person OA ID {openalex_id}")
            return None
        try:
            # Query based on the OpenAlex ID.
            return self.db.query(self.model).filter(self.model.openalex_id == openalex_id).first()
        except SQLAlchemyError as e:
            logger.error(f"SQLAlchemyError during get_by_openalex_id for Person {openalex_id}: {e}", exc_info=True)
            raise

    def get_by_orcid(self, *, orcid: str) -> Optional[Person]:
        """
        Retrieves a Person entity by their ORCID.

        Args:
            orcid: The ORCID string (e.g., '0000-0001-2345-6789') of the person.

        Returns:
            The Person model instance if found, otherwise None.

        Raises:
            SQLAlchemyError: If a database error occurs during the query.
        """
        logger.debug(f"Getting Person by orcid: {orcid}")
        if not self.db.is_active:
            logger.warning(f"Session is inactive in get_by_orcid for Person ORCID {orcid}")
            return None
        try:
            # Query based on the ORCID. Assumes ORCID is unique or the first match is desired.
            return self.db.query(self.model).filter(self.model.orcid == orcid).first()
        except SQLAlchemyError as e:
            logger.error(f"SQLAlchemyError during get_by_orcid for Person {orcid}: {e}", exc_info=True)
            raise

    def get_or_create_by_openalex_id(
        self, *, openalex_id: str, obj_in_data: Dict[str, Any]
    ) -> Person:
        """
        Retrieves or creates a Person, prioritizing the OpenAlex ID.

        Handles logic for entities potentially identifiable by OpenAlex ID or ORCID:
        1. Attempts to fetch by `openalex_id`.
        2. If found (by OA ID): Updates fields (like ORCID, name) if they differ,
           checking for ORCID conflicts (i.e., if the new ORCID belongs to another existing person).
        3. If not found by OA ID: Checks if an `orcid` is provided in `obj_in_data`.
        4. If ORCID provided: Attempts to fetch by `orcid`.
        5. If found (by ORCID): Updates the existing record, primarily adding the
           `openalex_id` if it was missing, and potentially filling other missing fields.
        6. If not found by OA ID or ORCID: Creates a new Person record using
           `obj_in_data` (ensuring `openalex_id` is set).

        Important:
        - Does NOT commit the transaction; caller is responsible.
        - Uses `db.flush()` and `db.refresh()` after add/update operations.

        Args:
            openalex_id: The primary OpenAlex ID to search for or use for creation.
            obj_in_data: Dictionary with person data. May include 'orcid',
                         'display_name', 'display_name_alternatives', etc.

        Returns:
            The existing (potentially updated) or newly created Person instance,
            managed within the session and flushed.

        Raises:
            ValueError: If `openalex_id` is missing.
            RuntimeError: If the session is inactive.
            SQLAlchemyError: If any database operation fails.
        """
        if not openalex_id:
            raise ValueError("openalex_id cannot be empty for Person get_or_create")
        if not self.db.is_active:
             logger.error("Session is inactive at start of get_or_create_by_openalex_id for Person.")
             raise RuntimeError("Database session is inactive, cannot perform get_or_create.")

        try:
            # --- Step 1: Query First by OpenAlex ID ---
            db_obj = self.get_by_openalex_id(openalex_id=openalex_id)

            if db_obj:
                # --- Step 2a: Found by OA ID - Update Check ---
                logger.debug(f"Found existing Person by OA ID {openalex_id} (DB ID: {db_obj.id}). Checking for updates.")
                updated = False
                new_orcid = obj_in_data.get("orcid")

                # Update ORCID if provided and different, checking for conflicts.
                if new_orcid and db_obj.orcid != new_orcid:
                     if not self.db.is_active: # Re-check session before dependent query
                          raise RuntimeError("Session became inactive before ORCID conflict check.")
                     existing_orcid_person = self.get_by_orcid(orcid=new_orcid)
                     if existing_orcid_person and existing_orcid_person.id != db_obj.id:
                          # Log conflict but don't update ORCID to avoid unique constraint error.
                          logger.warning(
                              f"Cannot update ORCID for Person OA ID {openalex_id} (DB ID {db_obj.id}) to '{new_orcid}' "
                              f"because it is already assigned to Person DB ID {existing_orcid_person.id}. Skipping ORCID update."
                          )
                     else:
                          logger.info(f"Updating ORCID for Person {db_obj.id} from '{db_obj.orcid}' to '{new_orcid}'")
                          db_obj.orcid = new_orcid
                          updated = True

                # Update other fields if provided and different.
                if obj_in_data.get('display_name') is not None and db_obj.display_name != obj_in_data.get('display_name'):
                    db_obj.display_name = obj_in_data['display_name']
                    updated = True
                # Note: Comparing JSON fields requires careful handling depending on DB backend and exact structure.
                if obj_in_data.get('display_name_alternatives') is not None and db_obj.display_name_alternatives != obj_in_data.get('display_name_alternatives'):
                     db_obj.display_name_alternatives = obj_in_data['display_name_alternatives']
                     updated = True
                # Add other updatable fields...

                if updated:
                    self.db.add(db_obj) # Mark as dirty.
                    logger.info(f"Person {db_obj.id} (found by OA ID) marked for update.")
                    # Optional: Flush and refresh.
                    # self.db.flush()
                    # self.db.refresh(db_obj)
                return db_obj # Return the instance found by OA ID.

            else:
                # --- Step 2b: Not Found by OA ID - Check ORCID ---
                orcid_to_check = obj_in_data.get("orcid")
                if orcid_to_check:
                    # --- Step 3: Query by ORCID ---
                    db_obj_orcid = self.get_by_orcid(orcid=orcid_to_check)
                    if db_obj_orcid:
                        # --- Step 4: Found by ORCID - Update with OA ID ---
                        logger.warning(f"Person not found by OA ID {openalex_id}, but found existing "
                                       f"Person DB ID {db_obj_orcid.id} by ORCID {orcid_to_check}. Attempting to merge/update.")
                        updated = False
                        # Add the OpenAlex ID if it was missing on the record found by ORCID.
                        if not db_obj_orcid.openalex_id:
                            logger.info(f"Updating missing OA ID for Person {db_obj_orcid.id} (found by ORCID {orcid_to_check}) to {openalex_id}")
                            db_obj_orcid.openalex_id = openalex_id
                            updated = True
                        # Potentially update other fields if they were missing on the ORCID-found record.
                        if obj_in_data.get('display_name') is not None and db_obj_orcid.display_name is None:
                            db_obj_orcid.display_name = obj_in_data['display_name']
                            updated = True
                        if obj_in_data.get('display_name_alternatives') is not None and db_obj_orcid.display_name_alternatives is None:
                             db_obj_orcid.display_name_alternatives = obj_in_data['display_name_alternatives']
                             updated = True
                        # Add other fields...

                        if updated:
                            self.db.add(db_obj_orcid) # Mark for update.
                            logger.info(f"Person {db_obj_orcid.id} (found by ORCID) marked for update with OA ID {openalex_id}.")
                            # Optional: Flush and refresh.
                            # self.db.flush()
                            # self.db.refresh(db_obj_orcid)
                        return db_obj_orcid # Return the instance found by ORCID.

                # --- Step 5: Not Found by OA ID or ORCID - Create New ---
                logger.debug(f"Person OA ID {openalex_id} (and ORCID {orcid_to_check or 'N/A'}) not found. Creating new.")
                obj_in_data["openalex_id"] = openalex_id # Ensure OA ID is set.
                new_obj = self.model(**obj_in_data) # Create instance.
                self.db.add(new_obj) # Add to session.
                self.db.flush() # Send INSERT.
                self.db.refresh(new_obj) # Load DB defaults.
                logger.info(f"Successfully created and flushed new Person OA ID {openalex_id} (DB ID: {new_obj.id})")
                return new_obj # Return the new instance.

        except SQLAlchemyError as e:
            logger.error(f"SQLAlchemyError during get_or_create_by_openalex_id for Person OA ID {openalex_id}: {e}", exc_info=True)
            # Caller handles rollback.
            raise

    def get_or_create_by_orcid(
        self, *, orcid: str, obj_in_data: Dict[str, Any]
    ) -> Person:
        """
        Retrieves or creates a Person, prioritizing the ORCID.

        Symmetrical logic to `get_or_create_by_openalex_id`:
        1. Attempts to fetch by `orcid`.
        2. If found (by ORCID): Updates fields (like OA ID, name) if they differ,
           checking for OpenAlex ID conflicts.
        3. If not found by ORCID: Checks if an `openalex_id` is provided.
        4. If OA ID provided: Attempts to fetch by `openalex_id`.
        5. If found (by OA ID): Updates the existing record, primarily adding the
           `orcid` if it was missing, and potentially filling other missing fields.
        6. If not found by ORCID or OA ID: Creates a new Person record using
           `obj_in_data` (ensuring `orcid` is set).

        Important:
        - Does NOT commit the transaction.
        - Uses `db.flush()` and `db.refresh()`.

        Args:
            orcid: The primary ORCID to search for or use for creation.
            obj_in_data: Dictionary with person data. May include 'openalex_id',
                         'display_name', etc.

        Returns:
            The existing (potentially updated) or newly created Person instance,
            managed within the session and flushed.

        Raises:
            ValueError: If `orcid` is missing.
            RuntimeError: If the session is inactive.
            SQLAlchemyError: If any database operation fails.
        """
        if not orcid:
             raise ValueError("ORCID must be provided for get_or_create_by_orcid")
        if not self.db.is_active:
             logger.error("Session is inactive at start of get_or_create_by_orcid for Person.")
             raise RuntimeError("Database session is inactive, cannot perform get_or_create.")

        try:
            # --- Step 1: Query First by ORCID ---
            db_obj = self.get_by_orcid(orcid=orcid)

            if db_obj:
                # --- Step 2a: Found by ORCID - Update Check ---
                logger.debug(f"Found existing Person by ORCID {orcid} (DB ID: {db_obj.id}). Checking for updates.")
                updated = False
                new_oa_id = obj_in_data.get("openalex_id")

                # Update OpenAlex ID if provided and different, checking for conflicts.
                if new_oa_id and db_obj.openalex_id != new_oa_id:
                    if not self.db.is_active: # Re-check session
                         raise RuntimeError("Session inactive before OA ID check during ORCID-based update.")
                    existing_oa_person = self.get_by_openalex_id(openalex_id=new_oa_id)
                    if existing_oa_person and existing_oa_person.id != db_obj.id:
                        # Log conflict, skip OA ID update.
                        logger.warning(f"Cannot update OA ID for Person ORCID {orcid} (DB ID {db_obj.id}) to {new_oa_id} "
                                       f"because it's already assigned to Person DB ID {existing_oa_person.id}. Skipping OA ID update.")
                    else:
                        logger.info(f"Updating OA ID for Person {db_obj.id} from '{db_obj.openalex_id}' to '{new_oa_id}'")
                        db_obj.openalex_id = new_oa_id
                        updated = True

                # Update other fields if provided and different.
                if obj_in_data.get('display_name') is not None and db_obj.display_name != obj_in_data.get('display_name'):
                    db_obj.display_name = obj_in_data['display_name']
                    updated = True
                if obj_in_data.get('display_name_alternatives') is not None and db_obj.display_name_alternatives != obj_in_data.get('display_name_alternatives'):
                     db_obj.display_name_alternatives = obj_in_data['display_name_alternatives']
                     updated = True
                # Add other updatable fields ...

                if updated:
                    self.db.add(db_obj) # Mark as dirty.
                    logger.info(f"Person {db_obj.id} (found by ORCID) marked for update.")
                    # Optional: Flush and refresh.
                    # self.db.flush()
                    # self.db.refresh(db_obj)
                return db_obj # Return instance found by ORCID.
            else:
                 # --- Step 2b: Not Found by ORCID - Check OpenAlex ID ---
                oa_id_to_check = obj_in_data.get("openalex_id")
                if oa_id_to_check:
                    # --- Step 3: Query by OpenAlex ID ---
                    db_obj_oa = self.get_by_openalex_id(openalex_id=oa_id_to_check)
                    if db_obj_oa:
                        # --- Step 4: Found by OA ID - Update with ORCID ---
                        logger.warning(f"Person not found by ORCID {orcid}, but found existing "
                                       f"Person DB ID {db_obj_oa.id} by OA ID {oa_id_to_check}. Attempting to merge/update.")
                        updated = False
                        # Add the ORCID if it was missing.
                        if not db_obj_oa.orcid:
                            logger.info(f"Updating missing ORCID for Person {db_obj_oa.id} (found by OA ID {oa_id_to_check}) to {orcid}")
                            db_obj_oa.orcid = orcid
                            updated = True
                        # Potentially update other fields if missing.
                        if obj_in_data.get('display_name') is not None and db_obj_oa.display_name is None:
                            db_obj_oa.display_name = obj_in_data['display_name']
                            updated = True
                        if obj_in_data.get('display_name_alternatives') is not None and db_obj_oa.display_name_alternatives is None:
                             db_obj_oa.display_name_alternatives = obj_in_data['display_name_alternatives']
                             updated = True
                        # Add other fields ...

                        if updated:
                            self.db.add(db_obj_oa) # Mark for update.
                            logger.info(f"Person {db_obj_oa.id} (found by OA ID) marked for update with ORCID {orcid}.")
                            # Optional: Flush and refresh.
                            # self.db.flush()
                            # self.db.refresh(db_obj_oa)
                        return db_obj_oa # Return instance found by OA ID.

                # --- Step 5: Not Found by ORCID or OA ID - Create New ---
                logger.debug(f"Person ORCID {orcid} (and OA ID {oa_id_to_check or 'N/A'}) not found. Creating new.")
                obj_in_data["orcid"] = orcid # Ensure ORCID is set.
                new_obj = self.model(**obj_in_data) # Create instance.
                self.db.add(new_obj) # Add to session.
                self.db.flush() # Send INSERT.
                self.db.refresh(new_obj) # Load DB defaults.
                logger.info(f"Successfully created and flushed new Person ORCID {orcid} (DB ID: {new_obj.id})")
                return new_obj # Return new instance.

        except SQLAlchemyError as e:
            logger.error(f"SQLAlchemyError during get_or_create_by_orcid for Person ORCID {orcid}: {e}", exc_info=True)
            # Caller handles rollback.
            raise