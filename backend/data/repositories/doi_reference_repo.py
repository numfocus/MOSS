# doi_reference_repo.py

"""
backend.data.repositories.doi_reference_repo
--------------------------------------------
Provides data access operations specifically for the DOIReference model,
handling queries related to Digital Object Identifier references found
within repositories.
"""

import logging
from typing import Optional, List

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from .base_repository import BaseRepository
from backend.data.models import DOIReference # The specific SQLAlchemy model

logger = logging.getLogger(__name__)

class DOIReferenceRepository(BaseRepository[DOIReference]):
    """
    Repository specializing in operations for DOIReference entities.

    Extends the BaseRepository to provide common CRUD functionality and adds
    specific query methods tailored to finding DOI references based on
    repository context, DOI value, source file, or associated work.
    """

    def __init__(self, db: Session):
        """
        Initializes the DOIReferenceRepository.

        Args:
            db: The SQLAlchemy Session for database interactions.
        """
        super().__init__(DOIReference, db)

    def find_by_repository_and_doi(
        self, *, repository_id: int, doi: str
    ) -> List[DOIReference]:
        """
        Finds all references to a specific DOI within a given repository.

        This can be useful to see all locations (e.g., files) where a
        particular DOI is mentioned within the scope of one repository.

        Args:
            repository_id: The ID of the repository to search within.
            doi: The DOI string to search for.

        Returns:
            A list of DOIReference instances matching the criteria, or an
            empty list if none are found.

        Raises:
            SQLAlchemyError: If a database error occurs during the query.
        """
        logger.debug(f"Finding DOIReferences for repo_id {repository_id} and DOI {doi}")
        try:
            return (
                self.db.query(self.model)
                .filter(self.model.repository_id == repository_id, self.model.doi == doi)
                .all()
            )
        except SQLAlchemyError as e:
            logger.error(f"DB error finding DOIReferences for repo {repository_id}, DOI {doi}: {e}", exc_info=True)
            raise

    def find_by_repository_and_doi_and_source(
        self, *, repository_id: int, doi: str, source_file: str
    ) -> Optional[DOIReference]:
        """
        Finds a specific DOI reference identified by its composite key elements.

        This targets a unique reference based on the repository it was found in,
        the DOI value itself, and the specific file path where it was located.

        Args:
            repository_id: The ID of the repository.
            doi: The DOI string.
            source_file: The path to the file where the DOI reference was found.

        Returns:
            The specific DOIReference instance if found, otherwise None.

        Raises:
            SQLAlchemyError: If a database error occurs during the query.
        """
        logger.debug(f"Finding unique DOIReference for repo_id {repository_id}, DOI {doi}, source {source_file}")
        try:
            # Querying based on the combination of fields that likely form a unique constraint or key.
            return (
                self.db.query(self.model)
                .filter(
                    self.model.repository_id == repository_id,
                    self.model.doi == doi,
                    self.model.source_file == source_file
                )
                .first() # Expecting at most one result due to the specific filters.
            )
        except SQLAlchemyError as e:
            logger.error(
                f"Database error finding DOIReference for repo {repository_id}, doi {doi}, source {source_file}: {e}",
                exc_info=True
            )
            # Re-raise allows the service layer or API endpoint to handle the failure gracefully.
            raise

    def find_by_repository(self, *, repository_id: int) -> List[DOIReference]:
        """
        Finds all DOI references associated with a specific repository.

        Args:
            repository_id: The ID of the repository whose DOI references are needed.

        Returns:
            A list of all DOIReference instances linked to the repository, or an
            empty list if none exist.

        Raises:
            SQLAlchemyError: If a database error occurs during the query.
        """
        logger.debug(f"Finding all DOIReferences for repo_id {repository_id}")
        try:
            return (
                self.db.query(self.model)
                .filter(self.model.repository_id == repository_id)
                .all()
            )
        except SQLAlchemyError as e:
            logger.error(f"DB error finding DOIReferences for repo {repository_id}: {e}", exc_info=True)
            raise

    def find_by_work_id(self, *, work_id: int) -> List[DOIReference]:
        """
        Finds all DOI references that have been linked to a specific Work entity.

        This allows retrieval of all source locations (across potentially multiple
        repositories) where a DOI corresponding to a known academic work (Work entity)
        has been found.

        Args:
            work_id: The ID of the Work entity.

        Returns:
            A list of DOIReference instances associated with the specified work_id,
            or an empty list if none are found.

        Raises:
            SQLAlchemyError: If a database error occurs during the query.
        """
        logger.debug(f"Finding DOIReferences associated with work_id {work_id}")
        try:
            return (
                self.db.query(self.model)
                .filter(self.model.work_id == work_id)
                .all()
            )
        except SQLAlchemyError as e:
             logger.error(f"DB error finding DOIReferences for work {work_id}: {e}", exc_info=True)
             raise

    # Other potential query methods could include:
    # - find_by_doi(doi: str) -> List[DOIReference]: Find all references to a DOI across all repositories.
    # - find_unlinked() -> List[DOIReference]: Find references not yet associated with a Work entity.