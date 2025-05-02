# pr_review_comment_repo.py

"""
backend.data.repositories.pr_review_comment_repo
------------------------------------------------
Provides data access operations for the PRReviewComment model, representing
comments made as part of a GitHub Pull Request review.
"""
import logging
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from .base_repository import BaseRepository
from backend.data.models import PRReviewComment # The specific SQLAlchemy model

logger = logging.getLogger(__name__)

class PRReviewCommentRepository(BaseRepository[PRReviewComment]):
    """
    Repository dedicated to managing Pull Request Review Comment entities.

    Handles CRUD operations via BaseRepository and adds specific methods
    for finding comments by GitHub ID and implementing a get-or-create pattern.
    These comments are distinct from standalone PR comments and are associated
    with a specific review.
    """

    def __init__(self, db: Session):
        """
        Initializes the PRReviewCommentRepository.

        Args:
            db: The SQLAlchemy Session for database interactions.
        """
        super().__init__(PRReviewComment, db)

    def get_by_github_id(self, *, github_id: int) -> Optional[PRReviewComment]:
        """
        Retrieves a PR review comment entity by its unique GitHub comment ID.

        Args:
            github_id: The GitHub ID of the PR review comment to find.

        Returns:
            The PRReviewComment model instance if found, otherwise None.

        Raises:
            SQLAlchemyError: If a database error occurs during the query.
        """
        logger.debug(f"Getting PRReviewComment by github_id: {github_id}")
        # Check for active session to help debug potential transaction issues.
        if not self.db.is_active:
            logger.warning(f"Session is inactive in get_by_github_id for PRReviewComment {github_id}")
            return None
        try:
            # Query the PRReviewComment model filtering by the unique github_id.
            return self.db.query(self.model).filter(self.model.github_id == github_id).first()
        except SQLAlchemyError as e:
            logger.error(f"SQLAlchemyError during get_by_github_id for PRReviewComment {github_id}: {e}", exc_info=True)
            raise

    def get_or_create_by_github_id(
        self, *, github_id: int, obj_in_data: Dict[str, Any]
    ) -> PRReviewComment:
        """
        Retrieves a PR review comment by GitHub ID or creates a new one if not found.

        Implements the "Query-First" pattern:
        1. Attempts to fetch the comment using `get_by_github_id`.
        2. If found, checks `obj_in_data` for potential updates (e.g., comment 'body',
           'gh_updated_at', 'pull_request_review_id') and marks the object as dirty
           in the session if changes exist.
        3. If not found, creates a new PRReviewComment instance. Requires 'pr_id'
           (the associated Pull Request ID) and 'user_id' (the comment author ID)
           to be present in `obj_in_data` for successful creation.
        4. The operation does NOT commit the transaction; the caller manages commit/rollback.
        5. Uses `db.flush()` after adding/updating to synchronize with the DB and check constraints.
        6. Uses `db.refresh()` to update the object state from the DB post-flush.

        Args:
            github_id: The unique GitHub comment ID to search for or use for creation.
            obj_in_data: Dictionary containing data for the comment. Must include
                         'pr_id' and 'user_id' if creating. Other fields like 'body',
                         'gh_updated_at', 'pull_request_review_id' are used for creation
                         or update checks.

        Returns:
            The existing (potentially updated) or newly created PRReviewComment instance,
            managed within the current session and flushed.

        Raises:
            ValueError: If `github_id` is missing, or if 'pr_id' or 'user_id'
                        are missing in `obj_in_data` during creation.
            RuntimeError: If the database session is inactive at the start.
            SQLAlchemyError: If any database interaction (query, add, flush, refresh) fails.
        """
        if not github_id:
            raise ValueError("github_id cannot be empty for PRReviewComment get_or_create")
        if not self.db.is_active:
             logger.error(f"Session is inactive at start of get_or_create_by_github_id for PRReviewComment {github_id}.")
             raise RuntimeError("Database session is inactive for PRReviewComment get_or_create.")

        # --- Step 1: Query First ---
        db_obj = self.get_by_github_id(github_id=github_id)

        if db_obj:
            # --- Step 2a: Record Found - Check for Updates ---
            logger.debug(f"Found existing PRReviewComment GH ID {github_id} (DB ID: {db_obj.id}). Checking for updates.")
            updated = False
            # Check if comment body has changed.
            if obj_in_data.get('body') is not None and db_obj.body != obj_in_data.get('body'):
                db_obj.body = obj_in_data['body']
                updated = True
            # Check if the GitHub update timestamp has changed.
            if obj_in_data.get('gh_updated_at') is not None and db_obj.gh_updated_at != obj_in_data.get('gh_updated_at'):
                db_obj.gh_updated_at = obj_in_data['gh_updated_at']
                updated = True
            # Check if the associated review ID has changed (less likely, but possible).
            if obj_in_data.get('pull_request_review_id') is not None and db_obj.pull_request_review_id != obj_in_data.get('pull_request_review_id'):
                 db_obj.pull_request_review_id = obj_in_data['pull_request_review_id']
                 updated = True
            # Add checks for other potentially updatable fields if needed.

            if updated:
                 self.db.add(db_obj) # Mark the instance as dirty.
                 logger.info(f"PRReviewComment {db_obj.id} marked for update in the current session.")
                 # Optional flush/refresh could go here if caller needs immediate DB state.
            return db_obj # Return the existing instance.
        else:
            # --- Step 2b: Record Not Found - Create New ---
            logger.debug(f"PRReviewComment GH ID {github_id} not found. Preparing to create new.")
            # Validate required foreign keys for creation.
            if 'pr_id' not in obj_in_data or 'user_id' not in obj_in_data:
                raise ValueError(f"Missing required 'pr_id' or 'user_id' in obj_in_data for creating new PRReviewComment with GH ID {github_id}")

            # Ensure the github_id is included in the data for the new object.
            obj_in_data["github_id"] = github_id
            new_obj = self.model(**obj_in_data) # Instantiate the new comment.
            self.db.add(new_obj) # Add to the session.
            # Flush to send INSERT to DB, assign PK, check FK constraints.
            self.db.flush()
            # Refresh to load any DB-generated values.
            self.db.refresh(new_obj)
            logger.info(f"Successfully created and flushed new PRReviewComment GH ID {github_id} (DB ID: {new_obj.id})")
            return new_obj # Return the newly created instance.

        # Note: SQLAlchemyError handling from underlying operations like
        # get_by_github_id, flush, refresh will propagate up. The caller
        # is responsible for handling these and managing the transaction.