"""
backend.data.models.authorship
------------------------------
This module defines the Authorship model, representing the link between
a Person (author) and a Work (publication, dataset, etc.). It serves as
an association object, potentially holding metadata specific to that
author's contribution to that work.
"""

import logging
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, Boolean, ForeignKey, Index

from sqlalchemy.orm import relationship, Mapped, mapped_column

# Assuming Base is correctly defined in ..database
# Adjust the import path if necessary
from ..database import Base

# Use TYPE_CHECKING to avoid circular imports during runtime
# Needed for type hinting relationships, especially back-references.
if TYPE_CHECKING:
    from .work import Work
    from .person import Person
    from .affiliation import Affiliation # Required for the 'affiliations' relationship

logger = logging.getLogger(__name__)

class Authorship(Base):
    """
    Represents the association between a Person (author) and a Work.

    This model acts as an association table connecting 'persons' and 'works' tables
    in a many-to-many relationship. It includes additional attributes specific
    to the authorship itself, such as the author's position in the author list
    and whether they are marked as a corresponding author. It uses a composite
    primary key consisting of the foreign keys to Person and Work.

    Attributes:
        work_id: Foreign key referencing the Work's primary key. Part of the composite PK.
        person_id: Foreign key referencing the Person's primary key. Part of the composite PK.
        author_position: Describes the author's position (e.g., 'first', 'last').
        is_corresponding: Flag indicating if this author is a corresponding author.
        work: Relationship back to the Work object.
        person: Relationship back to the Person object.
        affiliations: Relationship to associated Affiliation records for this specific authorship.
    """
    __tablename__ = "authorships"

    # --- Composite Primary Key and Foreign Keys ---
    # Define the composite primary key using the foreign keys to Work and Person.
    # This uniquely identifies a specific author's contribution to a specific work.
    work_id: Mapped[int] = mapped_column(
        # Define the foreign key constraint to the 'works' table.
        ForeignKey("works.id", ondelete="CASCADE"),
        primary_key=True # This column is part of the composite primary key.
        # 'ondelete="CASCADE"' ensures that if a Work is deleted, all its Authorship
        # records (and consequently their Affiliations) are also deleted.
    )
    person_id: Mapped[int] = mapped_column(
        # Define the foreign key constraint to the 'persons' table.
        ForeignKey("persons.id", ondelete="CASCADE"),
        primary_key=True # This column is also part of the composite primary key.
        # 'ondelete="CASCADE"' ensures that if a Person is deleted, all their Authorship
        # records (and consequently their Affiliations) are also deleted.
    )

    # --- Authorship Metadata ---
    # Optional fields providing more context about the specific authorship role.
    author_position: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    ) # E.g., 'first', 'middle', 'last' - useful for author contribution analysis.
    is_corresponding: Mapped[Optional[bool]] = mapped_column(
        Boolean, nullable=True
    ) # Indicates if this author handled correspondence for the publication.

    # --- Relationships ---
    # Define bidirectional relationships for easier data access and navigation.

    # Relationship to the Work this authorship belongs to.
    # `back_populates` links this to the 'authorships' collection on the Work model.
    work: Mapped["Work"] = relationship(back_populates="authorships")

    # Relationship to the Person (author) this authorship represents.
    # `back_populates` links this to the 'authorships' collection on the Person model.
    person: Mapped["Person"] = relationship(back_populates="authorships")

    # One-to-Many relationship: An Authorship can have multiple associated Affiliations
    # (e.g., author listed multiple institutions on the paper).
    # `back_populates` links this to the 'authorship' attribute on the Affiliation model.
    affiliations: Mapped[List["Affiliation"]] = relationship(
        back_populates="authorship",
        # 'cascade="all, delete-orphan"' means that if an Authorship record is deleted,
        # all Affiliation records associated *only* with this Authorship will also be deleted.
        # Operations like adding an Affiliation via this Authorship object will be cascaded.
        cascade="all, delete-orphan"
    )

    # --- Table Arguments ---
    # Define explicit indexes on the foreign key columns. While the composite primary key
    # provides an index on (work_id, person_id), separate indexes on each column
    # can improve performance for queries filtering only by work_id or only by person_id.
    __table_args__ = (
        Index('ix_authorships_work_id', 'work_id'),
        Index('ix_authorships_person_id', 'person_id'),
    )

    def __repr__(self):
        """Provides a concise string representation for debugging and logging."""
        return f"<Authorship(work_id={self.work_id}, person_id={self.person_id})>"