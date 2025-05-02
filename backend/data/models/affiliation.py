"""
backend.data.models.affiliation
-------------------------------
This module defines the Affiliation model, representing the link between
an author's contribution to a specific work (Authorship) and an
Institution they were affiliated with at that time.
"""

import logging
from typing import TYPE_CHECKING
from sqlalchemy import Integer, ForeignKey, Index, ForeignKeyConstraint

from sqlalchemy.orm import relationship, Mapped, mapped_column

# Assuming Base is correctly defined in ..database
# Adjust the import path if necessary
from ..database import Base

# Use TYPE_CHECKING to avoid circular imports during runtime
# Useful for type hinting relationships
if TYPE_CHECKING:
    from .authorship import Authorship
    from .institution import Institution

logger = logging.getLogger(__name__)

class Affiliation(Base):
    """
    Represents the association between an Authorship (Work+Person) and an Institution.

    An author might have multiple affiliations for a single work (e.g., joint appointments
    or affiliations listed on the publication). This table captures those specific links.
    It uses a composite primary key derived from the Authorship and Institution it links.

    Attributes:
        authorship_work_id: Part of the composite PK, referencing Work.id via Authorship.
        authorship_person_id: Part of the composite PK, referencing Person.id via Authorship.
        institution_id: Part of the composite PK, referencing Institution.id.
        authorship: Relationship back to the specific Authorship record.
        institution: Relationship back to the specific Institution record.
    """
    __tablename__ = "affiliations"

    # --- Composite Primary Key Definition ---
    # Part 1: Foreign key components referencing the Authorship composite PK.
    # These columns, along with institution_id, uniquely identify an affiliation record.
    authorship_work_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    authorship_person_id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Part 2: Foreign key to the Institution's primary key.
    institution_id: Mapped[int] = mapped_column(
        # Define the foreign key constraint directly here
        ForeignKey("institutions.id", ondelete="CASCADE"),
        primary_key=True # This column is also part of the composite primary key
    )

    # --- Relationships ---
    # Define bidirectional relationships for easier navigation in SQLAlchemy queries.

    # Relationship to the Authorship record this affiliation belongs to.
    # `back_populates` links this to the 'affiliations' collection on the Authorship model.
    authorship: Mapped["Authorship"] = relationship(back_populates="affiliations")

    # Relationship to the Institution this affiliation points to.
    # `back_populates` links this to the 'affiliations' collection on the Institution model.
    institution: Mapped["Institution"] = relationship(back_populates="affiliations")

    # --- Table Arguments ---
    # Includes composite foreign key constraints and indexes for performance.
    __table_args__ = (
        # Explicitly define the composite foreign key constraint for the Authorship relationship.
        # This ensures referential integrity at the database level.
        # 'ondelete="CASCADE"' ensures that if an Authorship record is deleted,
        # all corresponding Affiliation records are also automatically deleted.
        ForeignKeyConstraint(
            ['authorship_work_id', 'authorship_person_id'],
            ['authorships.work_id', 'authorships.person_id'],
            ondelete="CASCADE",
            name='fk_affiliation_authorship' # Optional: Provides a specific name for the constraint
        ),
        # Define indexes on individual foreign key columns to speed up lookups
        # based on institution or parts of the authorship key.
        Index('ix_affiliations_institution_id', 'institution_id'),
        Index('ix_affiliations_authorship_work_id', 'authorship_work_id'),
        Index('ix_affiliations_authorship_person_id', 'authorship_person_id'),
        # Note: The composite primary key implicitly creates an index on (work_id, person_id, inst_id).
    )

    def __repr__(self):
        """Provides a developer-friendly string representation of the Affiliation."""
        return (f"<Affiliation(work={self.authorship_work_id}, "
                f"person={self.authorship_person_id}, inst={self.institution_id})>")