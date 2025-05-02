# issue_comment_repo.py

"""
backend.data.repositories.issue_comment_repo
--------------------------------------------
Provides data access operations for the IssueComment model, representing
comments made on GitHub issues tracked by the system.
"""

import logging
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from .base_repository import BaseRepository
from backend.data.models import IssueComment # The specific SQLAlchemy model

logger = logging.getLogger(__name__)

class IssueCommentRepository(BaseRepository[IssueComment]):
    """
    Repository dedicated to managing IssueComment entities.

    Handles CRUD operations via BaseRepository and adds specific methods
    for finding comments by GitHub ID and implementing a get-or-create pattern.
    """

    def __init__(self, db: Session):
        """
        Initializes the IssueCommentRepository.

        Args:
            db: The SQLAlchemy Session for database interactions.
        """
        super().__init__(IssueComment, db)

    def get_by_github_id(self, *, github_id: int) -> Optional[IssueComment]:
        """
        Retrieves an issue comment entity by its unique GitHub comment ID.

        Args:
            github_id: The GitHub ID of the issue comment to find.

        Returns:
            The IssueComment model instance if found, otherwise None.

        Raises:
            SQLAlchemyError: If a database error occurs during the query.
        """
        logger.debug(f"Getting IssueComment by github_id: {github_id}")
        # Session activity check can aid in diagnosing transaction problems.
        if not self.db.is_active:
            logger.warning(f"Session is inactive in get_by_github_id for IssueComment {github_id}")
            return None
        try:
            # Query the IssueComment model filtering by the unique github_id.
            return self.db.query(self.model).filter(self.model.github_id == github_id).first()
        except SQLAlchemyError as e:
            logger.error(f"SQLAlchemyError during get_by_github_id for IssueComment {github_id}: {e}", exc_info=True)
            raise

    def get_or_create_by_github_id(
        self, *, github_id: int, obj_in_data: Dict[str, Any]
    ) -> IssueComment:
        """
        Retrieves an issue comment by GitHub ID or creates a new one if not found.

        Implements the "Query-First" pattern:
        1. Attempts to fetch the comment using `get_by_github_id`.
        2. If found, checks `obj_in_data` for potential updates (e.g., comment 'body',
           'gh_updated_at') and marks the object as dirty in the session if changes exist.
        3. If not found, creates a new IssueComment instance. Requires 'issue_id' and
           'user_id' (foreign keys) to be present in `obj_in_data` for successful creation.
        4. The operation does NOT commit the transaction; the caller handles commit/rollback.
        5. Uses `db.flush()` after adding/updating to synchronize with the DB and check constraints.
        6. Uses `db.refresh()` to update the object state from the DB post-flush.

        Args:
            github_id: The unique GitHub comment ID to search for or use for creation.
            obj_in_data: Dictionary containing data for the comment. Must include
                         'issue_id' and 'user_id' if creating a new comment. Other fields
                         like 'body', 'gh_updated_at' are used for creation or update checks.

        Returns:
            The existing (potentially updated) or newly created IssueComment instance,
            managed within the current session and flushed.

        Raises:
            ValueError: If `github_id` is missing, or if 'issue_id' or 'user_id'
                        are missing in `obj_in_data` during creation.
            RuntimeError: If the database session is inactive at the start.
            SQLAlchemyError: If any database interaction (query, add, flush, refresh) fails.
        """
        if not github_id:
            raise ValueError("github_id cannot be empty for IssueComment get_or_create")
        if not self.db.is_active:
             logger.error(f"Session is inactive at start of get_or_create_by_github_id for IssueComment {github_id}.")
             raise RuntimeError("Database session is inactive for IssueComment get_or_create.")

        # --- Step 1: Query First ---
        db_obj = self.get_by_github_id(github_id=github_id)

        if db_obj:
            # --- Step 2a: Record Found - Check for Updates ---
            logger.debug(f"Found existing IssueComment GH ID {github_id} (DB ID: {db_obj.id}). Checking for updates.")
            updated = False
            # Check if comment body has changed.
            if obj_in_data.get('body') is not None and db_obj.body != obj_in_data.get('body'):
                db_obj.body = obj_in_data['body']
                updated = True
            # Check if the GitHub update timestamp has changed.
            if obj_in_data.get('gh_updated_at') is not None and db_obj.gh_updated_at != obj_in_data.get('gh_updated_at'):
                db_obj.gh_updated_at = obj_in_data['gh_updated_at']
                updated = True
            # Add checks for other potentially updatable fields if needed.

            if updated:
                 self.db.add(db_obj) # Mark the instance as dirty.
                 logger.info(f"IssueComment {db_obj.id} marked for update in the current session.")
                 # Optional flush/refresh could go here if caller needs immediate DB state.
            return db_obj # Return the existing instance.
        else:
            # --- Step 2b: Record Not Found - Create New ---
            logger.debug(f"IssueComment GH ID {github_id} not found. Preparing to create new.")
            # Validate required foreign keys for creation.
            if 'issue_id' not in obj_in_data or 'user_id' not in obj_in_data:
                raise ValueError(f"Missing required 'issue_id' or 'user_id' in obj_in_data for creating new IssueComment with GH ID {github_id}")

            # Ensure the github_id is included in the data for the new object.
            obj_in_data["github_id"] = github_id
            new_obj = self.model(**obj_in_data) # Instantiate the new comment.
            self.db.add(new_obj) # Add to the session.
            # Flush to send INSERT to DB, assign PK, check FK constraints.
            self.db.flush()
            # Refresh to load any DB-generated values.
            self.db.refresh(new_obj)
            logger.info(f"Successfully created and flushed new IssueComment GH ID {github_id} (DB ID: {new_obj.id})")
            return new_obj # Return the newly created instance.

        # Note: SQLAlchemyError handling is implicitly covered by the BaseRepository
        # structure if the error occurs within self.get_by_github_id, or it will
        # propagate from flush/refresh if it occurs there. The caller should handle it.