# domain_repo.py

"""
backend.data.repositories.domain_repo
-------------------------------------
Provides data access operations for the Domain model, representing high-level
academic domains (e.g., from OpenAlex).
"""

import logging
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError # General SQLAlchemy exception

from .base_repository import BaseRepository
from backend.data.models import Domain # The specific SQLAlchemy model

logger = logging.getLogger(__name__)

class DomainRepository(BaseRepository[Domain]):
    """
    Repository dedicated to CRUD and specific query operations for Domain entities.

    Inherits standard CRUD methods and adds specific finders like
    `get_by_openalex_id` and a "get-or-create" method based on the OpenAlex ID.
    """

    def __init__(self, db: Session):
        """
        Initializes the DomainRepository.

        Args:
            db: The SQLAlchemy Session for database interactions.
        """
        # Pass the Domain model and the session to the base class constructor.
        super().__init__(Domain, db)

    def get_by_openalex_id(self, *, openalex_id: str) -> Optional[Domain]:
        """
        Retrieves a Domain entity by its unique OpenAlex ID.

        Args:
            openalex_id: The OpenAlex ID string (e.g., 'https://openalex.org/D12345')
                         of the domain to find.

        Returns:
            The Domain model instance if found, otherwise None.

        Raises:
            SQLAlchemyError: If a database error occurs during the query.
        """
        logger.debug(f"Getting Domain by openalex_id: {openalex_id}")
        # Check session state, helpful for debugging transaction issues.
        if not self.db.is_active:
             logger.warning(f"Session is inactive in get_by_openalex_id for OA ID {openalex_id}")
             return None
        try:
            # Query the Domain model, filtering by the openalex_id column.
            return self.db.query(self.model).filter(self.model.openalex_id == openalex_id).first()
        except SQLAlchemyError as e:
             logger.error(f"SQLAlchemyError during get_by_openalex_id for {openalex_id}: {e}", exc_info=True)
             raise

    def get_or_create_by_openalex_id(
        self, *, openalex_id: str, obj_in_data: Dict[str, Any]
    ) -> Domain:
        """
        Retrieves a Domain by OpenAlex ID or creates a new one if not found.

        Implements the "Query-First" pattern:
        1. Attempts to fetch the domain using `get_by_openalex_id`.
        2. If found, checks `obj_in_data` for differing fields and updates the
           existing record (marks dirty in the session).
        3. If not found, creates a new Domain instance using `obj_in_data`.

        Important Notes:
        - Does NOT commit the transaction; caller handles commit/rollback.
        - Uses `db.flush()` after adding/updating to handle DB interactions early.
        - Uses `db.refresh()` after flush to update the object state.

        Args:
            openalex_id: The unique OpenAlex ID to search for or use for creation.
            obj_in_data: Dictionary containing data for the domain (e.g.,
                         'display_name', 'description'). Used for creation or update checks.

        Returns:
            The existing (potentially updated) or newly created Domain instance,
            added to the session and flushed.

        Raises:
            ValueError: If `openalex_id` is not provided.
            RuntimeError: If the database session is inactive at the start.
            SQLAlchemyError: If any database operation (query, add, flush, refresh) fails.
        """
        if not openalex_id:
            raise ValueError("openalex_id cannot be empty for Domain get_or_create")
        # Ensure the session is active before proceeding.
        if not self.db.is_active:
             logger.error("Session is inactive at start of get_or_create_by_openalex_id for Domain.")
             raise RuntimeError("Database session is inactive, cannot perform get_or_create.")

        try:
            # --- Step 1: Query First ---
            db_obj = self.get_by_openalex_id(openalex_id=openalex_id)

            if db_obj:
                # --- Step 2a: Record Found - Check for Updates ---
                logger.debug(f"Found existing Domain OA ID {openalex_id} (DB ID: {db_obj.id}). Checking for updates.")
                updated = False
                # Compare and update fields if they differ from the input data.
                if obj_in_data.get('display_name') is not None and db_obj.display_name != obj_in_data.get('display_name'):
                    db_obj.display_name = obj_in_data['display_name']
                    updated = True
                if obj_in_data.get('description') is not None and db_obj.description != obj_in_data.get('description'):
                    db_obj.description = obj_in_data['description']
                    updated = True
                # Add checks for other relevant Domain fields if necessary.

                if updated:
                    self.db.add(db_obj) # Mark the object as dirty in the session.
                    logger.info(f"Domain {db_obj.id} marked for update in the current session.")
                    # Optional: Flush here if needed before commit.
                    # self.db.flush()
                    # self.db.refresh(db_obj)
                return db_obj # Return the existing object.

            else:
                # --- Step 2b: Record Not Found - Create New ---
                logger.debug(f"Domain with OA ID {openalex_id} not found. Preparing to create new.")
                # Ensure the openalex_id is set in the data for the new object.
                obj_in_data["openalex_id"] = openalex_id
                new_obj = self.model(**obj_in_data) # Instantiate the new Domain.
                self.db.add(new_obj) # Add to the session.
                # Flush to send INSERT to DB, assign PK, check constraints.
                self.db.flush()
                # Refresh to get any DB-generated values.
                self.db.refresh(new_obj)
                logger.info(f"Successfully created and flushed new Domain OA ID {openalex_id} (DB ID: {new_obj.id})")
                return new_obj # Return the new object.

        except SQLAlchemyError as e:
            logger.error(f"SQLAlchemyError during get_or_create for Domain OA ID {openalex_id}: {e}", exc_info=True)
            # Rollback is the responsibility of the calling context.
            raise # Re-raise the error.