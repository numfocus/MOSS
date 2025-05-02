"""
backend.data.models.institution
-------------------------------
This module defines the Institution model, representing organizations such
as universities, companies, hospitals, research labs, etc., primarily identified
through scholarly affiliations (e.g., from OpenAlex data) or potentially
linked to code repositories.
"""

import logging
from typing import List, Optional, TYPE_CHECKING, Dict, Any
# Import JSONB type for handling JSON data in PostgreSQL
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import String, Index

from sqlalchemy.orm import relationship, Mapped, mapped_column

# Assuming Base and BaseModel are correctly defined elsewhere
# Adjust import paths as necessary
from ..database import Base
from .base import BaseModel

# Use TYPE_CHECKING to prevent circular imports for type hints
if TYPE_CHECKING:
    from .affiliation import Affiliation # For the relationship to author affiliations

logger = logging.getLogger(__name__)

class Institution(BaseModel, Base):
    """
    Represents an institution (university, company, hospital, etc.).

    This model stores details about organizations, primarily sourced from external
    databases like OpenAlex or identified through other means (e.g., repository ownership).
    It serves as a central point for linking affiliations and potentially other
    related entities.

    Inherits common fields like `id`, `created_at`, `updated_at` from `BaseModel`.

    Attributes:
        openalex_id: Unique identifier from OpenAlex, if available.
        ror: Research Organization Registry (ROR) identifier, a persistent global ID.
        display_name: The primary human-readable name of the institution.
        country_code: ISO 3166-1 alpha-2 country code (e.g., 'US', 'GB').
        type: Classification of the institution type (e.g., 'education', 'company').
        github_organization_logins: List of known GitHub organization logins associated
                                    with this institution. Stored as JSON.
        affiliations: One-to-many relationship linking this institution to Affiliation
                      records (representing author affiliations on works).
    """
    __tablename__ = "institutions"

    # --- Identifiers ---
    # Key identifiers linking this record to external systems.

    # OpenAlex unique ID. Crucial for linking with OpenAlex publication data. Indexed.
    openalex_id: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)

    # Research Organization Registry ID. A globally unique and persistent identifier. Indexed.
    ror: Mapped[Optional[str]] = mapped_column(String, unique=True, index=True, nullable=True)

    # --- Descriptive Details ---
    # Core information about the institution.

    # The common name of the institution. Indexed for search and display.
    display_name: Mapped[str] = mapped_column(String, index=True, nullable=False)

    # Two-letter country code based on ISO 3166-1 alpha-2 standard.
    country_code: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)

    # Categorization based on OpenAlex types (e.g., 'education', 'healthcare', 'company'). Indexed.
    type: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)

    # --- GitHub Association (Added Field) ---
    # Stores potential GitHub Organization logins linked to this institution.
    # This facilitates linking repositories or contributors directly via known orgs.
    # Populated manually or via specific discovery/matching processes.
    github_organization_logins: Mapped[Optional[List[str]]] = mapped_column(
        JSONB, # Use JSONB for efficient storage and querying of list data in PostgreSQL.
        nullable=True
    )

    # --- Relationships ---
    # Defines how Institutions connect to other models.

    # One-to-Many relationship: An Institution can be listed in many Affiliations
    # across different authorships (Work + Person combinations).
    # `back_populates` establishes the bidirectional link to the 'institution' attribute
    # defined in the Affiliation model.
    # `cascade="all, delete-orphan"` means if an Institution is deleted, the corresponding
    # Affiliation records linking *to* this institution are also deleted. Consider if this
    # cascade behavior is always desired, as it removes authorship affiliation data.
    # An alternative might be to set the FK to NULL or prevent deletion if affiliations exist.
    affiliations: Mapped[List["Affiliation"]] = relationship(
        back_populates="institution",
        cascade="all, delete-orphan"
    )

    # --- Table Arguments ---
    # Explicitly define indexes for optimized query performance.
    # Indexes on unique columns are often created automatically but defining them here
    # provides clarity and central management.
    __table_args__ = (
        Index('ix_institutions_openalex_id', 'openalex_id'), # Index on OpenAlex ID
        Index('ix_institutions_ror', 'ror'),                 # Index on ROR ID
        Index('ix_institutions_display_name', 'display_name'),# Index on name for searching
        Index('ix_institutions_type', 'type'),               # Index for filtering by type
    )

    def __repr__(self):
        """Provides a concise string representation for debugging and logging."""
        # Uses getattr for id in case the instance isn't flushed yet
        obj_id = getattr(self, 'id', None)
        ror_repr = f", ror={self.ror}" if self.ror else ""
        return f"<Institution(id={obj_id}, name='{self.display_name}'{ror_repr})>"