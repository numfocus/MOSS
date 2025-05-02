"""
backend.data.models.issue
-------------------------
This module defines the Issue model, representing a GitHub Issue associated
with a specific Repository tracked by the system.
"""

import logging
from typing import Optional, TYPE_CHECKING
from datetime import datetime # Required for DateTime type hints

from sqlalchemy import (
    String, Integer, Text, Boolean, DateTime, BigInteger, ForeignKey, Index
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

# Assuming Base and BaseModel are correctly defined elsewhere
# Adjust import paths as necessary
from ..database import Base
from .base import BaseModel

# Use TYPE_CHECKING to prevent circular imports for type hints
if TYPE_CHECKING:
    from .repository import Repository
    from .contributor import Contributor # Assumes the issue author is stored as a Contributor

logger = logging.getLogger(__name__)

class Issue(BaseModel, Base):
    """
    Represents a GitHub Issue linked to a Repository.

    This model stores core information about a GitHub issue, mirroring data
    retrieved from the GitHub API. It links the issue to its repository and
    the user (Contributor) who created it.

    Inherits common fields like `id`, `created_at`, `updated_at` from `BaseModel`.

    Attributes:
        github_id: The unique numerical ID assigned by GitHub to the issue.
        repository_id: Foreign key linking to the Repository this issue belongs to.
        user_id: Foreign key linking to the Contributor who created the issue.
        number: The issue number, unique within its repository (e.g., #123).
        title: The title text of the issue.
        state: The current state of the issue ('open' or 'closed').
        gh_created_at: Timestamp when the issue was created on GitHub.
        gh_updated_at: Timestamp when the issue was last updated on GitHub.
        gh_closed_at: Timestamp when the issue was closed on GitHub (if applicable).
        repository: Relationship back to the parent Repository object.
        user: Relationship back to the Contributor (author) object.
    """
    __tablename__ = "issues"

    # --- GitHub Identifiers ---
    # Unique IDs connecting this record to the source GitHub data.

    # GitHub's unique ID for this specific issue. Indexed for efficient lookup.
    github_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)

    # --- Foreign Keys ---
    # Links to related entities (Repository, Contributor).

    # Link to the parent repository. Indexed. Cascade delete ensures issues
    # are removed if their repository is deleted.
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # Link to the Contributor record representing the issue's author. Indexed.
    # Assumes the author exists in the 'contributors' table. `ondelete` behavior
    # might need consideration (e.g., SET NULL if a contributor is deleted?).
    user_id: Mapped[int] = mapped_column(
        ForeignKey("contributors.id"), index=True, nullable=False
    )

    # --- Core Issue Details ---
    # Essential information about the issue content and status.

    # The issue number, unique within the context of its repository.
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    # The title of the issue. Stored as Text for potentially long titles.
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # State of the issue, typically 'open' or 'closed'. Indexed for filtering.
    state: Mapped[str] = mapped_column(String, index=True, nullable=False)

    # --- GitHub Timestamps ---
    # Stores the original timestamps from GitHub, preserving timezone information.

    # When the issue was created on GitHub.
    gh_created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # When the issue was last updated on GitHub.
    gh_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # When the issue was closed on GitHub (NULL if still open).
    gh_closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- Relationships ---
    # Define relationships for navigating from an Issue instance.

    # Relationship to the parent Repository.
    # No `back_populates` needed if Repository doesn't have an 'issues' collection.
    repository: Mapped["Repository"] = relationship()

    # Relationship to the Contributor who authored the issue.
    # No `back_populates` needed if Contributor doesn't have an 'issues_authored' collection.
    user: Mapped["Contributor"] = relationship()

    # --- Table Arguments ---
    # Define indexes to optimize common query patterns.
    __table_args__ = (
        # Individual indexes on foreign keys and state/number for common filtering/sorting.
        Index('ix_issues_repo_id', 'repository_id'),
        Index('ix_issues_user_id', 'user_id'),
        Index('ix_issues_state', 'state'),
        Index('ix_issues_number', 'number'),
        # Composite index for efficiently finding a specific issue number within a specific repo.
        Index('ix_issues_repo_number', 'repository_id', 'number'),
    )

    def __repr__(self):
        """Provides a concise string representation for debugging and logging."""
        # Uses getattr for id in case the instance isn't flushed yet
        obj_id = getattr(self, 'id', None)
        return (f"<Issue(id={obj_id}, gh_id={self.github_id}, "
                f"repo_id={self.repository_id}, number=#{self.number}, "
                f"state='{self.state}')>")