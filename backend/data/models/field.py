"""
backend.data.models.field
-------------------------
This module defines the Field model, representing the second-level subject
classification (Field) from the OpenAlex dataset, nested under Domains.
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
    from .domain import Domain     # For the many-to-one relationship to Domain
    from .subfield import Subfield # For the one-to-many relationship to Subfields

logger = logging.getLogger(__name__)

class Field(BaseModel, Base):
    """
    Represents an OpenAlex Field, the second tier in the subject hierarchy.

    Fields provide a more specific classification than Domains (e.g., "Artificial
    intelligence" within the "Computer science" Domain). Each Field belongs to
    exactly one Domain and contains multiple Subfields.

    Inherits common fields like `id`, `created_at`, `updated_at` from `BaseModel`.

    Attributes:
        openalex_id: The unique identifier for this Field in OpenAlex (e.g., "F12345").
        display_name: The human-readable name of the Field (e.g., "Artificial intelligence").
        description: An optional longer description of the Field's scope.
        domain_id: Foreign key linking this Field to its parent Domain.
        domain: Many-to-one relationship back to the parent Domain object.
        subfields: One-to-many relationship linking this Field to its constituent Subfields.
    """
    __tablename__ = "fields"

    # --- Identifiers and Details ---
    # Core attributes defining the Field based on OpenAlex data.

    # OpenAlex unique ID for the Field. Indexed for fast lookups.
    openalex_id: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)

    # Human-readable name. Indexed for searching and display.
    display_name: Mapped[str] = mapped_column(String, index=True, nullable=False)

    # Optional textual description provided by OpenAlex.
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # --- Foreign Key to Parent Domain ---
    # Establishes the hierarchical link within the subject classification.
    domain_id: Mapped[int] = mapped_column(
        ForeignKey("domains.id", ondelete="CASCADE"), # Links to the parent Domain
        index=True, # Index for efficient lookup of Fields within a Domain
        nullable=False
        # 'ondelete="CASCADE"' ensures that if a Domain is deleted, all its child
        # Fields (and consequently their Subfields, etc.) are also deleted.
    )

    # --- Relationships ---
    # Defines how Fields connect to other parts of the subject hierarchy.

    # Many-to-One relationship: Many Fields belong to one Domain.
    # `back_populates` establishes the bidirectional link to the 'fields' collection
    # defined in the Domain model.
    domain: Mapped["Domain"] = relationship(back_populates="fields")

    # One-to-Many relationship: A Field encompasses multiple Subfields.
    # `back_populates` establishes the bidirectional link to the 'field' attribute
    # defined in the Subfield model.
    # `cascade="all, delete-orphan"` ensures that if a Field is deleted, all its
    # associated Subfields are also removed from the database.
    subfields: Mapped[List["Subfield"]] = relationship(
        back_populates="field",
        cascade="all, delete-orphan"
    )

    # --- Table Arguments ---
    # Explicitly define indexes for optimized query performance.
    __table_args__ = (
        # Redundant index on openalex_id (already unique), but explicit for clarity.
        Index('ix_fields_openalex_id', 'openalex_id'),
        # Index on display_name for faster text-based searches or sorting.
        Index('ix_fields_display_name', 'display_name'),
        # Index on domain_id (already indexed via column definition, but explicit).
        Index('ix_fields_domain_id', 'domain_id'),
    )

    def __repr__(self):
        """Provides a concise string representation for debugging and logging."""
        # Uses getattr for id in case the instance isn't flushed yet
        obj_id = getattr(self, 'id', None)
        return f"<Field(id={obj_id}, name='{self.display_name}', oa_id='{self.openalex_id}')>"