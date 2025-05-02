# subfield_repo.py

"""
backend.data.repositories.subfield_repo
---------------------------------------
Provides data access operations for the Subfield model, representing specific
academic subfields, typically nested within Fields (e.g., from OpenAlex).
"""

import logging
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError # General SQLAlchemy exception

from .base_repository import BaseRepository
from backend.data.models import Subfield # The specific SQLAlchemy model

logger = logging.getLogger(__name__)

class SubfieldRepository(BaseRepository[Subfield]):
    """
    Repository managing CRUD and specific queries for Subfield entities.

    Extends BaseRepository for standard operations and includes methods for
    finding subfields by their OpenAlex ID and a get-or-create pattern based on it.
    Handles the relationship to the parent Field entity.
    """

    def __init__(self, db: Session):
        """
        Initializes the SubfieldRepository.

        Args:
            db: The SQLAlchemy Session for database interactions.
        """
        # Initialize the base repository with the Subfield model.
        super().__init__(Subfield, db)

    def get_by_openalex_id(self, *, openalex_id: str) -> Optional[Subfield]:
        """
        Retrieves a Subfield entity using its unique OpenAlex ID.

        Args:
            openalex_id: The OpenAlex ID string (e.g., 'https://openalex.org/S12345')
                         of the subfield to retrieve.

        Returns:
            The Subfield model instance if found, otherwise None.

        Raises:
            SQLAlchemyError: If a database error occurs during the query.
        """
        logger.debug(f"Getting Subfield by openalex_id: {openalex_id}")
        if not self.db.is_active:
            logger.warning(f"Session is inactive in get_by_openalex_id for Subfield OA ID {openalex_id}")
            return None
        try:
            # Standard query filtering by the unique OpenAlex ID.
            return self.db.query(self.model).filter(self.model.openalex_id == openalex_id).first()
        except SQLAlchemyError as e:
            logger.error(f"SQLAlchemyError during get_by_openalex_id for Subfield {openalex_id}: {e}", exc_info=True)
            raise

    def get_or_create_by_openalex_id(
        self, *, openalex_id: str, obj_in_data: Dict[str, Any]
    ) -> Subfield:
        """
        Retrieves a Subfield by OpenAlex ID or creates a new one if it doesn't exist.

        Follows the "Query-First" pattern:
        1. Attempts to fetch the subfield using `get_by_openalex_id`.
        2. If found: Compares attributes in `obj_in_data` (e.g., 'display_name',
           'description', 'field_id'). If differences exist, updates the object
           in the session.
        3. If not found: Creates a new Subfield instance. A valid `field_id` (foreign key
           to the parent Field) *must* be present in `obj_in_data`.
        4. Does NOT commit the transaction; caller is responsible.
        5. Uses `db.flush()` after add/update for early DB interaction and constraint checks.
        6. Uses `db.refresh()` after flush to update the Python object state.

        Args:
            openalex_id: The unique OpenAlex ID to search for or use for creation.
            obj_in_data: Dictionary containing data for the subfield. Must include
                         'field_id' if creating. Other keys ('display_name', 'description')
                         are used for creation or update checks.

        Returns:
            The existing (potentially updated) or newly created Subfield instance,
            managed within the current session and flushed.

        Raises:
            ValueError: If `openalex_id` is missing, or if `field_id` is missing
                        in `obj_in_data` when creating a new Subfield.
            RuntimeError: If the database session is inactive at the start.
            SQLAlchemyError: If any database interaction fails.
        """
        if not openalex_id:
            raise ValueError("openalex_id cannot be empty for Subfield get_or_create")
        if not self.db.is_active:
             logger.error("Session is inactive at start of get_or_create_by_openalex_id for Subfield.")
             raise RuntimeError("Database session is inactive, cannot perform get_or_create.")

        try:
            # --- Step 1: Query First ---
            db_obj = self.get_by_openalex_id(openalex_id=openalex_id)

            if db_obj:
                # --- Step 2a: Record Found - Check for Updates ---
                logger.debug(f"Found existing Subfield OA ID {openalex_id} (DB ID: {db_obj.id}). Checking for updates.")
                updated = False
                # Check and update display name if provided and different.
                if obj_in_data.get('display_name') is not None and db_obj.display_name != obj_in_data.get('display_name'):
                    db_obj.display_name = obj_in_data['display_name']
                    updated = True
                # Check and update description if provided and different.
                if obj_in_data.get('description') is not None and db_obj.description != obj_in_data.get('description'):
                     db_obj.description = obj_in_data['description']
                     updated = True
                # Check if the parent field_id needs updating.
                new_field_id = obj_in_data.get('field_id')
                if new_field_id is not None and db_obj.field_id != new_field_id:
                     logger.warning(f"Subfield OA ID {openalex_id} exists but field_id mismatch detected. "
                                    f"DB has {db_obj.field_id}, input data has {new_field_id}. Updating.")
                     db_obj.field_id = new_field_id
                     updated = True
                # Add other field update checks here if needed...

                if updated:
                    self.db.add(db_obj) # Mark as dirty.
                    logger.info(f"Subfield {db_obj.id} marked for update in the current session.")
                    # Optional: Flush and refresh if immediate state needed by caller.
                    # self.db.flush()
                    # self.db.refresh(db_obj)
                return db_obj # Return the existing instance.

            else:
                 # --- Step 2b: Record Not Found - Create New ---
                logger.debug(f"Subfield OA ID {openalex_id} not found. Preparing to create new.")
                # CRITICAL: Ensure the foreign key `field_id` is present for creation.
                if 'field_id' not in obj_in_data or obj_in_data['field_id'] is None:
                    raise ValueError(f"Missing required 'field_id' in obj_in_data for creating new Subfield with OA ID {openalex_id}")

                # Ensure openalex_id is part of the creation data.
                obj_in_data["openalex_id"] = openalex_id
                new_obj = self.model(**obj_in_data) # Create the instance.
                self.db.add(new_obj) # Add to session.
                # Flush: Send INSERT, get PK, check constraints (including FK to field).
                self.db.flush()
                # Refresh: Update object with DB defaults.
                self.db.refresh(new_obj)
                logger.info(f"Successfully created and flushed new Subfield OA ID {openalex_id} (DB ID: {new_obj.id})")
                return new_obj # Return the new instance.

        except SQLAlchemyError as e:
            logger.error(f"SQLAlchemyError during get_or_create for Subfield OA ID {openalex_id}: {e}", exc_info=True)
            # Caller handles rollback.
            raise # Re-raise the caught exception.