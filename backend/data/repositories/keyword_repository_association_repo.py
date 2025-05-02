# keyword_repository_association_repo.py

"""
backend.data.repositories.keyword_repository_association_repo
-------------------------------------------------------------
Provides data access operations specifically for the KeywordRepositoryAssociation
model, which links keyword search sessions to repositories found during those sessions.
"""

import logging
from typing import Optional, Dict, Any, List, Tuple # Import Tuple for composite key get

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

# Note: This repository deals with an association object that has a composite primary key.
# It does not inherit from BaseRepository as the standard get/remove methods
# based on a single 'id' argument are not directly applicable.
from backend.data.models import KeywordRepositoryAssociation

logger = logging.getLogger(__name__)

class KeywordRepositoryAssociationRepository:
    """
    Repository for managing KeywordRepositoryAssociation link records.

    Handles creation and retrieval of associations between a KeywordSearchSession
    and a Repository, including optional match details. Due to the composite
    primary key (session_id, repository_id), it implements its own methods
    instead of inheriting directly from BaseRepository.
    """
    def __init__(self, db: Session):
        """
        Initializes the KeywordRepositoryAssociationRepository.

        Args:
            db: The SQLAlchemy Session object for database interactions.
        """
        self.db = db
        self.model = KeywordRepositoryAssociation

    def create_association(
        self,
        *,
        session_id: int,
        repository_id: int,
        match_details: Optional[Dict[str, Any]] = None
    ) -> KeywordRepositoryAssociation:
        """
        Creates a new association record between a search session and a repository.

        Instantiates a KeywordRepositoryAssociation object with the provided IDs
        and optional JSON metadata about the match. Adds the object to the
        session and flushes to ensure it's in the buffer and constraints are checked.

        Important: This method does NOT commit the transaction. The caller is
        responsible for committing the session after potentially creating multiple
        associations or performing other related operations.

        Args:
            session_id: The ID of the related KeywordSearchSession.
            repository_id: The ID of the related Repository.
            match_details: Optional dictionary containing JSON-serializable data
                           describing why or how this repository matched the search.

        Returns:
            The newly created KeywordRepositoryAssociation object, added to the
            session and flushed (but not committed).

        Raises:
            SQLAlchemyError: If adding or flushing the object to the database fails
                             (e.g., due to constraint violations).
        """
        logger.debug(f"Preparing to create KeywordRepositoryAssociation for session {session_id}, repo {repository_id}")
        # Create the association object instance.
        db_obj = self.model(
            keyword_search_session_id=session_id,
            repository_id=repository_id,
            match_details=match_details # Store provided JSON details.
        )
        try:
            self.db.add(db_obj) # Add the new association to the session.
            # Flush the session to send the INSERT statement. This helps catch
            # potential integrity errors (like duplicate primary keys) early.
            self.db.flush()
            # No refresh needed here typically, as this model likely doesn't have
            # database-generated defaults beyond the primary key components provided.
            logger.info(f"Successfully created and flushed KeywordRepositoryAssociation for session {session_id}, repo {repository_id}")
            return db_obj
        except SQLAlchemyError as e:
            # Log the specific error during creation/flush.
            logger.error(
                f"Database error creating KeywordRepositoryAssociation for session {session_id}, repo {repository_id}: {e}",
                exc_info=True
            )
            # Rollback should be handled by the service layer or API endpoint managing the overall transaction.
            raise # Re-raise the error for the caller.

    def get_by_session_and_repo_id(
        self, *, session_id: int, repository_id: int
    ) -> Optional[KeywordRepositoryAssociation]:
        """
        Retrieves a specific association record using its composite primary key.

        Uses `Session.get()` with a tuple representing the composite key.

        Args:
            session_id: The ID of the KeywordSearchSession part of the key.
            repository_id: The ID of the Repository part of the key.

        Returns:
            The KeywordRepositoryAssociation object if found, otherwise None.

        Raises:
            SQLAlchemyError: If a database error occurs during the lookup.
        """
        logger.debug(f"Getting KeywordRepositoryAssociation by composite key: session {session_id}, repo {repository_id}")
        try:
            # For composite keys, Session.get requires a tuple of the key values in the correct order.
            composite_key = (session_id, repository_id)
            return self.db.get(self.model, composite_key)
        except SQLAlchemyError as e:
            logger.error(
                f"Database error getting KeywordRepositoryAssociation for session {session_id}, repo {repository_id}: {e}",
                exc_info=True
            )
            raise # Re-raise for higher-level handling.

    def find_by_session_id(
        self, *, session_id: int
    ) -> List[KeywordRepositoryAssociation]:
        """
        Finds all repository associations belonging to a specific keyword search session.

        Args:
            session_id: The ID of the KeywordSearchSession whose associated
                        repositories are to be retrieved.

        Returns:
            A list of KeywordRepositoryAssociation objects linked to the given
            session ID. Returns an empty list if no associations are found.

        Raises:
            SQLAlchemyError: If a database error occurs during the query.
        """
        logger.debug(f"Finding all KeywordRepositoryAssociations for session_id {session_id}")
        try:
            # Query the association model, filtering by the session ID part of the composite key.
            return (
                self.db.query(self.model)
                .filter(self.model.keyword_search_session_id == session_id)
                .all()
            )
        except SQLAlchemyError as e:
            logger.error(
                f"Database error finding KeywordRepositoryAssociations for session {session_id}: {e}",
                exc_info=True
            )
            raise # Re-raise for caller to handle.

    # A potential future method:
    # def find_by_repository_id(self, *, repository_id: int) -> List[KeywordRepositoryAssociation]:
    #     """Find all search sessions that identified a specific repository."""
    #     logger.debug(f"Finding KeywordRepositoryAssociations for repository_id {repository_id}")
    #     # Implementation would filter by self.model.repository_id
    #     ...