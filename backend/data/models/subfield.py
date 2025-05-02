"""
backend.data.models.subfield
----------------------------
This module defines the Subfield model, representing the third-level subject
classification (Subfield) from the OpenAlex dataset, nested under Fields.
"""

import logging
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import String, Text, Integer, ForeignKey, Index
from sqlalchemy.orm import relationship, Mapped, mapped_column

# Assuming Base and BaseModel are correctly defined elsewhere
# Adjust import paths as necessary
from ..database import Base
from .base import BaseModel

# Use TYPE_CHECKING to prevent circular imports for type hints
if TYPE_CHECKING:
    from .field import Field # For the many-to-one relationship to Field
    from .topic import Topic # For the one-to-many relationship to Topics

logger = logging.getLogger(__name__)

class Subfield(BaseModel, Base):
    """
    Represents an OpenAlex Subfield, the third tier in the subject hierarchy.

    Subfields provide a more granular classification than Fields (e.g., "Databases"
    within the "Computer science" Field -> "Data management" Subfield). Each Subfield
    belongs to exactly one Field and contains multiple Topics.

    Inherits common fields like `id`, `created_at`, `updated_at` from `BaseModel`.

    Attributes:
        openalex_id: The unique identifier for this Subfield in OpenAlex (e.g., "S12345").
        display_name: The human-readable name of the Subfield (e.g., "Data management").
        description: An optional longer description of the Subfield's scope.
        field_id: Foreign key linking this Subfield to its parent Field.
        field: Many-to-one relationship back to the parent Field object.
        topics: One-to-many relationship linking this Subfield to its constituent Topics.
    """
    __tablename__ = "subfields"

    # --- Identifiers and Details ---
    # Core attributes defining the Subfield based on OpenAlex data.

    # OpenAlex unique ID for the Subfield. Indexed for fast lookups.
    openalex_id: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)

    # Human-readable name. Indexed for searching and display.
    display_name: Mapped[str] = mapped_column(String, index=True, nullable=False)

    # Optional textual description provided by OpenAlex.
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # --- Foreign Key to Parent Field ---
    # Establishes the hierarchical link within the subject classification.
    field_id: Mapped[int] = mapped_column(
        ForeignKey("fields.id", ondelete="CASCADE"), # Links to the parent Field
        index=True, # Index for efficient lookup of Subfields within a Field
        nullable=False
        # 'ondelete="CASCADE"' ensures that if a Field is deleted, all its child
        # Subfields (and consequently their Topics) are also deleted.
    )

    # --- Relationships ---
    # Defines how Subfields connect to other parts of the subject hierarchy.

    # Many-to-One relationship: Many Subfields belong to one Field.
    # `back_populates` establishes the bidirectional link to the 'subfields' collection
    # defined in the Field model.
    field: Mapped["Field"] = relationship(back_populates="subfields")

    # One-to-Many relationship: A Subfield encompasses multiple Topics.
    # `back_populates` establishes the bidirectional link to the 'subfield' attribute
    # defined in the Topic model.
    # `cascade="all, delete-orphan"` ensures that if a Subfield is deleted, all its
    # associated Topics are also removed from the database.
    topics: Mapped[List["Topic"]] = relationship(
        back_populates="subfield",
        cascade="all, delete-orphan"
    )

    # --- Table Arguments ---
    # Explicitly define indexes for optimized query performance.
    __table_args__ = (
        # Index on OpenAlex ID (unique already implies index, but explicit).
        Index('ix_subfields_openalex_id', 'openalex_id'),
        # Index on display name for text searches or sorting.
        Index('ix_subfields_display_name', 'display_name'),
        # Index on the foreign key to the parent Field (already indexed via column def, but explicit).
        Index('ix_subfields_field_id', 'field_id'),
    )

    def __repr__(self):
        """Provides a concise string representation for debugging and logging."""
        # Safely access 'id' which comes from BaseModel
        obj_id = getattr(self, 'id', None)
        return f"<Subfield(id={obj_id}, name='{self.display_name}', oa_id='{self.openalex_id}')>"