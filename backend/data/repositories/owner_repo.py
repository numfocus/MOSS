# owner_repo.py

"""
backend.data.repositories.owner_repo
------------------------------------
Provides data access operations for the Owner model, representing GitHub
users or organizations that own repositories.
"""

import logging
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError # General SQLAlchemy exception

from .base_repository import BaseRepository
from backend.data.models import Owner # The specific SQLAlchemy model

logger = logging.getLogger(__name__)

class OwnerRepository(BaseRepository[Owner]):
    """
    Repository dedicated to CRUD and specific query operations for Owner entities.

    Handles operations related to GitHub repository owners (Users or Organizations),
    including finding by GitHub ID or login, and a robust get-or-create mechanism.
    """

    def __init__(self, db: Session):
        """
        Initializes the OwnerRepository.

        Args:
            db: The SQLAlchemy Session for database interactions.
        """
        # Pass the Owner model and the session to the base class constructor.
        super().__init__(Owner, db)

    def get_by_github_id(self, *, github_id: int) -> Optional[Owner]:
        """
        Retrieves an owner entity by their unique GitHub ID.

        Args:
            github_id: The GitHub ID of the owner (user or organization) to find.

        Returns:
            The Owner model instance if found, otherwise None.

        Raises:
            SQLAlchemyError: If a database error occurs during the query.
        """
        logger.debug(f"Getting Owner by github_id: {github_id}")
        # Session activity check for debugging transactional issues.
        if not self.db.is_active:
            logger.warning(f"Session is inactive in get_by_github_id for Owner GH ID {github_id}")
            return None
        try:
            # Standard query filtering by the github_id column.
            return self.db.query(self.model).filter(self.model.github_id == github_id).first()
        except SQLAlchemyError as e:
            logger.error(f"SQLAlchemyError during get_by_github_id for Owner {github_id}: {e}", exc_info=True)
            raise

    def get_by_login(self, *, login: str) -> Optional[Owner]:
        """
        Retrieves an owner entity by their GitHub login (username or org name).

        Args:
            login: The GitHub login string of the owner.

        Returns:
            The Owner model instance if found, otherwise None.

        Raises:
            SQLAlchemyError: If a database error occurs during the query.
        """
        logger.debug(f"Getting Owner by login: {login}")
        if not self.db.is_active:
             logger.warning(f"Session is inactive in get_by_login for Owner login '{login}'")
             return None
        try:
            # Query filtering by the login column.
            return self.db.query(self.model).filter(self.model.login == login).first()
        except SQLAlchemyError as e:
             logger.error(f"SQLAlchemyError during get_by_login for Owner {login}: {e}", exc_info=True)
             raise

    def get_or_create_by_github_id(
        self, *, github_id: int, obj_in_data: Dict[str, Any]
    ) -> Owner:
        """
        Retrieves an owner by GitHub ID or creates a new one if not found.

        Implements the "Query-First" or "Get-or-Create" pattern for Owner entities:
        1. Attempts to fetch the owner using `get_by_github_id`.
        2. If found: Checks `obj_in_data` for differing fields (e.g., 'login', 'type',
           'avatar_url', 'html_url'). If the 'login' differs, it checks if the new
           login is already used by a *different* owner to prevent unique constraint
           violations before updating. Updates other differing fields as well.
        3. If not found: Creates a new Owner instance using `obj_in_data`.
        4. Important: This method does NOT commit the transaction. The caller is
           responsible for session management (commit or rollback).
        5. Uses `db.flush()` after adding a new object or marking an existing one
           for update. This assigns primary keys (for new objects) and can help
           detect constraint violations early within the transaction.
        6. `db.refresh()` is called after flush to ensure the Python object
           reflects any database-side changes (like default values).

        Args:
            github_id: The unique GitHub ID to search for or use for creation.
            obj_in_data: Dictionary containing the data for the owner. Must include
                         necessary fields like 'login', 'type'. Other fields like
                         'avatar_url', 'html_url' are used for creation or update.

        Returns:
            The existing (potentially updated) or newly created Owner instance,
            added to the session and flushed.

        Raises:
            ValueError: If `github_id` is not provided.
            RuntimeError: If the database session is inactive when the method starts.
            SQLAlchemyError: If any database operation (query, add, flush, refresh) fails.
                             The caller should handle rollback.
        """
        if not github_id:
             raise ValueError("github_id cannot be empty for Owner get_or_create")
        if not self.db.is_active:
             logger.error("Session is inactive at start of get_or_create_by_github_id for Owner.")
             raise RuntimeError("Database session is inactive, cannot perform get_or_create.")

        try:
            # --- Step 1: Query First ---
            db_obj = self.get_by_github_id(github_id=github_id)

            if db_obj:
                # --- Step 2a: Record Found - Check for Updates ---
                logger.debug(f"Found existing Owner GH ID {github_id} (DB ID: {db_obj.id}). Checking for updates.")
                updated = False
                new_login = obj_in_data.get('login')

                # Check if login needs update and handle potential uniqueness conflicts.
                if new_login and db_obj.login != new_login:
                    if not self.db.is_active: # Re-check session state before next query
                        raise RuntimeError("Session became inactive before login conflict check during owner update.")
                    existing_login_owner = self.get_by_login(login=new_login)
                    if existing_login_owner and existing_login_owner.id != db_obj.id:
                        # Log the conflict but skip the update to avoid DB error.
                        # Consider if raising an error might be more appropriate depending on requirements.
                        logger.warning(
                            f"Cannot update login for Owner GH ID {github_id} (DB ID: {db_obj.id}) to '{new_login}' "
                            f"because it's already assigned to Owner DB ID {existing_login_owner.id}. Skipping login update."
                        )
                    else:
                        logger.info(f"Updating login for Owner {db_obj.id} from '{db_obj.login}' to '{new_login}'")
                        db_obj.login = new_login
                        updated = True

                # Check and update other fields if they differ.
                if obj_in_data.get('type') is not None and db_obj.type != obj_in_data.get('type'):
                    db_obj.type = obj_in_data['type']
                    updated = True
                if obj_in_data.get('avatar_url') is not None and db_obj.avatar_url != obj_in_data.get('avatar_url'):
                     db_obj.avatar_url = obj_in_data['avatar_url']
                     updated = True
                if obj_in_data.get('html_url') is not None and db_obj.html_url != obj_in_data.get('html_url'):
                     db_obj.html_url = obj_in_data['html_url']
                     updated = True
                # Add checks for other relevant fields...

                if updated:
                    self.db.add(db_obj) # Add to session to mark dirty for commit.
                    logger.info(f"Owner {db_obj.id} marked for update in the current session.")
                    # Optional flush/refresh if caller needs immediate DB state.
                    # self.db.flush()
                    # self.db.refresh(db_obj)
                return db_obj # Return the existing (potentially updated) owner.

            else:
                # --- Step 2b: Record Not Found - Create New ---
                logger.debug(f"Owner with GH ID {github_id} not found. Preparing to create new.")
                # Ensure the github_id is included in the data used for creation.
                obj_in_data["github_id"] = github_id
                new_obj = self.model(**obj_in_data) # Create a new model instance.
                self.db.add(new_obj) # Add the new object to the session.
                # Flush the session: sends INSERT, assigns PK, checks constraints.
                self.db.flush()
                # Refresh the instance: loads DB-generated values (e.g., defaults).
                self.db.refresh(new_obj)
                logger.info(f"Successfully created and flushed new Owner GH ID {github_id} (DB ID: {new_obj.id})")
                return new_obj # Return the newly created owner.

        except SQLAlchemyError as e:
            # Log the error encountered during the get_or_create process.
            logger.error(f"SQLAlchemyError during get_or_create for Owner GH ID {github_id}: {e}", exc_info=True)
            # Critical: Do NOT rollback here. The caller manages the transaction.
            # self.db.rollback() # <-- Avoid rollback in repository methods.
            raise # Re-raise the exception for the caller to handle.