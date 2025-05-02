"""
backend.data.models.work
------------------------
This module defines the Work model, representing a scholarly work such as
a journal article, conference paper, book chapter, dataset, etc., typically
identified via sources like OpenAlex or Crossref using DOIs.
"""

from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, Text, Index, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column

# Assuming Base and BaseModel are correctly defined elsewhere
# Adjust import paths as necessary
from ..database import Base
from .base import BaseModel

# Use TYPE_CHECKING to prevent circular imports for type hints,
# necessary for defining relationships to other models.
if TYPE_CHECKING:
    from .doi_reference import DOIReference # Links DOIs found in repos back to this Work
    from .authorship import Authorship     # Links Persons (authors) to this Work
    from .work_citation import WorkCitation # Links this Work to cited/citing Works
    from .work_topic import WorkTopic       # Links this Work to classification Topics

class Work(BaseModel, Base):
    """
    Represents a scholarly work (e.g., paper, dataset, book chapter).

    This model stores metadata about individual scholarly outputs, identified
    primarily by their OpenAlex ID and DOI. It connects to related entities like
    authors (via Authorship), institutions (via Authorship -> Affiliation),
    citations, references, topics, and instances where its DOI was found in code
    repositories.

    Inherits common fields like `id`, `created_at`, `updated_at` from `BaseModel`.

    Attributes:
        openalex_id: The unique identifier for this work in OpenAlex.
        doi: The Digital Object Identifier (DOI) for the work. Unique and indexed.
        title: The title of the work.
        publication_year: The year the work was published. Indexed.
        type: The type of work (e.g., 'journal-article', 'book-chapter'). Indexed.
        cited_by_count: The number of times this work has been cited (according to source).
        host_venue_display_name: Name of the publication venue (e.g., journal name).
        openalex_url: URL to the work's page on OpenAlex.
        doi_references: Relationship to DOIReference records linking this Work to repositories.
        authorships: Relationship to Authorship records linking authors (Persons) to this Work.
        references: Relationship to WorkCitation records where this Work is the *citing* work.
        citations: Relationship to WorkCitation records where this Work is the *cited* work.
        topics: Relationship to WorkTopic records linking this Work to subject Topics.
    """
    __tablename__ = "works"

    # --- Identifiers ---
    # Key unique identifiers for the scholarly work.

    # OpenAlex unique ID. Essential for linking with OpenAlex data. Indexed.
    openalex_id: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    # Digital Object Identifier. Should be unique and is crucial for resolution. Indexed.
    doi: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)

    # --- Core Metadata ---
    # Descriptive information about the work.

    # Title of the publication. Text allows for long titles.
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Year of publication. Indexed for filtering by year.
    publication_year: Mapped[Optional[int]] = mapped_column(Integer, index=True, nullable=True)
    # Type of publication according to OpenAlex taxonomy. Indexed.
    type: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)
    # Citation count as reported by the data source (e.g., OpenAlex).
    cited_by_count: Mapped[Optional[int]] = mapped_column(Integer, default=0, nullable=True)
    # Display name of the host venue (journal, conference proceedings, etc.).
    host_venue_display_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # URL linking back to the OpenAlex page for this work.
    openalex_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # --- Relationships ---
    # Defines connections to other relevant data models.

    # One-to-Many: A Work's DOI can be referenced multiple times in different repositories/files.
    # `back_populates` links to the 'work' attribute in DOIReference.
    # `cascade` ensures associated DOIReferences are deleted if the Work is deleted.
    doi_references: Mapped[List["DOIReference"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan"
    )

    # One-to-Many: A Work typically has multiple Authorships (one per author).
    # `back_populates` links to the 'work' attribute in Authorship.
    # `cascade` ensures Authorships (and their Affiliations) are deleted if the Work is deleted.
    authorships: Mapped[List["Authorship"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan"
    )

    # One-to-Many (Self-Referential via WorkCitation): Represents works *cited by* this work.
    # `foreign_keys` specifies that this relationship uses the `citing_work_id` column in WorkCitation.
    # `back_populates` links to the 'citing_work' attribute in WorkCitation.
    # `cascade` ensures citation links are removed if this (citing) work is deleted.
    references: Mapped[List["WorkCitation"]] = relationship(
        foreign_keys="WorkCitation.citing_work_id",
        back_populates="citing_work",
        cascade="all, delete-orphan"
    )

    # One-to-Many (Self-Referential via WorkCitation): Represents works *that cite* this work.
    # `foreign_keys` specifies that this relationship uses the `cited_work_id` column in WorkCitation.
    # `back_populates` links to the 'cited_work' attribute in WorkCitation.
    # `cascade` ensures citation links are removed if this (cited) work is deleted.
    citations: Mapped[List["WorkCitation"]] = relationship(
        foreign_keys="WorkCitation.cited_work_id",
        back_populates="cited_work",
        cascade="all, delete-orphan"
    )

    # One-to-Many: A Work can be associated with multiple Topics via the WorkTopic association table.
    # `back_populates` links to the 'work' attribute in the WorkTopic model.
    # `cascade` ensures WorkTopic entries are deleted if the Work is deleted.
    topics: Mapped[List["WorkTopic"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan"
    )

    # --- Table Arguments ---
    # Define explicit indexes for commonly queried metadata fields.
    __table_args__ = (
        # Index on publication type for filtering.
        Index('ix_works_type', 'type'),
        # Index on publication year for filtering or sorting by year.
        Index('ix_works_publication_year', 'publication_year'),
        # Note: Indexes on openalex_id and doi are created due to unique=True.
    )

    def __repr__(self):
        """Provides a concise string representation for debugging and logging."""
        # Safely access 'id' which comes from BaseModel
        obj_id = getattr(self, 'id', None)
        # Truncate title for brevity
        title_repr = (self.title[:50] + '...') if self.title and len(self.title) > 50 else self.title or '[No Title]'
        return f"<Work(id={obj_id}, doi='{self.doi}', title='{title_repr}')>"