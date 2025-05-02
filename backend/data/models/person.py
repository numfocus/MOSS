"""
backend.data.models.person
--------------------------
This module defines the Person model, representing an individual identified
primarily through scholarly contributions (e.g., as an author in OpenAlex).
It serves as a distinct entity from a code Contributor, although links
between them might be established later.
"""

import logging
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from sqlalchemy import String, Index
# Import JSONB type for handling JSON data in PostgreSQL, specifically for alternative names.
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column

# Assuming Base and BaseModel are correctly defined elsewhere
# Adjust import paths as necessary
from ..database import Base
from .base import BaseModel

# Use TYPE_CHECKING to prevent circular imports for type hints, especially for relationships.
if TYPE_CHECKING:
    from .authorship import Authorship # For the one-to-many relationship to Authorship records

logger = logging.getLogger(__name__)

class Person(BaseModel, Base):
    """
    Represents a person, typically identified via scholarly metadata sources.

    This model stores information about individuals primarily known through their
    publications or other scholarly works, often sourced from databases like
    OpenAlex. It captures identifiers like OpenAlex ID and ORCID, along with name
    variations.

    Inherits common fields like `id`, `created_at`, `updated_at` from `BaseModel`.

    Attributes:
        openalex_id: The unique identifier for this person in OpenAlex.
        orcid: The person's Open Researcher and Contributor ID (ORCID), if available.
        display_name: The primary, canonical name associated with the person.
        display_name_alternatives: A list of alternative names or variations found
                                   for this person, stored as JSON.
        authorships: One-to-many relationship linking this person to their Authorship
                     records (representing their role on specific Works).
    """
    __tablename__ = "persons"

    # --- Identifiers ---
    # Key unique identifiers linking this person to external scholarly systems.

    # OpenAlex unique ID. Essential for linking to OpenAlex data. Indexed.
    openalex_id: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)

    # ORCID iD provides a persistent digital identifier for researchers. Unique and indexed.
    orcid: Mapped[Optional[str]] = mapped_column(String, unique=True, index=True, nullable=True)

    # --- Name Information ---
    # Stores the person's name and known variations.

    # The primary or most common display name. Indexed for searching.
    display_name: Mapped[str] = mapped_column(String, index=True, nullable=False)

    # Stores a list of alternative names (e.g., ["J. Smith", "Johnathan Smith"])
    # using JSONB for flexibility and efficient querying within the list in PostgreSQL.
    display_name_alternatives: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)

    # --- Relationships ---
    # Defines how Persons connect to their contributions (Works via Authorships).

    # One-to-Many relationship: A Person can have multiple Authorships on different Works.
    # `back_populates` establishes the bidirectional link to the 'person' attribute
    # defined in the Authorship model.
    # `cascade="all, delete-orphan"`: If a Person record is deleted, all associated
    # Authorship records (and consequently their Affiliations) are also deleted.
    # This implies that removing a person removes all their recorded publication links.
    authorships: Mapped[List["Authorship"]] = relationship(
        back_populates="person",
        cascade="all, delete-orphan"
    )

    # --- Table Arguments ---
    # Explicitly define indexes for optimized query performance, particularly on identifiers.
    # While unique=True implies an index, defining them here ensures clarity.
    __table_args__ = (
        Index('ix_persons_openalex_id', 'openalex_id'), # Index on OpenAlex ID
        Index('ix_persons_orcid', 'orcid'),             # Index on ORCID
        Index('ix_persons_display_name', 'display_name'), # Index on primary name for searching
    )

    def __repr__(self):
        """Provides a concise string representation for debugging and logging."""
        # Safely access 'id' which comes from BaseModel
        obj_id = getattr(self, 'id', None)
        orcid_repr = f", orcid={self.orcid}" if self.orcid else ""
        return f"<Person(id={obj_id}, name='{self.display_name}'{orcid_repr})>"