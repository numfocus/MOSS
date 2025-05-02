# repository_institution_affiliation_repo.py

"""
backend.data.repositories.repository_institution_affiliation_repo
-----------------------------------------------------------------
Provides data access operations for the RepositoryInstitutionAffiliation model,
representing the calculated affiliation between a Repository and an Institution
based on a specific algorithm.
"""

import logging
from typing import Dict, Any, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
# from sqlalchemy import func # Uncomment if using func.now() as server_default
from datetime import datetime, timezone # Used for manually setting timestamps

from backend.data.models import RepositoryInstitutionAffiliation # The specific model

logger = logging.getLogger(__name__)

class RepositoryInstitutionAffiliationRepository:
    """
    Repository for managing RepositoryInstitutionAffiliation records.

    This class specifically handles the creation and updating of affiliation links
    between repositories and institutions, as determined by named algorithms.
    It does not inherit from BaseRepository because it deals with a composite
    primary key (repository_id, institution_id, algorithm_name, algorithm_version)
    and implements a specific create-or-update logic.
    """
    def __init__(self, db: Session):
        """
        Initializes the RepositoryInstitutionAffiliationRepository.

        Args:
            db: The SQLAlchemy Session object for database interactions.
        """
        self.db = db
        self.model = RepositoryInstitutionAffiliation

    def get_affiliation(
        self,
        *,
        repository_id: int,
        institution_id: int,
        algorithm_name: str,
        algorithm_version: str
    ) -> Optional[RepositoryInstitutionAffiliation]:
        """
        Retrieves a specific affiliation record using its composite primary key.

        Args:
            repository_id: The ID of the associated Repository.
            institution_id: The ID of the associated Institution.
            algorithm_name: The name identifier of the algorithm used.
            algorithm_version: The version identifier of the algorithm used.

        Returns:
            The RepositoryInstitutionAffiliation object if found, otherwise None.

        Raises:
            SQLAlchemyError: If a database error occurs during the lookup.
        """
        pk_tuple = (repository_id, institution_id, algorithm_name, algorithm_version)
        logger.debug(f"Getting affiliation by composite key: {pk_tuple}")
        try:
            # Session.get is efficient for primary key lookups, including composite keys (passed as a tuple).
            return self.db.get(self.model, pk_tuple)
        except SQLAlchemyError as e:
            logger.error(f"DB error getting affiliation for key {pk_tuple}: {e}", exc_info=True)
            raise # Propagate the error for handling by the caller.

    def create_or_update_affiliation(
        self,
        *,
        repository_id: int,
        institution_id: int,
        algorithm_name: str,
        algorithm_version: str,
        confidence_score: float,
        evidence: Optional[Dict[str, Any]] = None,
        parameters_used: Optional[Dict[str, Any]] = None
    ) -> Tuple[RepositoryInstitutionAffiliation, bool]:
        """
        Creates a new affiliation record or updates an existing one based on the composite PK.

        This method implements an "upsert" logic for affiliation records.
        1. It first attempts to `get_affiliation` using the composite key elements.
        2. If an existing record is found:
           - It updates the `confidence_score`, `evidence`, `parameters_used`.
           - Crucially, it also updates the `calculated_at` timestamp to reflect
             when this latest calculation/update occurred.
        3. If no existing record is found:
           - It creates a new `RepositoryInstitutionAffiliation` instance with all
             provided data, including the current timestamp for `calculated_at`.
        4. Adds the new or updated object to the session and flushes the session.
           Flushing sends the SQL (INSERT or UPDATE) to the DB and checks constraints.
        5. Refreshes the object state from the database after flushing.

        Important:
        - Does NOT commit the transaction; the caller is responsible for commit/rollback.
        - Manually sets the `calculated_at` timestamp on both create and update.
          If the model used `server_default=func.now()`, refresh might handle it,
          but explicit setting ensures consistency.

        Args:
            repository_id: ID of the Repository.
            institution_id: ID of the Institution.
            algorithm_name: Name of the affiliation algorithm.
            algorithm_version: Version of the affiliation algorithm.
            confidence_score: The calculated confidence score for this affiliation.
            evidence: Optional JSON-serializable dictionary detailing the evidence found.
            parameters_used: Optional JSON-serializable dictionary of algorithm parameters used.

        Returns:
            A tuple containing:
                - The created or updated RepositoryInstitutionAffiliation object (flushed and refreshed).
                - A boolean: `True` if a new record was created, `False` if an existing record was updated.

        Raises:
            SQLAlchemyError: If any database operation (get, add, flush, refresh) fails.
        """
        # Attempt to find an existing record using the composite key.
        existing_affiliation = self.get_affiliation(
            repository_id=repository_id,
            institution_id=institution_id,
            algorithm_name=algorithm_name,
            algorithm_version=algorithm_version
        )

        created = False # Flag to indicate if a new record was created.
        # Get the current UTC time for the calculated_at timestamp.
        current_time = datetime.now(timezone.utc)
        pk_tuple = (repository_id, institution_id, algorithm_name, algorithm_version) # For logging

        if existing_affiliation:
            # --- Update Existing Record ---
            logger.debug(f"Updating existing affiliation for key: {pk_tuple}")
            db_obj = existing_affiliation
            # Update the relevant fields with the new calculation results.
            db_obj.confidence_score = confidence_score
            db_obj.evidence = evidence
            db_obj.parameters_used = parameters_used
            # Explicitly update the timestamp on each update.
            db_obj.calculated_at = current_time
            # Mark created as False since we are updating.
            created = False
        else:
            # --- Create New Record ---
            logger.debug(f"Creating new affiliation for key: {pk_tuple}")
            db_obj = self.model(
                repository_id=repository_id,
                institution_id=institution_id,
                algorithm_name=algorithm_name,
                algorithm_version=algorithm_version,
                confidence_score=confidence_score,
                evidence=evidence,
                parameters_used=parameters_used,
                calculated_at=current_time # Set timestamp on creation as well.
            )
            # Mark created as True since we are inserting.
            created = True

        try:
            self.db.add(db_obj) # Add the new or updated object to the session.
            # Flush to send SQL (INSERT or UPDATE) to the database and check constraints.
            self.db.flush()
            # Refresh the object state to ensure it reflects any DB-side changes
            # (though less likely for this model unless triggers are used).
            self.db.refresh(db_obj)
            logger.info(f"Successfully {'created' if created else 'updated'} and flushed affiliation for key: {pk_tuple}")
            return db_obj, created # Return the object and the created/updated status flag.
        except SQLAlchemyError as e:
            logger.error(f"DB error {'creating' if created else 'updating'} affiliation for key {pk_tuple}: {e}", exc_info=True)
            # Rollback should occur in the calling service layer / API endpoint.
            raise # Re-raise the error.