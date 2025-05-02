"""
backend.data.models.doi_reference
---------------------------------
This module defines the DOIReference model, which records each instance
where a Digital Object Identifier (DOI) is found within a specific file
of a tracked repository. It links the DOI text to the repository and,
potentially, to the resolved scholarly Work it identifies.
"""

from typing import Optional, TYPE_CHECKING
from sqlalchemy import (
    String, Integer, Text, ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

# Assuming Base and BaseModel are correctly defined elsewhere
# Adjust import paths as necessary
from ..database import Base
from .base import BaseModel

# Use TYPE_CHECKING to prevent circular imports for type hints
if TYPE_CHECKING:
    from .repository import Repository
    from .work import Work

class DOIReference(BaseModel, Base):
    """
    Represents an instance of a DOI found within a repository file.

    This model captures the context of *where* a specific DOI string was found,
    linking it back to the source repository and file. It also holds a potentially
    nullable foreign key to the 'works' table, indicating if the DOI was successfully
    resolved to a known scholarly Work.

    Inherits common fields like `id`, `created_at`, `updated_at` from `BaseModel`.

    Attributes:
        doi: The DOI string exactly as found (or canonicalized).
        repository_id: Foreign key linking to the Repository where the DOI was found.
        work_id: Foreign key linking to the resolved Work (optional, nullable).
        source_file: Path to the file within the repository containing the DOI.
        context: An optional snippet of text surrounding the DOI for context.
        repository: Relationship back to the Repository object.
        work: Relationship back to the resolved Work object (or None).
    """
    __tablename__ = "doi_references"

    # --- Core DOI Information ---
    # The actual DOI string. Indexed for searching by DOI.
    doi: Mapped[str] = mapped_column(String, index=True, nullable=False)

    # --- Foreign Keys ---
    # Link this reference back to its source repository and potentially resolved work.

    # Reference to the Repository where this DOI was located. Indexed.
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id"), index=True, nullable=False
    )
    # Reference to the Work record if the DOI could be resolved. Nullable. Indexed.
    work_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("works.id"), index=True, nullable=True
        # Nullable=True is crucial, as not all found DOIs might resolve
        # or correspond to Works currently in the database.
    )

    # --- Provenance Information ---
    # Details about where exactly the DOI was found within the repository.

    # The file path where the DOI was discovered, e.g., 'README.md', 'paper/references.bib'.
    source_file: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # Optional: Store a small text snippet around the DOI for quick context review.
    context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # --- Relationships ---
    # Define relationships for easy navigation from a DOIReference instance.

    # Relationship to the Repository containing this DOI reference.
    # `back_populates` links to the 'doi_references' collection on the Repository model.
    repository: Mapped["Repository"] = relationship(back_populates="doi_references")

    # Relationship to the Work identified by this DOI, if resolution was successful.
    # `back_populates` links to the 'doi_references' collection on the Work model.
    # This relationship naturally handles the case where work_id is NULL (returns None).
    work: Mapped[Optional["Work"]] = relationship(back_populates="doi_references")

    # --- Table Arguments ---
    # Define indexes and constraints for data integrity and query performance.
    __table_args__ = (
        # Ensure that the same DOI isn't recorded multiple times for the exact same file
        # within the same repository. This prevents duplicate entries from reappearing if
        # a file is scanned multiple times without changes.
        UniqueConstraint('repository_id', 'doi', 'source_file', name='uq_repo_doi_source'),

        # Explicit indexes on individual columns often used in queries.
        # While some are already indexed due to FKs or the `index=True` flag,
        # defining them here provides a central place to manage table-level indexing.
        Index('ix_doi_references_doi', 'doi'),
        Index('ix_doi_references_repository_id', 'repository_id'),
        Index('ix_doi_references_work_id', 'work_id'), # Indexing nullable FK can still be useful.
    )

    def __repr__(self):
        """Provides a concise string representation for debugging and logging."""
        # Uses getattr for id in case the instance isn't flushed yet
        obj_id = getattr(self, 'id', None)
        work_repr = f", work_id={self.work_id}" if self.work_id else ", work_id=None"
        return (f"<DOIReference(id={obj_id}, doi='{self.doi}', "
                f"repo_id={self.repository_id}{work_repr})>")