"""
backend.data.models.keyword_repository_association
--------------------------------------------------
This module defines the KeywordRepositoryAssociation model, an association
table linking a specific KeywordSearchSession to a Repository identified
during that search execution.
"""

import logging
from typing import Optional, Dict, Any, TYPE_CHECKING
from sqlalchemy import (
    ForeignKey, Index # Index might be used if specific indexing beyond PK/FK is needed
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column

# Assuming Base is correctly defined elsewhere
# Adjust import path as necessary
from ..database import Base

logger = logging.getLogger(__name__)

# Use TYPE_CHECKING to prevent circular imports for type hints,
# although direct relationships are commented out in this version.
if TYPE_CHECKING:
    from .keyword_search_session import KeywordSearchSession
    from .repository import Repository

class KeywordRepositoryAssociation(Base):
    """
    Association table linking KeywordSearchSessions to discovered Repositories.

    This model represents a many-to-many relationship join between a search
    session and the repositories found as results of that search. It uses a
    composite primary key consisting of the foreign keys to the session and
    the repository. It can optionally store details about why a specific
    repository matched the search criteria.

    It inherits directly from `Base` as it doesn't require its own independent
    primary key or standard timestamp columns (`created_at`, `updated_at`).

    Attributes:
        keyword_search_session_id: Foreign key linking to the KeywordSearchSession. Part of the composite PK.
        repository_id: Foreign key linking to the Repository. Part of the composite PK.
        match_details: Optional JSON field to store data about the match, like relevance score or matched terms.
    """
    __tablename__ = "keyword_repository_associations"

    # --- Composite Primary Key and Foreign Keys ---
    # These two columns together uniquely identify a link between a specific
    # search session and a specific repository found during that session.

    # Foreign key to the KeywordSearchSession table. Part of the composite PK.
    # Indexed to optimize queries finding all repositories for a given session.
    keyword_search_session_id: Mapped[int] = mapped_column(
        ForeignKey("keyword_search_sessions.id", ondelete="CASCADE"),
        primary_key=True,
        index=True # Index this foreign key
    )
    # Foreign key to the Repositories table. Part of the composite PK.
    # Indexed to optimize queries finding all sessions that discovered a given repository.
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"),
        primary_key=True,
        index=True # Index this foreign key
    )

    # --- Optional Match Metadata ---
    # Store additional details about why this repository was considered a match
    # during the search process. This is flexible using JSONB.
    match_details: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=True
        # Example: {'score': 0.85, 'matched_in': ['description', 'readme'], 'terms': ['quantum computing']}
    )

    # --- Relationships (Optional) ---
    # Relationships can be defined for easier navigation in code, though they might
    # not be strictly necessary if queries usually start from Session or Repository.
    # Uncomment and adjust `back_populates` if needed in related models.
    # search_session: Mapped["KeywordSearchSession"] = relationship(
    #     back_populates="repository_associations" # Requires KeywordSearchSession.repository_associations
    # )
    # repository: Mapped["Repository"] = relationship(
    #     # No back_populates needed if Repository doesn't link back directly.
    # )

    # --- Table Arguments ---
    # The composite primary key inherently creates a unique constraint and an index
    # on `(keyword_search_session_id, repository_id)`. Explicit single-column indexes
    # are defined above using `index=True` on the `mapped_column` definitions.
    # Additional specific indexes could be added here if complex query patterns emerge.
    # __table_args__ = (
    #     Index('ix_kw_repo_assoc_match_details_score', 'match_details["score"]'), # Example index on JSONB field
    # )

    def __repr__(self):
        """Provides a concise string representation for debugging and logging."""
        return (f"<KeywordRepoAssoc(session_id={self.keyword_search_session_id}, "
                f"repo_id={self.repository_id})>")