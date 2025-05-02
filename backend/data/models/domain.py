"""
backend.data.models.domain
--------------------------
This module defines the Domain model, representing the highest-level subject
classification (Domain) from the OpenAlex dataset.
"""

import logging
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import String, Text, Index
from sqlalchemy.orm import relationship, Mapped, mapped_column

# Assuming Base and BaseModel are correctly defined elsewhere
# Adjust import paths as necessary
from ..database import Base
from .base import BaseModel

# Use TYPE_CHECKING to prevent circular imports for type hints
if TYPE_CHECKING:
    from .field import Field # For the one-to-many relationship to Fields

logger = logging.getLogger(__name__)

class Domain(BaseModel, Base):
    """
    Represents an OpenAlex Domain, the top tier in the subject hierarchy.

    Domains categorize broad areas of knowledge (e.g., "Medicine", "Physics").
    Each Domain contains multiple Fields.

    Inherits common fields like `id`, `created_at`, `updated_at` from `BaseModel`.

    Attributes:
        openalex_id: The unique identifier for this Domain in OpenAlex (e.g., "D12345").
        display_name: The human-readable name of the Domain (e.g., "Computer science").
        description: An optional longer description of the Domain's scope.
        fields: One-to-many relationship linking this Domain to its constituent Fields.
    """
    __tablename__ = "domains"

    # --- Identifiers and Details ---
    # Core attributes defining the Domain based on OpenAlex data.

    # OpenAlex unique ID for the Domain. Indexed for fast lookups.
    openalex_id: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)

    # Human-readable name. Indexed for searching and display.
    display_name: Mapped[str] = mapped_column(String, index=True, nullable=False)

    # Optional textual description provided by OpenAlex.
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # --- Relationships ---
    # Defines how Domains connect to other parts of the subject hierarchy.

    # One-to-Many relationship: A Domain encompasses multiple Fields.
    # `back_populates` establishes the bidirectional link to the 'domain' attribute
    # defined in the Field model.
    # `cascade="all, delete-orphan"` ensures that if a Domain is deleted, all its
    # associated Fields are also removed from the database.
    fields: Mapped[List["Field"]] = relationship(
        back_populates="domain",
        cascade="all, delete-orphan"
    )

    # --- Table Arguments ---
    # Explicitly define indexes for optimized query performance.
    __table_args__ = (
        # Redundant index on openalex_id (already unique), but explicitly defined for clarity.
        Index('ix_domains_openalex_id', 'openalex_id'),
        # Index on display_name for faster text-based searches or sorting.
        Index('ix_domains_display_name', 'display_name'),
    )

    def __repr__(self):
        """Provides a concise string representation for debugging and logging."""
        # Uses getattr for id in case the instance isn't flushed yet
        obj_id = getattr(self, 'id', None)
        return f"<Domain(id={obj_id}, name='{self.display_name}', oa_id='{self.openalex_id}')>"