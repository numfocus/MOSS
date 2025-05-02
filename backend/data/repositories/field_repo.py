# field_repo.py

"""
backend.data.repositories.field_repo
------------------------------------
Provides data access operations for the Field model, representing academic
fields of study, often nested within Domains (e.g., from OpenAlex).
"""

import logging
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError # General SQLAlchemy exception

from .base_repository import BaseRepository
from backend.data.models import Field # The specific SQLAlchemy model

logger = logging.getLogger(__name__)

class FieldRepository(BaseRepository[Field]):
    """
    Repository managing CRUD and specific queries for Field entities.

    Extends BaseRepository for standard operations and includes methods for
    finding fields by their OpenAlex ID and a get-or-create pattern based on it.
    """

    def __init__(self, db: Session):
        """
        Initializes the FieldRepository.

        Args:
            db: The SQLAlchemy Session for database interactions.
        """
        # Initialize the base repository with the Field model and the database session.
        super().__init__(Field, db)

    def get_by_openalex_id(self, *, openalex_id: str) -> Optional[Field]:
        """
        Retrieves a Field entity using its unique OpenAlex ID.

        Args:
            openalex_id: The OpenAlex ID string (e.g., 'https://openalex.org/F12345')
                         of the field to retrieve.

        Returns:
            The Field model instance if found, otherwise None.

        Raises:
            SQLAlchemyError: If a database error occurs during the query.
        """
        logger.debug(f"Getting Field by openalex_id: {openalex_id}")
        # Pre-check for active session can help diagnose transaction issues.
        if not self.db.is_active:
            logger.warning(f"Session is inactive in get_by_openalex_id for OA ID {openalex_id}")
            return None
        try:
            # Standard query filtering by the unique OpenAlex ID.
            return self.db.query(self.model).filter(self.model.openalex_id == openalex_id).first()
        except SQLAlchemyError as e:
             logger.error(f"SQLAlchemyError during get_by_openalex_id for {openalex_id}: {e}", exc_info=True)
             raise

    def get_or_create_by_openalex_id(
        self, *, openalex_id: str, obj_in_data: Dict[str, Any]
    ) -> Field:
        """
        Retrieves a Field by OpenAlex ID or creates a new one if it doesn't exist.

        This method follows the "Query-First" or "Get-or-Create" pattern:
        1. Attempts to fetch the field using `get_by_openalex_id`.
        2. If found, it compares attributes in `obj_in_data` with the existing
           object. If differences are found (e.g., in 'display_name', 'description',
           or even 'domain_id'), it updates the existing object in the session.
        3. If not found, it creates a new Field instance. A valid `domain_id`
           *must* be present in `obj_in_data` for creation to succeed.
        4. The operation does NOT commit the transaction; the caller is responsible
           for session commit or rollback.
        5. `db.flush()` is used after adding or updating to synchronize with the DB
           and potentially raise constraint errors early.
        6. `db.refresh()` ensures the Python object reflects the latest state from
           the DB after flushing (e.g., loading default values).

        Args:
            openalex_id: The unique OpenAlex ID to search for or use for creation.
            obj_in_data: Dictionary containing the data for the field. Must include
                         'domain_id' if creating a new field. Other keys like
                         'display_name', 'description' are used for creation or update checks.

        Returns:
            The existing (potentially updated) or newly created Field instance,
            managed within the current session and flushed.

        Raises:
            ValueError: If `openalex_id` is missing, or if `domain_id` is missing
                        in `obj_in_data` when creating a new Field.
            RuntimeError: If the database session is inactive when the method is called.
            SQLAlchemyError: If any database interaction (query, add, flush, refresh) fails.
        """
        if not openalex_id:
            raise ValueError("openalex_id cannot be empty for Field get_or_create")
        # Ensure the session is usable at the start.
        if not self.db.is_active:
             logger.error("Session is inactive at start of get_or_create_by_openalex_id for Field.")
             raise RuntimeError("Database session is inactive, cannot perform get_or_create.")

        try:
            # --- Step 1: Query First ---
            db_obj = self.get_by_openalex_id(openalex_id=openalex_id)

            if db_obj:
                # --- Step 2a: Record Found - Check for Updates ---
                logger.debug(f"Found existing Field OA ID {openalex_id} (DB ID: {db_obj.id}). Checking for updates.")
                updated = False
                # Check and update display name if provided and different.
                if obj_in_data.get('display_name') is not None and db_obj.display_name != obj_in_data.get('display_name'):
                    db_obj.display_name = obj_in_data['display_name']
                    updated = True
                # Check and update description if provided and different.
                if obj_in_data.get('description') is not None and db_obj.description != obj_in_data.get('description'):
                     db_obj.description = obj_in_data['description']
                     updated = True
                # Check if the parent domain_id needs updating (less common, but possible).
                new_domain_id = obj_in_data.get('domain_id')
                if new_domain_id is not None and db_obj.domain_id != new_domain_id:
                     logger.warning(f"Field OA ID {openalex_id} exists but domain_id mismatch detected. "
                                    f"DB has {db_obj.domain_id}, input data has {new_domain_id}. Updating.")
                     db_obj.domain_id = new_domain_id
                     updated = True
                # Add other field update checks here if needed...

                if updated:
                    self.db.add(db_obj) # Mark as dirty in the session.
                    logger.info(f"Field {db_obj.id} marked for update in the current session.")
                    # Optional: Flush and refresh if immediate DB state is needed by caller before commit.
                    # self.db.flush()
                    # self.db.refresh(db_obj)
                return db_obj # Return the existing instance.

            else:
                # --- Step 2b: Record Not Found - Create New ---
                logger.debug(f"Field OA ID {openalex_id} not found. Preparing to create new.")
                # Crucial check: Ensure the foreign key `domain_id` is provided for creation.
                if 'domain_id' not in obj_in_data or obj_in_data['domain_id'] is None:
                    raise ValueError(f"Missing required 'domain_id' in obj_in_data for creating new Field with OA ID {openalex_id}")

                # Ensure the openalex_id is part of the creation data.
                obj_in_data["openalex_id"] = openalex_id
                new_obj = self.model(**obj_in_data) # Create the instance.
                self.db.add(new_obj) # Add to session.
                # Flush: Send INSERT, get PK, check constraints.
                self.db.flush()
                # Refresh: Update object with DB defaults.
                self.db.refresh(new_obj)
                logger.info(f"Successfully created and flushed new Field OA ID {openalex_id} (DB ID: {new_obj.id})")
                return new_obj # Return the new instance.

        except SQLAlchemyError as e:
            logger.error(f"SQLAlchemyError during get_or_create for Field OA ID {openalex_id}: {e}", exc_info=True)
            # Let the caller handle transaction rollback.
            raise # Re-raise the caught exception.