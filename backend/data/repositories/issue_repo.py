# issue_repo.py

"""
backend.data.repositories.issue_repo
------------------------------------
Provides data access operations for the Issue model, representing GitHub issues
tracked within associated repositories.
"""
import logging
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from .base_repository import BaseRepository
from backend.data.models import Issue # The specific SQLAlchemy model

logger = logging.getLogger(__name__)

class IssueRepository(BaseRepository[Issue]):
    """
    Repository for managing Issue entities, including CRUD and specific queries.

    Extends the generic BaseRepository and adds methods tailored for issues,
    such as finding by GitHub ID and a get-or-create pattern.
    """

    def __init__(self, db: Session):
        """
        Initializes the IssueRepository.

        Args:
            db: The SQLAlchemy Session for database interactions.
        """
        super().__init__(Issue, db)

    def get_by_github_id(self, *, github_id: int) -> Optional[Issue]:
        """
        Retrieves an issue entity by its unique GitHub issue ID.

        Note: GitHub issue IDs are unique within a repository, but this method
        queries based on the globally unique ID assigned in the `issues` table,
        which should correspond to GitHub's global node ID or similar if used,
        or a repository-specific ID if the model design implies that. The implementation
        filters `self.model.github_id`, assuming this column holds the intended unique ID.

        Args:
            github_id: The GitHub ID (as stored in the `github_id` column) of the issue.

        Returns:
            The Issue model instance if found, otherwise None.

        Raises:
            SQLAlchemyError: If a database error occurs during the query.
        """
        logger.debug(f"Getting Issue by github_id: {github_id}")
        if not self.db.is_active:
            logger.warning(f"Session is inactive in get_by_github_id for Issue {github_id}")
            return None
        try:
            # Query the Issue model filtering by the unique github_id.
            return self.db.query(self.model).filter(self.model.github_id == github_id).first()
        except SQLAlchemyError as e:
            logger.error(f"SQLAlchemyError during get_by_github_id for Issue {github_id}: {e}", exc_info=True)
            raise

    def get_or_create_by_github_id(
        self, *, github_id: int, obj_in_data: Dict[str, Any]
    ) -> Issue:
        """
        Retrieves an issue by GitHub ID or creates a new one if not found.

        Follows the "Query-First" pattern:
        1. Attempts to fetch the issue using `get_by_github_id`.
        2. If found, checks `obj_in_data` for differing fields (e.g., 'title',
           'state', 'gh_updated_at', 'gh_closed_at') and updates the existing
           record in the session if necessary.
        3. If not found, creates a new Issue instance. Requires 'repository_id'
           and 'user_id' (foreign keys representing the repo and issue creator)
           to be present in `obj_in_data`.
        4. Does NOT commit the transaction; relies on the caller.
        5. Uses `db.flush()` after add/update to interact with the DB early.
        6. Uses `db.refresh()` after flush to update the Python object state.

        Args:
            github_id: The unique GitHub issue ID (as stored in the table) to
                       search for or use for creation.
            obj_in_data: Dictionary containing data for the issue. Must include
                         'repository_id' and 'user_id' if creating. Other fields
                         like 'title', 'state', timestamps are used for creation or update.

        Returns:
            The existing (potentially updated) or newly created Issue instance,
            managed within the current session and flushed.

        Raises:
            ValueError: If `github_id` is missing, or if 'repository_id' or 'user_id'
                        are missing in `obj_in_data` during creation.
            RuntimeError: If the database session is inactive at the start.
            SQLAlchemyError: If any database interaction (query, add, flush, refresh) fails.
        """
        if not github_id:
            raise ValueError("github_id cannot be empty for Issue get_or_create")
        if not self.db.is_active:
             logger.error(f"Session is inactive at start of get_or_create_by_github_id for Issue {github_id}.")
             raise RuntimeError("Database session is inactive, cannot perform get_or_create.")

        try:
            # --- Step 1: Query First ---
            db_obj = self.get_by_github_id(github_id=github_id)

            if db_obj:
                # --- Step 2a: Record Found - Check for Updates ---
                logger.debug(f"Found existing Issue GH ID {github_id} (DB ID: {db_obj.id}). Checking for updates.")
                updated = False
                # Check and update common fields that might change.
                if obj_in_data.get('title') is not None and db_obj.title != obj_in_data.get('title'):
                    db_obj.title = obj_in_data['title']
                    updated = True
                if obj_in_data.get('state') is not None and db_obj.state != obj_in_data.get('state'):
                    db_obj.state = obj_in_data['state']
                    updated = True
                if obj_in_data.get('gh_updated_at') is not None and db_obj.gh_updated_at != obj_in_data.get('gh_updated_at'):
                    db_obj.gh_updated_at = obj_in_data['gh_updated_at']
                    updated = True
                if obj_in_data.get('gh_closed_at') is not None and db_obj.gh_closed_at != obj_in_data.get('gh_closed_at'):
                    # Note: Ensure gh_closed_at can be None if the issue is reopened.
                    db_obj.gh_closed_at = obj_in_data['gh_closed_at']
                    updated = True
                # Add other relevant fields like labels, assignees, body if managed here.

                if updated:
                    self.db.add(db_obj) # Mark as dirty in the session.
                    logger.info(f"Issue {db_obj.id} marked for update in the current session.")
                    # Optional: Flush and refresh if immediate state needed by caller.
                    # self.db.flush()
                    # self.db.refresh(db_obj)
                return db_obj # Return the existing instance.
            else:
                # --- Step 2b: Record Not Found - Create New ---
                logger.debug(f"Issue GH ID {github_id} not found. Preparing to create new.")
                # Validate presence of required foreign keys for creation.
                if 'repository_id' not in obj_in_data or 'user_id' not in obj_in_data:
                    raise ValueError(f"Missing required 'repository_id' or 'user_id' in obj_in_data for creating new Issue with GH ID {github_id}")

                # Ensure github_id is set in the creation data.
                obj_in_data["github_id"] = github_id
                new_obj = self.model(**obj_in_data) # Instantiate the new issue.
                self.db.add(new_obj) # Add to session.
                # Flush: Send INSERT, get PK, check FK constraints.
                self.db.flush()
                # Refresh: Load DB defaults/generated values.
                self.db.refresh(new_obj)
                logger.info(f"Successfully created and flushed new Issue GH ID {github_id} (DB ID: {new_obj.id})")
                return new_obj # Return the new instance.

        except SQLAlchemyError as e:
            logger.error(f"SQLAlchemyError during get_or_create for Issue GH ID {github_id}: {e}", exc_info=True)
            # Rollback is handled by the caller.
            raise # Re-raise the error.