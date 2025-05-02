# repository_repo.py

"""
backend.data.repositories.repository_repo
-----------------------------------------
Provides data access operations for the Repository model, representing source
code repositories (e.g., from GitHub).
"""

import logging
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError # General SQLAlchemy exception

from .base_repository import BaseRepository
from backend.data.models import Repository, Owner # Import Owner for relationship handling

logger = logging.getLogger(__name__)

class RepositoryRepository(BaseRepository[Repository]):
    """
    Repository for managing Repository entities, including CRUD and specific queries.

    Extends the generic BaseRepository and adds methods tailored for repositories,
    such as finding by GitHub ID or full name, and implementing a robust
    get-or-create pattern that handles the relationship with the Owner entity.
    """

    def __init__(self, db: Session):
        """
        Initializes the RepositoryRepository.

        Args:
            db: The SQLAlchemy Session for database interactions.
        """
        super().__init__(Repository, db)

    def get_by_github_id(self, *, github_id: int) -> Optional[Repository]:
        """
        Retrieves a repository entity by its unique GitHub repository ID.

        Args:
            github_id: The GitHub ID of the repository to find.

        Returns:
            The Repository model instance if found, otherwise None.

        Raises:
            SQLAlchemyError: If a database error occurs during the query.
        """
        logger.debug(f"Getting Repository by github_id: {github_id}")
        if not self.db.is_active:
            logger.warning(f"Session is inactive in get_by_github_id for Repository GH ID {github_id}")
            return None
        try:
            # Standard query filtering by the unique github_id.
            return self.db.query(self.model).filter(self.model.github_id == github_id).first()
        except SQLAlchemyError as e:
            logger.error(f"SQLAlchemyError during get_by_github_id for Repository {github_id}: {e}", exc_info=True)
            raise

    def get_by_full_name(self, *, full_name: str) -> Optional[Repository]:
        """
        Retrieves a repository entity by its full name (e.g., 'owner/repo').

        Args:
            full_name: The 'owner_login/repository_name' string.

        Returns:
            The Repository model instance if found, otherwise None.

        Raises:
            SQLAlchemyError: If a database error occurs during the query.
        """
        logger.debug(f"Getting Repository by full_name: {full_name}")
        if not self.db.is_active:
            logger.warning(f"Session is inactive in get_by_full_name for Repository '{full_name}'")
            return None
        try:
            # Query filtering by the full_name, which should ideally be unique.
            return self.db.query(self.model).filter(self.model.full_name == full_name).first()
        except SQLAlchemyError as e:
            logger.error(f"SQLAlchemyError during get_by_full_name for Repository '{full_name}': {e}", exc_info=True)
            raise

    def get_or_create_by_github_id(
        self, *, github_id: int, obj_in_data: Dict[str, Any], owner_obj: Optional[Owner] = None
    ) -> Repository:
        """
        Retrieves a repository by GitHub ID or creates a new one if not found.

        Implements the "Query-First" pattern for Repository entities:
        1. Attempts to fetch the repository using `get_by_github_id`.
        2. If found: Checks `obj_in_data` for differing fields (e.g., 'full_name',
           'description', 'stargazers_count', 'topics', 'license'). If the 'full_name'
           differs, it checks for conflicts with other existing repositories.
           It also updates the `owner_id` (and the relationship) if a different `owner_obj`
           is provided and attached to the session.
        3. If not found: Creates a new Repository instance. Requires a valid, flushed
           `owner_obj` (with an assigned ID) to be passed to establish the relationship.
           The necessary owner information (like ID) must be present in `owner_obj`.
        4. Important: Does NOT commit the transaction; caller is responsible.
        5. Uses `db.flush()` after add/update to interact with the DB early.
        6. Uses `db.refresh()` after flush to update the Python object state.

        Args:
            github_id: The unique GitHub repository ID to search for or use for creation.
            obj_in_data: Dictionary containing data for the repository. Must include fields
                         like 'full_name', 'description', etc.
            owner_obj: The *already persisted and flushed* Owner instance associated
                       with this repository. Required when creating a new repository.
                       Must have its primary key (`id`) populated.

        Returns:
            The existing (potentially updated) or newly created Repository instance,
            managed within the current session and flushed.

        Raises:
            ValueError: If `github_id` is missing, or if `owner_obj` is missing or not
                        properly flushed (lacks an ID) during creation.
            RuntimeError: If the database session is inactive at the start.
            SQLAlchemyError: If any database interaction (query, add, flush, refresh) fails.
        """
        if not github_id:
            raise ValueError("github_id cannot be empty for Repository get_or_create")
        if not self.db.is_active:
             logger.error("Session is inactive at start of get_or_create_by_github_id for Repository.")
             raise RuntimeError("Database session is inactive, cannot perform get_or_create.")

        try:
            # --- Step 1: Query First ---
            db_obj = self.get_by_github_id(github_id=github_id)

            if db_obj:
                # --- Step 2a: Record Found - Check for Updates ---
                logger.debug(f"Found existing Repository GH ID {github_id} (DB ID: {db_obj.id}). Checking for updates.")
                updated = False
                new_full_name = obj_in_data.get('full_name')

                # Check if full_name needs update and handle potential uniqueness conflicts.
                if new_full_name and db_obj.full_name != new_full_name:
                    if not self.db.is_active: # Re-check session before dependent query
                        raise RuntimeError("Session inactive before full_name conflict check.")
                    existing_fn_repo = self.get_by_full_name(full_name=new_full_name)
                    if existing_fn_repo and existing_fn_repo.id != db_obj.id:
                        # Log conflict, skip full_name update to avoid potential unique constraint error.
                        logger.warning(
                            f"Cannot update full_name for Repository GH ID {github_id} (DB ID: {db_obj.id}) to '{new_full_name}' "
                            f"because it's already assigned to Repository DB ID {existing_fn_repo.id}. Skipping full_name update."
                        )
                    else:
                        logger.info(f"Updating full_name for Repository {db_obj.id} from '{db_obj.full_name}' to '{new_full_name}'")
                        db_obj.full_name = new_full_name
                        updated = True

                # Update owner relationship if a valid owner object is provided and different.
                # Assumes owner_obj is already flushed and has an ID.
                if owner_obj and owner_obj.id is not None and db_obj.owner_id != owner_obj.id:
                    logger.info(f"Updating owner for Repository {db_obj.id} from owner_id {db_obj.owner_id} to owner_id {owner_obj.id}")
                    db_obj.owner_id = owner_obj.id
                    # Optionally update the relationship attribute directly if needed before commit,
                    # although changing owner_id is often sufficient for SQLAlchemy.
                    # db_obj.owner = owner_obj
                    updated = True

                # Update other repository attributes if provided and different.
                if obj_in_data.get('description') is not None and db_obj.description != obj_in_data.get('description'):
                    db_obj.description = obj_in_data['description']
                    updated = True
                if obj_in_data.get('stargazers_count') is not None and db_obj.stargazers_count != obj_in_data.get('stargazers_count'):
                    db_obj.stargazers_count = obj_in_data['stargazers_count']
                    updated = True
                # Note: Comparison for JSON/Array fields like topics might need adjustment based on data type/DB.
                if obj_in_data.get('topics') is not None and db_obj.topics != obj_in_data.get('topics'):
                    db_obj.topics = obj_in_data['topics']
                    updated = True
                if obj_in_data.get('license') is not None and db_obj.license != obj_in_data.get('license'):
                     db_obj.license = obj_in_data['license']
                     updated = True
                # Add other updatable fields (e.g., fork, archived, language, homepage)...

                if updated:
                    self.db.add(db_obj) # Mark as dirty.
                    logger.info(f"Repository {db_obj.id} marked for update in the current session.")
                    # Optional: Flush and refresh if needed.
                    # self.db.flush()
                    # self.db.refresh(db_obj)
                return db_obj # Return the existing instance.

            else:
                # --- Step 2b: Record Not Found - Create New ---
                logger.debug(f"Repository GH ID {github_id} not found. Preparing to create new.")
                # CRITICAL: Ensure a valid, flushed Owner object is provided for creation.
                if not owner_obj or owner_obj.id is None:
                    logger.error(f"Cannot create Repository GH ID {github_id}: Owner object is missing or not flushed (Owner ID: {getattr(owner_obj, 'id', 'None')}).")
                    raise ValueError("A flushed Owner object (with an assigned ID) must be provided via 'owner_obj' when creating a Repository.")

                # Ensure github_id is set in the creation data.
                obj_in_data["github_id"] = github_id
                new_obj = self.model(**obj_in_data) # Create the Repository instance.
                # Assign the owner relationship. SQLAlchemy handles setting the owner_id FK based on this.
                new_obj.owner = owner_obj
                self.db.add(new_obj) # Add to session.
                # Flush: Send INSERT, assign PK, check constraints (including FK to owner).
                self.db.flush()
                # Refresh: Load DB defaults.
                self.db.refresh(new_obj)
                logger.info(f"Successfully created and flushed new Repository GH ID {github_id} (DB ID: {new_obj.id}) with owner_id {new_obj.owner_id}")
                return new_obj # Return the new instance.

        except SQLAlchemyError as e:
            logger.error(f"SQLAlchemyError during get_or_create for Repository GH ID {github_id}: {e}", exc_info=True)
            # Caller handles rollback.
            raise # Re-raise the error.