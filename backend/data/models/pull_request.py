"""
backend.data.models.pull_request
--------------------------------
This module defines the PullRequest model, representing a GitHub Pull Request
associated with a specific Repository tracked by the system.
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
    from .contributor import Contributor # Assumes the PR author is stored as a Contributor

logger = logging.getLogger(__name__)

class PullRequest(BaseModel, Base):
    """
    Represents a GitHub Pull Request linked to a Repository.

    This model stores core information about a GitHub pull request, mirroring
    data retrieved from the GitHub API. It connects the PR to its repository,
    the author (Contributor), and tracks its state (open, closed, merged) and
    key timestamps.

    Inherits common fields like `id`, `created_at`, `updated_at` from `BaseModel`.

    Attributes:
        github_id: The unique numerical ID assigned by GitHub to the pull request.
        repository_id: Foreign key linking to the Repository this PR belongs to.
        user_id: Foreign key linking to the Contributor who opened the PR.
        number: The pull request number, unique within its repository (e.g., #45).
        title: The title text of the pull request.
        state: The current state ('open' or 'closed'). Merged status is indicated by `gh_merged_at`.
        gh_created_at: Timestamp when the PR was created on GitHub.
        gh_updated_at: Timestamp when the PR was last updated on GitHub.
        gh_closed_at: Timestamp when the PR was closed on GitHub (if closed).
        gh_merged_at: Timestamp when the PR was merged on GitHub (if merged).
        repository: Relationship back to the parent Repository object.
        user: Relationship back to the Contributor (author) object.
    """
    __tablename__ = "pull_requests"

    # --- GitHub Identifier ---
    # Unique ID connecting this record to the source GitHub data.

    # GitHub's unique ID for this specific pull request. Indexed.
    github_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)

    # --- Foreign Keys ---
    # Links to related entities (Repository, Contributor).

    # Link to the parent repository. Indexed. Cascade delete ensures PRs
    # are removed if their repository is deleted.
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # Link to the Contributor record representing the PR's author. Indexed.
    # Assumes the author exists in the 'contributors' table.
    user_id: Mapped[int] = mapped_column(
        ForeignKey("contributors.id"), index=True, nullable=False
    )

    # --- Core Pull Request Details ---
    # Essential information about the PR content and status.

    # The PR number, unique within the context of its repository.
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    # The title of the pull request. Stored as Text for potentially long titles.
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # State: 'open' or 'closed'. Whether it was merged is determined by gh_merged_at. Indexed.
    state: Mapped[str] = mapped_column(String, index=True, nullable=False)

    # --- GitHub Timestamps ---
    # Stores key lifecycle timestamps from GitHub, preserving timezone information.

    # When the PR was created on GitHub.
    gh_created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # When the PR was last updated on GitHub.
    gh_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # When the PR was closed on GitHub (whether merged or not). NULL if still open.
    gh_closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # When the PR was merged on GitHub. NULL if not merged (either open or closed without merge).
    gh_merged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- Relationships ---
    # Define relationships for navigating from a PullRequest instance.

    # Relationship to the parent Repository.
    # No `back_populates` needed if Repository doesn't have a 'pull_requests' collection.
    repository: Mapped["Repository"] = relationship()

    # Relationship to the Contributor who opened the PR.
    # No `back_populates` needed if Contributor doesn't have a 'pull_requests_opened' collection.
    user: Mapped["Contributor"] = relationship()

    # --- Table Arguments ---
    # Define indexes to optimize common query patterns.
    __table_args__ = (
        # Individual indexes on foreign keys, state, and number.
        Index('ix_pull_requests_repo_id', 'repository_id'),
        Index('ix_pull_requests_user_id', 'user_id'),
        Index('ix_pull_requests_state', 'state'),
        Index('ix_pull_requests_number', 'number'),
        # Composite index for efficiently finding a specific PR number within a specific repo.
        Index('ix_pull_requests_repo_number', 'repository_id', 'number'),
    )

    def __repr__(self):
        """Provides a concise string representation for debugging and logging."""
        # Safely access 'id' which comes from BaseModel
        obj_id = getattr(self, 'id', None)
        # Display 'merged' status explicitly if applicable, otherwise show 'open'/'closed'.
        merged_status = "merged" if self.gh_merged_at else self.state
        return (f"<PullRequest(id={obj_id}, gh_id={self.github_id}, "
                f"repo_id={self.repository_id}, number=#{self.number}, "
                f"state='{merged_status}')>")