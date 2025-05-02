# topic_repo.py

"""
backend.data.repositories.topic_repo
------------------------------------
Provides data access operations for the Topic model, representing fine-grained
academic topics, typically nested within Subfields (e.g., from OpenAlex).
"""

import logging
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError # General SQLAlchemy exception

from .base_repository import BaseRepository
from backend.data.models import Topic # The specific SQLAlchemy model

logger = logging.getLogger(__name__)

class TopicRepository(BaseRepository[Topic]):
    """
    Repository managing CRUD and specific queries for Topic entities.

    Extends BaseRepository for standard operations and includes methods for
    finding topics by their OpenAlex ID and a get-or-create pattern based on it.
    Handles the relationship to the parent Subfield entity.
    """

    def __init__(self, db: Session):
        """
        Initializes the TopicRepository.

        Args:
            db: The SQLAlchemy Session for database interactions.
        """
        # Initialize the base repository with the Topic model.
        super().__init__(Topic, db)

    def get_by_openalex_id(self, *, openalex_id: str) -> Optional[Topic]:
        """
        Retrieves a Topic entity using its unique OpenAlex ID.

        Args:
            openalex_id: The OpenAlex ID string (e.g., 'https://openalex.org/T12345')
                         of the topic to retrieve.

        Returns:
            The Topic model instance if found, otherwise None.

        Raises:
            SQLAlchemyError: If a database error occurs during the query.
        """
        logger.debug(f"Getting Topic by openalex_id: {openalex_id}")
        if not self.db.is_active:
            logger.warning(f"Session is inactive in get_by_openalex_id for Topic OA ID {openalex_id}")
            return None
        try:
            # Standard query filtering by the unique OpenAlex ID.
            return self.db.query(self.model).filter(self.model.openalex_id == openalex_id).first()
        except SQLAlchemyError as e:
            logger.error(f"SQLAlchemyError during get_by_openalex_id for Topic {openalex_id}: {e}", exc_info=True)
            raise

    def get_or_create_by_openalex_id(
        self, *, openalex_id: str, obj_in_data: Dict[str, Any]
    ) -> Topic:
        """
        Retrieves a Topic by OpenAlex ID or creates a new one if it doesn't exist.

        Follows the "Query-First" pattern:
        1. Attempts to fetch the topic using `get_by_openalex_id`.
        2. If found: Compares attributes in `obj_in_data` (e.g., 'display_name',
           'description', 'subfield_id'). If differences exist, updates the object
           in the session.
        3. If not found: Creates a new Topic instance. A valid `subfield_id` (foreign key
           to the parent Subfield) *must* be present in `obj_in_data`.
        4. Does NOT commit the transaction; caller is responsible.
        5. Uses `db.flush()` after add/update for early DB interaction and constraint checks.
        6. Uses `db.refresh()` after flush to update the Python object state.

        Args:
            openalex_id: The unique OpenAlex ID to search for or use for creation.
            obj_in_data: Dictionary containing data for the topic. Must include
                         'subfield_id' if creating. Other keys ('display_name', 'description')
                         are used for creation or update checks.

        Returns:
            The existing (potentially updated) or newly created Topic instance,
            managed within the current session and flushed.

        Raises:
            ValueError: If `openalex_id` is missing, or if `subfield_id` is missing
                        in `obj_in_data` when creating a new Topic.
            RuntimeError: If the database session is inactive at the start.
            SQLAlchemyError: If any database interaction fails.
        """
        if not openalex_id:
            raise ValueError("openalex_id cannot be empty for Topic get_or_create")
        if not self.db.is_active:
             logger.error("Session is inactive at start of get_or_create_by_openalex_id for Topic.")
             raise RuntimeError("Database session is inactive, cannot perform get_or_create.")

        try:
            # --- Step 1: Query First ---
            db_obj = self.get_by_openalex_id(openalex_id=openalex_id)

            if db_obj:
                # --- Step 2a: Record Found - Check for Updates ---
                logger.debug(f"Found existing Topic OA ID {openalex_id} (DB ID: {db_obj.id}). Checking for updates.")
                updated = False
                # Check and update display name if provided and different.
                if obj_in_data.get('display_name') is not None and db_obj.display_name != obj_in_data.get('display_name'):
                    db_obj.display_name = obj_in_data['display_name']
                    updated = True
                # Check and update description if provided and different.
                if obj_in_data.get('description') is not None and db_obj.description != obj_in_data.get('description'):
                     db_obj.description = obj_in_data['description']
                     updated = True
                # Check if the parent subfield_id needs updating.
                new_subfield_id = obj_in_data.get('subfield_id')
                if new_subfield_id is not None and db_obj.subfield_id != new_subfield_id:
                     logger.warning(f"Topic OA ID {openalex_id} exists but subfield_id mismatch detected. "
                                    f"DB has {db_obj.subfield_id}, input data has {new_subfield_id}. Updating.")
                     db_obj.subfield_id = new_subfield_id
                     updated = True
                # Add other field update checks here if needed...

                if updated:
                    self.db.add(db_obj) # Mark as dirty.
                    logger.info(f"Topic {db_obj.id} marked for update in the current session.")
                    # Optional: Flush and refresh if immediate state needed by caller.
                    # self.db.flush()
                    # self.db.refresh(db_obj)
                return db_obj # Return the existing instance.
            else:
                 # --- Step 2b: Record Not Found - Create New ---
                logger.debug(f"Topic OA ID {openalex_id} not found. Preparing to create new.")
                # CRITICAL: Ensure the foreign key `subfield_id` is present for creation.
                if 'subfield_id' not in obj_in_data or obj_in_data['subfield_id'] is None:
                     raise ValueError(f"Missing required 'subfield_id' in obj_in_data for creating new Topic with OA ID {openalex_id}")

                # Ensure openalex_id is part of the creation data.
                obj_in_data["openalex_id"] = openalex_id
                new_obj = self.model(**obj_in_data) # Create the instance.
                self.db.add(new_obj) # Add to session.
                # Flush: Send INSERT, get PK, check constraints (including FK to subfield).
                self.db.flush()
                # Refresh: Update object with DB defaults.
                self.db.refresh(new_obj)
                logger.info(f"Successfully created and flushed new Topic OA ID {openalex_id} (DB ID: {new_obj.id})")
                return new_obj # Return the new instance.

        except SQLAlchemyError as e:
            logger.error(f"SQLAlchemyError during get_or_create for Topic OA ID {openalex_id}: {e}", exc_info=True)
            # Caller handles rollback.
            raise # Re-raise the caught exception.