# contributor_repo.py

"""
backend.data.repositories.contributor_repo
------------------------------------------
Provides specific data access operations for the Contributor model,
extending the generic BaseRepository.
"""

import logging
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError # General SQLAlchemy exception

from .base_repository import BaseRepository
from backend.data.models import Contributor # The specific SQLAlchemy model

logger = logging.getLogger(__name__)

class ContributorRepository(BaseRepository[Contributor]):
    """
    Repository dedicated to CRUD and specific query operations for Contributor entities.

    Inherits common CRUD methods from BaseRepository and adds methods specific
    to finding contributors based on attributes like GitHub ID or login.
    """

    def __init__(self, db: Session):
        """
        Initializes the ContributorRepository.

        Args:
            db: The SQLAlchemy Session for database interactions.
        """
        # Pass the Contributor model class and the session to the base class.
        super().__init__(Contributor, db)

    def get_by_github_id(self, *, github_id: int) -> Optional[Contributor]:
        """
        Retrieves a contributor entity by their unique GitHub user ID.

        Args:
            github_id: The GitHub ID of the contributor to find.

        Returns:
            The Contributor model instance if found, otherwise None.

        Raises:
            SQLAlchemyError: If a database error occurs during the query.
        """
        logger.debug(f"Getting Contributor by github_id: {github_id}")
        # Basic check if the session is active, useful for debugging transaction issues.
        if not self.db.is_active:
            logger.warning(f"Session is inactive in get_by_github_id for GitHub ID {github_id}")
            # Depending on application logic, could raise an error or return None.
            # Returning None might hide issues, raising might be better in strict contexts.
            return None
        try:
            # Query the Contributor model, filtering by the github_id column.
            return self.db.query(self.model).filter(self.model.github_id == github_id).first()
        except SQLAlchemyError as e:
            logger.error(f"SQLAlchemyError during get_by_github_id for {github_id}: {e}", exc_info=True)
            raise

    def get_by_login(self, *, login: str) -> Optional[Contributor]:
        """
        Retrieves a contributor entity by their GitHub login (username).

        Args:
            login: The GitHub login (case-sensitive, typically) of the contributor.

        Returns:
            The Contributor model instance if found, otherwise None.

        Raises:
            SQLAlchemyError: If a database error occurs during the query.
        """
        logger.debug(f"Getting Contributor by login: {login}")
        if not self.db.is_active:
             logger.warning(f"Session is inactive in get_by_login for login '{login}'")
             return None
        try:
            # Query the Contributor model, filtering by the login column.
            return self.db.query(self.model).filter(self.model.login == login).first()
        except SQLAlchemyError as e:
             logger.error(f"SQLAlchemyError during get_by_login for {login}: {e}", exc_info=True)
             raise

    def get_or_create_by_github_id(
        self, *, github_id: int, obj_in_data: Dict[str, Any]
    ) -> Contributor:
        """
        Retrieves a contributor by GitHub ID or creates a new one if not found.

        This method implements a "Query-First" or "Get-or-Create" pattern.
        It first attempts to fetch the contributor by `github_id`. If found,
        it checks if any fields in `obj_in_data` differ and updates the
        existing record accordingly (marks it dirty in the session). If not found,
        it creates a new contributor instance using `obj_in_data`.

        Important:
            - This method does NOT commit the transaction. The caller is responsible
              for session management (commit or rollback).
            - It uses `db.flush()` after adding a new object or marking an existing
              one for update. This assigns primary keys (for new objects) and
              can help detect constraint violations early within the transaction.
            - `db.refresh()` is called after flush to ensure the Python object
              reflects any database-side changes (like default values or triggers).
            - Handles potential conflicts if updating the `login` to one that
              already exists for a *different* contributor.

        Args:
            github_id: The unique GitHub ID to search for or use for creation.
            obj_in_data: A dictionary containing the data for the contributor.
                         Used for creation or to determine updates if the record exists.
                         Must include necessary fields like 'login', 'type', etc.

        Returns:
            The existing (potentially updated) or newly created Contributor instance,
            added to the session and flushed.

        Raises:
            ValueError: If `github_id` is not provided.
            RuntimeError: If the database session is inactive when the method starts.
            SQLAlchemyError: If any database operation (query, add, flush, refresh) fails.
                             The caller should handle rollback.
        """
        if not github_id:
             raise ValueError("github_id cannot be empty for Contributor get_or_create")
        # Check session state at the beginning. Crucial for transactional integrity.
        if not self.db.is_active:
             logger.error("Session is inactive at start of get_or_create_by_github_id for Contributor.")
             raise RuntimeError("Database session is inactive, cannot perform get_or_create.")

        try:
            # --- Step 1: Query First ---
            db_obj = self.get_by_github_id(github_id=github_id)

            if db_obj:
                # --- Step 2a: Record Found - Check for Updates ---
                logger.debug(f"Found existing Contributor GH ID {github_id} (DB ID: {db_obj.id}). Checking for updates.")
                updated = False
                new_login = obj_in_data.get('login')

                # Check if login needs update and handle potential uniqueness conflicts.
                if new_login and db_obj.login != new_login:
                    if not self.db.is_active: # Re-check session before subsequent query
                        raise RuntimeError("Session became inactive before login conflict check during update.")
                    existing_login_contributor = self.get_by_login(login=new_login)
                    if existing_login_contributor and existing_login_contributor.id != db_obj.id:
                        # Log a warning but proceed without changing the login to avoid unique constraint error.
                        # Alternatively, could raise an error here depending on desired behavior.
                        logger.warning(
                            f"Cannot update login for Contributor GH ID {github_id} to '{new_login}' "
                            f"because it's already assigned to Contributor DB ID {existing_login_contributor.id}. Skipping login update."
                        )
                    else:
                        logger.info(f"Updating login for Contributor {db_obj.id} from '{db_obj.login}' to '{new_login}'")
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
                # Add checks for other relevant fields here...

                if updated:
                    # Add the modified object to the session to mark it for update on commit.
                    self.db.add(db_obj)
                    logger.info(f"Contributor {db_obj.id} marked for update in the current session.")
                    # Optional: Flush here if the caller needs the updated state
                    # reflected in the DB *before* the final commit.
                    # self.db.flush()
                    # self.db.refresh(db_obj) # Refresh if flushed
                return db_obj # Return the existing (potentially updated) object.

            else:
                # --- Step 2b: Record Not Found - Create New ---
                logger.debug(f"Contributor with GH ID {github_id} not found. Preparing to create new.")
                # Ensure the github_id is included in the data used for creation.
                obj_in_data["github_id"] = github_id
                # Create a new model instance.
                new_obj = self.model(**obj_in_data)
                self.db.add(new_obj) # Add the new object to the session.
                # Flush the session to send the INSERT statement to the database.
                # This assigns the primary key (if auto-generated) and checks constraints.
                self.db.flush()
                # Refresh the instance to load any database-generated values (e.g., defaults).
                self.db.refresh(new_obj)
                logger.info(f"Successfully created and flushed new Contributor GH ID {github_id} (DB ID: {new_obj.id})")
                return new_obj # Return the newly created object.

        except SQLAlchemyError as e:
            # Log the error occurred during the get_or_create process.
            logger.error(f"SQLAlchemyError during get_or_create for Contributor GH ID {github_id}: {e}", exc_info=True)
            # Critical: Do NOT rollback here. The caller manages the transaction boundary.
            # self.db.rollback() # <-- DO NOT DO THIS HERE
            raise # Re-raise the exception for the caller to handle.