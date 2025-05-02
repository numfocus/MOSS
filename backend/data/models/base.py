"""
backend.data.models.base
------------------------
This module defines a base mixin class (`BaseModel`) providing common columns
like an integer primary key (`id`) and timestamp fields (`created_at`, `updated_at`)
for other SQLAlchemy models. It leverages the `models.types` module for
consistent type definitions.
"""

# Keep these necessary imports for defining mapped columns and declared attributes
from sqlalchemy.orm import Mapped
from sqlalchemy.ext.declarative import declared_attr

# Import the custom type definitions from the local 'types.py' file
# This promotes consistency and reusability across different models.
from .types import intpk, timestamp_created, timestamp_updated

class BaseModel:
    """
    Base mixin class providing common columns for database models.

    This class is intended to be inherited by other SQLAlchemy models that require
    a standard integer primary key (`id`) and automatic timestamping for creation
    and updates (`created_at`, `updated_at`).

    It uses the `Mapped` annotation style introduced in SQLAlchemy 2.0 and relies
    on custom type annotations (`intpk`, `timestamp_created`, `timestamp_updated`)
    defined in `models.types` for clarity and consistency.

    Note:
        Models inheriting from this mixin should also inherit from the SQLAlchemy
        declarative base (e.g., `Base` from `database.py`).
    """
    # --- Common Columns ---

    # Define the primary key column.
    # `intpk` is an Annotated type likely defining Integer, primary_key=True, etc.
    id: Mapped[intpk]

    # Define the creation timestamp column.
    # `timestamp_created` is an Annotated type likely defining DateTime(timezone=True)
    # with a server_default of the current time. It's not updatable.
    created_at: Mapped[timestamp_created]

    # Define the update timestamp column.
    # `timestamp_updated` is an Annotated type likely defining DateTime(timezone=True)
    # with a server_default and an onupdate trigger to set the current time.
    updated_at: Mapped[timestamp_updated]


    # --- Optional: Automatic Tablename Generation ---
    # This commented-out section shows how you could automatically generate
    # table names based on the class name (e.g., 'MyModel' -> 'mymodels').
    # Uncomment and adapt if this convention is desired project-wide.
    # @declared_attr
    # def __tablename__(cls):
    #     # Example: Converts 'ModelName' to 'modelnames'
    #     return cls.__name__.lower() + "s"