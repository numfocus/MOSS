# software_dependency_repo.py

"""
backend.data.repositories.software_dependency_repo
--------------------------------------------------
Provides data access operations for the SoftwareDependency model, representing
dependencies listed in project files (e.g., requirements.txt, package.json).
"""
import logging
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from .base_repository import BaseRepository
from backend.data.models import SoftwareDependency # The specific model

logger = logging.getLogger(__name__)

class SoftwareDependencyRepository(BaseRepository[SoftwareDependency]):
    """
    Repository for managing SoftwareDependency entities.

    Handles CRUD operations via BaseRepository and adds specific methods for
    finding dependencies within a repository, potentially by name and source file,
    and includes a get-or-create pattern based on these identifiers.
    """

    def __init__(self, db: Session):
        """
        Initializes the SoftwareDependencyRepository.

        Args:
            db: The SQLAlchemy Session for database interactions.
        """
        super().__init__(SoftwareDependency, db)

    def find_by_repository_and_name(
        self, *, repository_id: int, dependency_name: str, source_file: str
    ) -> Optional[SoftwareDependency]:
        """
        Finds a specific dependency entry based on the repository, dependency name,
        and the source file where it was declared.

        Assumes the combination of repository, name, and source file is unique or
        that retrieving the first match is sufficient.

        Args:
            repository_id: The ID of the repository containing the dependency.
            dependency_name: The name of the dependency package/library.
            source_file: The path to the file declaring the dependency (e.g., 'requirements.txt').

        Returns:
            The SoftwareDependency model instance if found, otherwise None.

        Raises:
            SQLAlchemyError: If a database error occurs during the query.
        """
        logger.debug(f"Finding dependency '{dependency_name}' from source '{source_file}' in repository {repository_id}")
        try:
            return (
                self.db.query(self.model)
                .filter(
                    self.model.repository_id == repository_id,
                    self.model.dependency_name == dependency_name,
                    self.model.source_file == source_file
                )
                .first() # Expecting one or zero matches based on these fields.
            )
        except SQLAlchemyError as e:
            logger.error(f"DB error finding dependency {dependency_name} in {source_file} for repo {repository_id}: {e}", exc_info=True)
            raise

    def get_or_create(
        self, *, obj_in_data: Dict[str, Any]
    ) -> SoftwareDependency:
        """
        Retrieves a software dependency record or creates a new one if not found.

        Uses the combination of `repository_id`, `dependency_name`, and `source_file`
        as the logical key for identifying an existing dependency record.

        1. Extracts key fields from `obj_in_data`.
        2. Calls `find_by_repository_and_name` to check for existence.
        3. If found: Returns the existing object. Optionally, could update fields
           like `version_constraint` here if needed (currently commented out).
        4. If not found: Creates a new `SoftwareDependency` instance using `obj_in_data`.
        5. Does NOT commit the transaction; caller is responsible.
        6. Uses `db.flush()` after adding a new object.
        7. Uses `db.refresh()` after flush.

        Args:
            obj_in_data: Dictionary containing data for the dependency. Must include
                         'repository_id', 'dependency_name', and 'source_file'. May also
                         include 'version_constraint', 'dependency_type', etc.

        Returns:
            The existing or newly created SoftwareDependency instance, managed within
            the current session and flushed.

        Raises:
            ValueError: If required key fields ('repository_id', 'dependency_name',
                        'source_file') are missing in `obj_in_data`.
            SQLAlchemyError: If any database interaction fails.
        """
        repo_id = obj_in_data.get("repository_id")
        dep_name = obj_in_data.get("dependency_name")
        src_file = obj_in_data.get("source_file")

        # Validate required fields for lookup/creation.
        if not all([repo_id, dep_name, src_file is not None]): # Allow empty string for source_file? Check constraints.
            raise ValueError("repository_id, dependency_name, and source_file must be provided in obj_in_data for SoftwareDependency get_or_create")

        # --- Step 1: Query First ---
        db_obj = self.find_by_repository_and_name(
            repository_id=repo_id, dependency_name=dep_name, source_file=src_file
        )

        if db_obj:
            # --- Step 2a: Record Found ---
            logger.debug(f"Found existing dependency record: {dep_name} in {src_file} for repo {repo_id} (ID: {db_obj.id})")
            # --- Optional Update Logic ---
            # Example: Update version constraint if it has changed.
            # new_version = obj_in_data.get("version_constraint")
            # if new_version is not None and new_version != db_obj.version_constraint:
            #     logger.info(f"Updating version constraint for dependency {db_obj.id} from '{db_obj.version_constraint}' to '{new_version}'")
            #     db_obj.version_constraint = new_version
            #     self.db.add(db_obj) # Mark as dirty if updated.
            #     # Consider flushing/refreshing if updates are made.
            return db_obj # Return existing object.
        else:
            # --- Step 2b: Record Not Found - Create New ---
            logger.debug(f"Creating new dependency record: {dep_name} in {src_file} for repo {repo_id}")
            try:
                new_obj = self.model(**obj_in_data) # Instantiate new object.
                self.db.add(new_obj) # Add to session.
                self.db.flush() # Send INSERT, get PK, check constraints.
                self.db.refresh(new_obj) # Load DB defaults.
                logger.info(f"Successfully created and flushed new dependency {new_obj.id} ({dep_name} in {src_file} for repo {repo_id})")
                return new_obj # Return new object.
            except SQLAlchemyError as e:
                logger.error(f"DB error creating dependency {dep_name} in {src_file} for repo {repo_id}: {e}", exc_info=True)
                raise # Re-raise for caller to handle (and rollback).

    def find_by_repository(
        self, *, repository_id: int
    ) -> List[SoftwareDependency]:
        """
        Finds all software dependencies declared within a specific repository.

        Args:
            repository_id: The ID of the repository whose dependencies are needed.

        Returns:
            A list of all SoftwareDependency instances linked to the repository,
            ordered by source file and then dependency name. Returns an empty
            list if none exist.

        Raises:
            SQLAlchemyError: If a database error occurs during the query.
        """
        logger.debug(f"Finding all dependencies for repository_id {repository_id}")
        try:
            return (
                self.db.query(self.model)
                .filter(self.model.repository_id == repository_id)
                .order_by(self.model.source_file, self.model.dependency_name) # Order for consistent results.
                .all()
            )
        except SQLAlchemyError as e:
            logger.error(f"DB error finding dependencies for repo {repository_id}: {e}", exc_info=True)
            raise