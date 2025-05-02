"""
backend.data.models.types
-------------------------
This module centralizes common SQLAlchemy column type definitions using
typing.Annotated and mapped_column. This promotes consistency and DRY (Don't
Repeat Yourself) principles across different model definitions.
"""

from typing import Annotated
from datetime import datetime
from sqlalchemy import Integer, DateTime, func
from sqlalchemy.orm import mapped_column

# --- Annotated Type Definitions for SQLAlchemy Columns ---
# Using typing.Annotated allows us to bundle the Python type hint (e.g., int, datetime)
# with the specific SQLAlchemy `mapped_column` configuration. This makes model
# definitions cleaner and ensures consistent column properties (like timezone,
# server defaults) are applied wherever these types are used.

# Define a standard integer primary key column.
# Includes auto-incrementing, indexing, and marking as the primary key.
intpk = Annotated[
    int, # Python type hint
    mapped_column(Integer, primary_key=True, index=True, autoincrement=True) # SQLAlchemy config
]

# Define a standard timestamp column, ensuring timezone awareness.
# It expects a Python `datetime` object and maps to a database DateTime type
# that stores timezone information (e.g., TIMESTAMPTZ in PostgreSQL).
timestamp = Annotated[
    datetime, # Python type hint
    mapped_column(DateTime(timezone=True), nullable=False) # SQLAlchemy config: timezone=True, not nullable
]

# Define a nullable version of the standard timestamp column.
# Useful for optional timestamps like 'completed_at' or 'deleted_at'.
timestamp_nullable = Annotated[
    datetime, # Python type hint
    mapped_column(DateTime(timezone=True), nullable=True) # SQLAlchemy config: timezone=True, nullable
]

# Define a timestamp column specifically for tracking creation time.
# Automatically sets the timestamp using the database's clock (`func.now()`)
# when a record is first inserted (`server_default`). It is not nullable.
timestamp_created = Annotated[
    datetime, # Python type hint
    mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
]

# Define a timestamp column specifically for tracking the last update time.
# Automatically sets the timestamp on creation (`server_default`) and updates
# it whenever the record is modified (`onupdate`). It is not nullable.
timestamp_updated = Annotated[
    datetime, # Python type hint
    mapped_column(
        DateTime(timezone=True),
        server_default=func.now(), # Set on creation
        onupdate=func.now(),      # Update on modification
        nullable=False
    )
]