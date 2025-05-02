"""
backend.data.models.work_citation
---------------------------------
This module defines the WorkCitation model, an association table representing
a citation link between two scholarly Works. It captures the directed
relationship: 'citing_work' cites 'cited_work'.
"""

import logging
from typing import TYPE_CHECKING
from sqlalchemy import Integer, ForeignKey, Index

from sqlalchemy.orm import relationship, Mapped, mapped_column

# Assuming Base is correctly defined elsewhere
# Adjust import path as necessary
from ..database import Base

# Use TYPE_CHECKING to prevent circular imports for type hints, crucial for
# the self-referential relationships back to the Work model.
if TYPE_CHECKING:
    from .work import Work

logger = logging.getLogger(__name__)

class WorkCitation(Base):
    """
    Represents a citation link between two Works (citing -> cited).

    This model acts as an association table for a many-to-many relationship
    of the Work model with itself. Each row signifies that the work identified
    by `citing_work_id` includes a citation to the work identified by
    `cited_work_id`.

    It uses a composite primary key consisting of the two foreign keys. It
    inherits directly from `Base`.

    Attributes:
        citing_work_id: Foreign key to the Work that contains the citation. Part of PK.
        cited_work_id: Foreign key to the Work that is being cited. Part of PK.
        citing_work: Relationship back to the Work object that is citing.
        cited_work: Relationship back to the Work object that is being cited.
    """
    __tablename__ = "work_citations"

    # --- Composite Primary Key and Foreign Keys ---
    # These two columns together uniquely identify a single citation instance.

    # Foreign key referencing the Work that performs the citation. Part of the composite PK.
    # `ondelete="CASCADE"` ensures that if the citing work is deleted, this citation link is removed.
    citing_work_id: Mapped[int] = mapped_column(
        ForeignKey("works.id", ondelete="CASCADE"), primary_key=True
    )
    # Foreign key referencing the Work that receives the citation. Part of the composite PK.
    # `ondelete="CASCADE"` ensures that if the cited work is deleted, this citation link is removed.
    cited_work_id: Mapped[int] = mapped_column(
        ForeignKey("works.id", ondelete="CASCADE"), primary_key=True
    )

    # --- Relationships ---
    # Define relationships back to the Work model for easier navigation.
    # Because both foreign keys point to the same table ('works'), we must explicitly
    # specify which foreign key corresponds to which relationship using `foreign_keys`.

    # Relationship to the Work entity that contains the citation (the citing work).
    # `foreign_keys=[citing_work_id]` specifies this relationship uses the citing_work_id FK.
    # `back_populates="references"` links this to the 'references' collection on the Work model
    # (representing the list of works *cited by* that Work).
    citing_work: Mapped["Work"] = relationship(
        foreign_keys=[citing_work_id],
        back_populates="references" # Corresponds to Work.references
    )

    # Relationship to the Work entity that is being cited (the cited work).
    # `foreign_keys=[cited_work_id]` specifies this relationship uses the cited_work_id FK.
    # `back_populates="citations"` links this to the 'citations' collection on the Work model
    # (representing the list of works *that cite* that Work).
    cited_work: Mapped["Work"] = relationship(
        foreign_keys=[cited_work_id],
        back_populates="citations" # Corresponds to Work.citations
    )

    # --- Table Arguments ---
    # Define explicit indexes on the individual foreign key columns.
    # While the composite primary key creates an index on (citing_work_id, cited_work_id),
    # these single-column indexes improve performance for queries filtering only by
    # the citing work or only by the cited work (e.g., finding all references for a work,
    # or finding all citations of a work).
    __table_args__ = (
        Index('ix_work_citations_citing_work_id', 'citing_work_id'),
        Index('ix_work_citations_cited_work_id', 'cited_work_id'),
    )

    def __repr__(self):
        """Provides a concise string representation for debugging and logging."""
        return (f"<WorkCitation(citing={self.citing_work_id}, "
                f"cited={self.cited_work_id})>")