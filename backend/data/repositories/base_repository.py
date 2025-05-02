# base_repository.py

"""
backend.data.repositories.base_repository
-----------------------------------------
Provides a generic base class for data repository operations,
encapsulating common CRUD functionalities for SQLAlchemy models.
"""

import logging
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

# Note: The 'Base' import from backend.data.database is not directly needed here
# as the ModelType is unbound, but models used *with* this repository
# are expected to inherit from a SQLAlchemy declarative base.

logger = logging.getLogger(__name__)

# Define a TypeVar for the SQLAlchemy model type.
# This allows the repository to be generic over any SQLAlchemy model class.
ModelType = TypeVar("ModelType")
# Placeholder TypeVars for schema types, potentially Pydantic models later.
# CreateSchemaType = TypeVar("CreateSchemaType", bound=Dict[str, Any])
# UpdateSchemaType = TypeVar("UpdateSchemaType", bound=Dict[str, Any])

class BaseRepository(Generic[ModelType]):
    """
    Generic base class for data repositories.

    Provides standardized CRUD (Create, Read, Update, Delete) operations
    for a specific SQLAlchemy model type (`ModelType`). This promotes code
    reuse and consistency across different data access layers.
    """

    def __init__(self, model: Type[ModelType], db: Session):
        """
        Initializes the BaseRepository.

        Args:
            model: The SQLAlchemy model class this repository will manage.
                   It's expected that this model class maps to a database table.
            db: The SQLAlchemy Session object to be used for database interactions.
                This session is typically managed externally (e.g., via dependency injection).
        """
        self.model = model
        self.db = db

    def get(self, id: Any) -> Optional[ModelType]:
        """
        Retrieves a single object by its primary key.

        Uses `Session.get()`, which is optimized for primary key lookups,
        especially when dealing with identity maps.

        Args:
            id: The primary key value of the object to retrieve. The type
                can vary depending on the model's primary key definition (e.g., int, UUID).

        Returns:
            The model instance corresponding to the given ID, or None if no
            such object exists.

        Raises:
            SQLAlchemyError: If a database-related error occurs during the query.
                             The original exception is re-raised after logging.
        """
        logger.debug(f"Getting {self.model.__name__} with id: {id}")
        try:
            # Recommended way to fetch by PK in SQLAlchemy >= 1.4
            return self.db.get(self.model, id)
        except SQLAlchemyError as e:
            logger.error(f"Database error getting {self.model.__name__} id {id}: {e}", exc_info=True)
            # Re-raise allows higher-level handlers (e.g., API endpoints)
            # to manage the error appropriately (e.g., return HTTP 500).
            raise

    def get_multi(
        self, *, skip: int = 0, limit: int = 100
    ) -> List[ModelType]:
        """
        Retrieves multiple objects with optional pagination.

        Args:
            skip: The number of initial records to skip (for pagination). Defaults to 0.
            limit: The maximum number of records to return. Defaults to 100.

        Returns:
            A list of model instances found, potentially empty if none match
            or if the skip/limit range is outside available data.

        Raises:
            SQLAlchemyError: If a database-related error occurs during the query.
        """
        logger.debug(f"Getting multiple {self.model.__name__}s, skip={skip}, limit={limit}")
        try:
            # Basic query with offset and limit for pagination.
            return self.db.query(self.model).offset(skip).limit(limit).all()
        except SQLAlchemyError as e:
            logger.error(f"Database error getting multiple {self.model.__name__}s: {e}", exc_info=True)
            raise

    def create(self, *, obj_in_data: Dict[str, Any]) -> ModelType:
        """
        Creates a new object instance and persists it to the database.

        Assumes that the keys in `obj_in_data` correspond to the attribute
        names defined in the `ModelType` and that the model's `__init__`
        can accept these as keyword arguments.

        Args:
            obj_in_data: A dictionary where keys are attribute names and values
                         are the desired values for the new object.

        Returns:
            The newly created and persisted model instance, refreshed to
            include any database-generated defaults (like primary keys).

        Raises:
            SQLAlchemyError: If a database error occurs during add, commit, or refresh.
                             The session is rolled back before re-raising.
        """
        logger.debug(f"Creating new {self.model.__name__}")
        # Instantiate the model using the provided data dictionary.
        # This requires the model's __init__ to support this pattern.
        db_obj = self.model(**obj_in_data)
        try:
            self.db.add(db_obj)  # Add the new object to the session.
            self.db.commit()    # Persist changes to the database.
            self.db.refresh(db_obj) # Update the instance with DB defaults (e.g., ID).
            # Attempt to log the ID of the created object if it has an 'id' attribute.
            obj_id = getattr(db_obj, 'id', '[unknown ID]')
            logger.info(f"Created {self.model.__name__} with id: {obj_id}")
            return db_obj
        except SQLAlchemyError as e:
            logger.error(f"Database error creating {self.model.__name__}: {e}", exc_info=True)
            self.db.rollback() # Roll back the transaction on error.
            raise

    def update(
        self,
        *,
        db_obj: ModelType,
        obj_in_data: Dict[str, Any]
        # Union type for obj_in can be added later if using Pydantic schemas:
        # obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        """
        Updates an existing object instance in the database.

        Iterates through the `obj_in_data` dictionary and sets the corresponding
        attributes on the provided `db_obj` model instance.

        Args:
            db_obj: The existing SQLAlchemy model instance to update. This object
                    should already be associated with the session or loaded from it.
            obj_in_data: A dictionary containing the attributes to update. Keys
                         should correspond to model attribute names.

        Returns:
            The updated model instance, refreshed from the database.

        Raises:
            SQLAlchemyError: If a database error occurs during commit or refresh.
                             The session is rolled back before re-raising.
        """
        # Retrieve the object's ID for logging, if available.
        obj_id = getattr(db_obj, 'id', '[unknown ID]')
        logger.debug(f"Updating {self.model.__name__} id: {obj_id}")

        # Iterate over the provided data and update the model instance.
        for field, value in obj_in_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
            else:
                 # Log a warning if a field in the input data doesn't exist on the model.
                 logger.warning(f"Field '{field}' not found in model {self.model.__name__} during update for ID {obj_id}.")

        try:
            # Add the modified object to the session (marks it as dirty).
            # If the object was already persistent, add() is usually a no-op
            # but ensures it's tracked if detached/re-attached.
            self.db.add(db_obj)
            self.db.commit()    # Persist the changes.
            self.db.refresh(db_obj) # Refresh the instance state from the DB.
            logger.info(f"Updated {self.model.__name__} with id: {obj_id}")
            return db_obj
        except SQLAlchemyError as e:
            logger.error(f"Database error updating {self.model.__name__} id {obj_id}: {e}", exc_info=True)
            self.db.rollback() # Roll back the transaction on error.
            raise

    def remove(self, *, id: Any) -> Optional[ModelType]:
        """
        Removes an object from the database by its primary key.

        First retrieves the object using `self.get(id)`, then deletes it
        if found.

        Args:
            id: The primary key of the object to remove.

        Returns:
            The removed model instance if it was found and deleted successfully,
            otherwise None if the object was not found.

        Raises:
            SQLAlchemyError: If a database error occurs during delete or commit.
                             The session is rolled back before re-raising.
        """
        logger.debug(f"Attempting to remove {self.model.__name__} with id: {id}")
        # Fetch the object first.
        obj = self.get(id)
        if obj:
            try:
                self.db.delete(obj) # Mark the object for deletion.
                self.db.commit()    # Persist the deletion.
                logger.info(f"Successfully removed {self.model.__name__} with id: {id}")
                return obj # Return the deleted object (now detached from session).
            except SQLAlchemyError as e:
                # Log using the ID available on the object, if possible.
                obj_id = getattr(obj, 'id', id)
                logger.error(f"Database error removing {self.model.__name__} id {obj_id}: {e}", exc_info=True)
                self.db.rollback() # Roll back the transaction on error.
                raise
        else:
            # Log a warning if the object to be removed wasn't found.
            logger.warning(f"{self.model.__name__} with id: {id} not found for removal.")
            return None